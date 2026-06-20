"""Synthetic data generator.

Produces a realistic-shaped panel so the pipeline can run offline (tests, CI,
previews). Numbers are illustrative only and must never be reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Settings
from app.core.features import FEATURE_COLUMNS, label_drops

_OUTPUT = FEATURE_COLUMNS + ["ret_1d", "is_drop", "ticker", "sector", "date"]


def generate_synthetic_panel(settings: Settings, n_days: int = 750) -> pd.DataFrame:
    """Return a clean modelling panel built from random-but-plausible data."""
    rng = np.random.default_rng(settings.random_state)
    dates = pd.bdate_range(settings.date_start, periods=n_days)

    market_ret = rng.normal(0.0004, 0.011, n_days)
    vix = np.clip(18 + np.cumsum(rng.normal(0, 0.8, n_days)) * 0.3, 10, 60)
    treasury = np.clip(2.5 + np.cumsum(rng.normal(0, 0.02, n_days)) * 0.05, 0.5, 5)
    cpi = np.clip(3 + np.cumsum(rng.normal(0, 0.03, n_days)) * 0.05, 0, 9)

    frames = []
    for tkr, sector in settings.tickers.items():
        beta = rng.uniform(0.8, 1.8)
        ret = beta * market_ret + rng.normal(0, 0.018, n_days)
        for _ in range(int(rng.integers(2, 5))):          # inject idiosyncratic crashes
            ret[int(rng.integers(30, n_days))] -= rng.uniform(0.10, 0.28)
        volume = np.abs(rng.uniform(1e7, 5e7) * (1 + 3 * np.abs(ret)
                        + rng.normal(0, 0.1, n_days)))
        frames.append(pd.DataFrame({
            "date": dates, "ticker": tkr, "sector": sector,
            "ret_1d": ret, "market_ret": market_ret, "volume": volume,
            "vix_close": vix, "treasury_10y": treasury, "cpi_yoy": cpi,
        }))

    panel = pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])
    panel["ret_prev"] = panel.groupby("ticker")["ret_1d"].shift(1)
    panel["momentum_5d"] = panel.groupby("ticker")["ret_1d"].transform(
        lambda s: s.rolling(5).sum())
    g = panel.groupby("ticker")["volume"]
    panel["volume_z"] = ((panel["volume"] - g.transform(lambda s: s.rolling(20).mean()))
                         / g.transform(lambda s: s.rolling(20).std()))
    panel["volatility_20d"] = panel.groupby("ticker")["ret_1d"].transform(
        lambda s: s.rolling(20).std())
    panel["vix"] = panel["vix_close"]
    panel["vix_change"] = panel.groupby("ticker")["vix_close"].pct_change()
    panel["is_drop"] = label_drops(panel["ret_1d"], settings).astype(int)

    return panel.dropna(subset=FEATURE_COLUMNS + ["ret_1d"])[_OUTPUT].reset_index(drop=True)
