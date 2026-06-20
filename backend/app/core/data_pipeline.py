"""Data acquisition pipeline with retry, timeout and graceful fallback.

External data sources are flaky by nature, so every network call is wrapped in a
``tenacity`` retry with exponential backoff and re-raised as a typed
:class:`DataSourceError`. Results are cached so repeated requests in one run do
not re-hit the network.
"""
from __future__ import annotations

import pandas as pd
from tenacity import (RetryError, retry, retry_if_exception_type,
                      stop_after_attempt, wait_exponential)

from app.config import Settings, get_settings
from app.core.features import build_features
from app.core.synthetic import generate_synthetic_panel
from app.exceptions import DataSourceError
from app.logging_config import get_logger

logger = get_logger(__name__)

# In-process cache: settings fingerprint -> modelling panel.
_CACHE: dict[tuple, pd.DataFrame] = {}


def _retryer(settings: Settings):
    """Build a tenacity retry decorator from settings."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.fetch_max_attempts),
        wait=wait_exponential(multiplier=settings.fetch_backoff_seconds, max=20),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError, ValueError)),
        before_sleep=lambda rs: logger.warning(
            "Data fetch attempt %d failed (%s); retrying...",
            rs.attempt_number, rs.outcome.exception()),
    )


# --------------------------------------------------------------------------
# Raw loaders (network)
# --------------------------------------------------------------------------
def _load_prices(settings: Settings) -> pd.DataFrame:
    import yfinance as yf

    symbols = list(settings.tickers) + [settings.market_index, settings.vix_index]

    @_retryer(settings)
    def _download() -> pd.DataFrame:
        raw = yf.download(symbols, start=settings.date_start, end=settings.date_end,
                          auto_adjust=True, progress=False, group_by="ticker",
                          timeout=settings.fetch_timeout_seconds)
        if raw is None or raw.empty:
            raise ValueError("yfinance returned an empty frame.")
        return raw

    raw = _download()
    market = raw[settings.market_index]["Close"].rename("market_close")
    vix = raw[settings.vix_index]["Close"].rename("vix_close")
    market_df = pd.concat([market, vix], axis=1).reset_index()
    market_df.columns = ["date", "market_close", "vix_close"]

    frames = []
    for tkr, sector in settings.tickers.items():
        sub = raw[tkr][["Close", "Volume"]].copy()
        sub.columns = ["close", "volume"]
        sub = sub.reset_index().rename(columns={"Date": "date"})
        sub["ticker"], sub["sector"] = tkr, sector
        frames.append(sub)
    return pd.concat(frames, ignore_index=True).merge(market_df, on="date", how="left")


def _load_macro(settings: Settings) -> pd.DataFrame:
    from pandas_datareader import data as pdr

    @_retryer(settings)
    def _download() -> pd.DataFrame:
        series = pdr.DataReader(list(settings.fred_series), "fred",
                                settings.date_start, settings.date_end)
        if series is None or series.empty:
            raise ValueError("FRED returned an empty frame.")
        return series

    series = _download().rename(columns=settings.fred_series)
    series["cpi_yoy"] = series["cpi"].pct_change(12) * 100.0
    macro = series[["treasury_10y", "cpi_yoy"]].ffill().reset_index()
    return macro.rename(columns={"DATE": "date"})


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def _fingerprint(settings: Settings) -> tuple:
    return (settings.use_synthetic, settings.date_start, settings.date_end,
            settings.drop_method, settings.drop_threshold, settings.drop_percentile,
            tuple(sorted(settings.tickers)))


def get_modeling_dataset(settings: Settings | None = None,
                         use_cache: bool = True) -> pd.DataFrame:
    """Return the cleaned modelling panel used by all models.

    Raises
    ------
    DataSourceError
        If real data cannot be retrieved after all retry attempts.
    InsufficientDataError
        If the resulting panel is too small (raised from ``build_features``).
    """
    settings = settings or get_settings()
    key = _fingerprint(settings)
    if use_cache and key in _CACHE:
        logger.info("Returning cached dataset.")
        return _CACHE[key].copy()

    if settings.use_synthetic:
        logger.warning("USING SYNTHETIC DATA -- illustrative only; do not report.")
        data = generate_synthetic_panel(settings)
    else:
        try:
            logger.info("Fetching prices (yfinance) and macro (FRED)...")
            prices = _load_prices(settings)
            macro = _load_macro(settings)
        except (RetryError, Exception) as exc:  # noqa: BLE001 - re-typed below
            raise DataSourceError(
                f"Could not retrieve market/macro data after "
                f"{settings.fetch_max_attempts} attempts: {exc}"
            ) from exc
        data = build_features(prices, macro, settings)

    n_drops = int(data["is_drop"].sum())
    logger.info("Built panel: %d stock-days, %d drops (%.1f%%).",
                len(data), n_drops, 100 * n_drops / len(data))
    if use_cache:
        _CACHE[key] = data.copy()
    return data


def clear_cache() -> None:
    _CACHE.clear()
