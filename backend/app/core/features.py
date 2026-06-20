"""Feature engineering and drop labelling.

These are deliberately *pure* functions over DataFrames so they can be unit
tested without any network access.

Leakage note: the binary label ``is_drop`` is derived from the same-day return
``ret_1d``; therefore ``ret_1d`` is never included in :data:`FEATURE_COLUMNS`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Settings
from app.core.earnings import add_earnings_context
from app.core.factors import add_factor_decomposition
from app.core.macro_calendar import add_macro_context
from app.exceptions import InsufficientDataError

#: Candidate driver features shared by every model.
FEATURE_COLUMNS: list[str] = [
    "market_ret",
    "volume_z",
    "volatility_20d",
    "ret_prev",
    "momentum_5d",
    "vix",
    "vix_change",
    "treasury_10y",
    "cpi_yoy",
]

#: Attribution-only columns (same-day quantities): used to explain a drop, never
#: as model features. ``near_fomc`` is excluded from the NaN-drop subset so early
#: rows (before betas can be estimated) are still usable for the classifiers.
ANALYSIS_COLUMNS = ["sector_ret", "systematic_ret", "idio_ret", "idio_z",
                    "rate_chg_bp", "near_fomc", "near_earnings", "eps_surprise"]

_REQUIRED_OUTPUT = (FEATURE_COLUMNS + ["ret_1d", "is_drop", "ticker", "sector", "date"]
                    + ANALYSIS_COLUMNS)


def label_drops(returns: pd.Series, settings: Settings) -> pd.Series:
    """Flag significant single-day drops as a boolean Series."""
    if settings.drop_method == "percentile":
        valid = returns.dropna()
        if valid.empty:
            raise InsufficientDataError("No returns available to compute a percentile cutoff.")
        cutoff = float(np.percentile(valid, settings.drop_percentile))
        return returns <= cutoff
    return returns <= settings.drop_threshold


def build_features(prices: pd.DataFrame, macro: pd.DataFrame, settings: Settings,
                   earnings_events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Engineer per-stock, per-day driver features and the drop label.

    Parameters
    ----------
    prices : long-format frame with date, ticker, close, volume, sector,
             market_close, vix_close.
    macro  : daily frame with date, treasury_10y, cpi_yoy.
    earnings_events : optional [ticker, date, eps_surprise] used to tag drops
             that landed on/around an earnings announcement.
    """
    if prices.empty:
        raise InsufficientDataError("Price frame is empty; nothing to engineer.")

    df = prices.sort_values(["ticker", "date"]).copy()

    df["ret_1d"] = df.groupby("ticker")["close"].pct_change()
    df["ret_prev"] = df.groupby("ticker")["ret_1d"].shift(1)
    df["momentum_5d"] = df.groupby("ticker")["close"].pct_change(5)
    df["market_ret"] = df["market_close"].pct_change()

    vol = df.groupby("ticker")["volume"]
    vol_mean = vol.transform(lambda s: s.rolling(20).mean())
    vol_std = vol.transform(lambda s: s.rolling(20).std())
    df["volume_z"] = (df["volume"] - vol_mean) / vol_std.replace(0, np.nan)

    df["volatility_20d"] = df.groupby("ticker")["ret_1d"].transform(
        lambda s: s.rolling(20).std()
    )
    df["vix"] = df["vix_close"]
    df["vix_change"] = df["vix_close"].pct_change()

    # Sector factor return (per ticker so it never crosses ticker boundaries).
    if "sector_close" in df.columns:
        df["sector_ret"] = df.groupby("ticker")["sector_close"].pct_change()
    else:
        df["sector_ret"] = np.nan

    df["date"] = pd.to_datetime(df["date"])
    macro = macro.copy()
    macro["date"] = pd.to_datetime(macro["date"])
    df = df.merge(macro, on="date", how="left")
    df[["treasury_10y", "cpi_yoy"]] = df[["treasury_10y", "cpi_yoy"]].ffill()

    df["is_drop"] = label_drops(df["ret_1d"], settings).astype("Int64")

    # Attribution layers (systematic vs idiosyncratic, macro and earnings context).
    df = add_factor_decomposition(df, window=settings.factor_window)
    df = add_macro_context(df)
    df = add_earnings_context(df, earnings_events, settings)

    clean = df.dropna(subset=FEATURE_COLUMNS + ["ret_1d", "is_drop"]).copy()
    clean["is_drop"] = clean["is_drop"].astype(int)

    if len(clean) < settings.min_rows_required:
        raise InsufficientDataError(
            f"Only {len(clean)} usable rows after cleaning; "
            f"need at least {settings.min_rows_required}. "
            "Widen the date window or check the data source."
        )
    return clean[_REQUIRED_OUTPUT].reset_index(drop=True)
