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


#: FRED's public CSV export endpoint -- stable, keyless and dependency-free.
_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _read_fred_csv(text: str) -> pd.DataFrame:
    """Read one FRED ``fredgraph.csv`` payload into a date-indexed frame.

    Validates that the response actually *is* CSV before handing it to the
    parser -- FRED occasionally answers with an HTML error/rate-limit page, and
    feeding that to ``read_csv`` produces a cryptic "Error tokenizing data"
    instead of an actionable message. The date column has been ``DATE`` (legacy)
    or ``observation_date`` (current) over the years, so accept both.
    """
    import io

    head = text.lstrip()[:1]
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if head == "<" or "," not in first_line:
        snippet = text.strip()[:160].replace("\n", " ")
        raise ValueError(f"FRED did not return CSV (got: {snippet!r}).")

    raw = pd.read_csv(io.StringIO(text), na_values=["."])
    date_col = next((c for c in ("observation_date", "DATE", "date") if c in raw.columns),
                    raw.columns[0])
    raw = raw.rename(columns={date_col: "date"})
    raw["date"] = pd.to_datetime(raw["date"])
    return raw


def _finalize_macro(frame: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Turn an assembled frame (``date`` + raw FRED series columns) into the
    macro feature frame: rename, derive year-over-year CPI, forward-fill."""
    for code in settings.fred_series:
        if code not in frame.columns:
            raise ValueError(f"FRED response missing series '{code}'.")
        frame[code] = pd.to_numeric(frame[code], errors="coerce")

    series = frame.rename(columns=settings.fred_series).set_index("date").sort_index()

    # CPI (CPIAUCSL) is monthly while the 10y yield is daily, so the merged frame
    # has CPI only on month-start rows and NaN elsewhere. Year-over-year change
    # must be computed on the *monthly* observations (12 periods = 12 months),
    # then aligned back onto the daily index -- not via pct_change(12) on the
    # daily frame, which would compare against 12 calendar days ago.
    cpi_monthly = series["cpi"].dropna()
    cpi_yoy = cpi_monthly.pct_change(12) * 100.0
    series["cpi_yoy"] = cpi_yoy.reindex(series.index).ffill()

    macro = series[["treasury_10y", "cpi_yoy"]].ffill().reset_index()
    if macro.empty:
        raise ValueError("FRED returned an empty frame.")
    return macro


def _parse_fred_csv(text: str, settings: Settings) -> pd.DataFrame:
    """Parse a single combined ``fredgraph.csv`` payload into the macro frame.

    Pure function (no network) so it can be unit-tested directly.
    """
    return _finalize_macro(_read_fred_csv(text), settings)


def _load_macro(settings: Settings) -> pd.DataFrame:
    """Fetch each FRED series in its own request and merge on date.

    ``fredgraph.csv`` is only reliable one series at a time; a comma-joined
    ``id=A,B`` can return an unexpected layout. Fetching per series (the same
    approach ``pandas-datareader`` used) and outer-joining on date is robust.
    """
    import requests

    def _fetch(series_id: str) -> pd.DataFrame:
        @_retryer(settings)
        def _download() -> pd.DataFrame:
            resp = requests.get(
                _FRED_CSV_URL,
                params={
                    "id": series_id,
                    "cosd": settings.date_start,
                    "coed": settings.date_end,
                },
                headers={"User-Agent": "stock-drop-analysis/1.0"},
                timeout=settings.fetch_timeout_seconds,
            )
            resp.raise_for_status()
            if not resp.text.strip():
                raise ValueError(f"FRED returned an empty response for '{series_id}'.")
            return _read_fred_csv(resp.text)

        return _download()

    merged: pd.DataFrame | None = None
    for code in settings.fred_series:
        part = _fetch(code)
        keep = ["date", code] if code in part.columns else list(part.columns)
        part = part[keep]
        merged = part if merged is None else merged.merge(part, on="date", how="outer")

    return _finalize_macro(merged, settings)


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
