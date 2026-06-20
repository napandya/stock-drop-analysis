"""Return decomposition: systematic (market + sector) vs. idiosyncratic.

A single-day fall is only an "explanation" once you know whether the stock fell
*because the market/sector fell* (beta) or because something specific hit the
name. We estimate each stock's market and sector betas on a **trailing** window
(strictly past data -> no look-ahead), predict the systematic part of today's
return, and treat the residual as idiosyncratic.

    ret = alpha + beta_mkt * market_ret + beta_sec * sector_ret + idio
    systematic_ret = beta_mkt * market_ret + beta_sec * sector_ret   (excl. alpha)
    idio_ret       = ret - systematic_ret

These columns are *attribution only* -- they are same-day quantities and must
never enter the model feature set (that would be leakage).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

#: Sector -> SPDR sector ETF, used as the sector factor. Tickers whose sector is
#: unknown fall back to a market-only (CAPM) decomposition.
SECTOR_ETF: dict[str, str] = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Real Estate": "XLRE",
}

DECOMP_COLUMNS = ["systematic_ret", "idio_ret", "idio_z"]


def sector_etfs_for(sectors) -> list[str]:
    """ETF symbols needed to cover the given sectors (deduped, order-stable)."""
    seen = {}
    for s in sectors:
        etf = SECTOR_ETF.get(s)
        if etf:
            seen[etf] = None
    return list(seen)


def _rolling_systematic(y: np.ndarray, factors: np.ndarray, window: int) -> np.ndarray:
    """Predicted systematic return per day from trailing-window OLS.

    ``factors`` is (n, k) with no intercept column; an intercept is fitted but
    excluded from the systematic component (alpha is stock-specific drift).
    """
    n = len(y)
    out = np.full(n, np.nan)
    for t in range(window, n):
        yw = y[t - window:t]
        xw = factors[t - window:t]
        ft = factors[t]
        m = np.isfinite(yw) & np.isfinite(xw).all(axis=1)
        if m.sum() < max(10, int(window * 0.6)) or not np.isfinite(ft).all():
            continue
        design = np.column_stack([np.ones(m.sum()), xw[m]])
        beta, *_ = np.linalg.lstsq(design, yw[m], rcond=None)
        out[t] = float(beta[1:] @ ft)        # exclude intercept (alpha)
    return out


def add_factor_decomposition(df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """Add ``systematic_ret``, ``idio_ret`` and ``idio_z`` per stock-day.

    Requires ``ret_1d`` and ``market_ret``; uses ``sector_ret`` when present and
    non-empty for a ticker, otherwise decomposes on the market factor alone.
    """
    df = df.sort_values(["ticker", "date"]).copy()
    has_sector = "sector_ret" in df.columns
    systematic = np.full(len(df), np.nan)

    for _, idx in df.groupby("ticker").indices.items():
        sub = df.iloc[idx]
        cols = ["market_ret"]
        if has_sector and sub["sector_ret"].notna().any():
            cols = ["market_ret", "sector_ret"]
        y = sub["ret_1d"].to_numpy(dtype=float)
        factors = sub[cols].to_numpy(dtype=float)
        systematic[idx] = _rolling_systematic(y, factors, window)

    df["systematic_ret"] = systematic
    df["idio_ret"] = df["ret_1d"] - df["systematic_ret"]
    # Idiosyncratic move in units of its own trailing volatility (shifted so the
    # current day is excluded from its own normalisation).
    df["idio_z"] = df.groupby("ticker")["idio_ret"].transform(
        lambda s: s / s.rolling(window).std().shift(1)
    )
    return df


def drop_attribution(systematic_ret: float, ret_1d: float) -> dict:
    """Classify a fall as market/sector-driven, stock-specific or mixed."""
    if not np.isfinite(systematic_ret) or not np.isfinite(ret_1d) or ret_1d >= 0:
        return {"type": "unknown", "systematic_share": None, "idio_share": None}
    share = float(np.clip(systematic_ret / ret_1d, 0.0, 1.0))
    kind = ("market/sector-driven" if share >= 0.6
            else "stock-specific" if share <= 0.3 else "mixed")
    return {"type": kind,
            "systematic_share": round(share, 2),
            "idio_share": round(1.0 - share, 2)}
