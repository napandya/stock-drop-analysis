"""Synthetic data generator.

Produces a realistic-shaped panel so the pipeline can run offline (tests, CI,
previews). Numbers are illustrative only and must never be reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Settings
from app.core.earnings import add_earnings_context
from app.core.factors import add_factor_decomposition
from app.core.features import ANALYSIS_COLUMNS, FEATURE_COLUMNS, label_drops
from app.core.macro_calendar import add_macro_context

_OUTPUT = (FEATURE_COLUMNS + ["ret_1d", "is_drop", "ticker", "sector", "date"]
           + ANALYSIS_COLUMNS)


def generate_synthetic_panel(settings: Settings, n_days: int = 750) -> pd.DataFrame:
    """Return a clean modelling panel built from random-but-plausible data.

    Returns carry a genuine market + sector factor structure plus idiosyncratic
    crashes, so the factor decomposition has something real to recover offline.
    """
    rng = np.random.default_rng(settings.random_state)
    dates = pd.bdate_range(settings.date_start, periods=n_days)

    market_ret = rng.normal(0.0004, 0.011, n_days)
    vix = np.clip(18 + np.cumsum(rng.normal(0, 0.8, n_days)) * 0.3, 10, 60)
    treasury = np.clip(2.5 + np.cumsum(rng.normal(0, 0.02, n_days)) * 0.05, 0.5, 5)
    cpi = np.clip(3 + np.cumsum(rng.normal(0, 0.03, n_days)) * 0.05, 0, 9)

    # One sector factor per distinct sector, correlated with the market.
    sectors = list(dict.fromkeys(settings.tickers.values()))
    sector_rets = {sec: rng.uniform(0.7, 1.1) * market_ret + rng.normal(0, 0.006, n_days)
                   for sec in sectors}

    frames = []
    for tkr, sector in settings.tickers.items():
        sret = sector_rets[sector]
        bm, bs = rng.uniform(0.6, 1.3), rng.uniform(0.3, 0.9)
        ret = bm * market_ret + bs * sret + rng.normal(0, 0.012, n_days)
        for _ in range(int(rng.integers(2, 5))):          # inject idiosyncratic crashes
            ret[int(rng.integers(30, n_days))] -= rng.uniform(0.10, 0.28)
        volume = np.abs(rng.uniform(1e7, 5e7) * (1 + 3 * np.abs(ret)
                        + rng.normal(0, 0.1, n_days)))
        frames.append(pd.DataFrame({
            "date": dates, "ticker": tkr, "sector": sector,
            "ret_1d": ret, "market_ret": market_ret, "sector_ret": sret,
            "volume": volume, "vix_close": vix, "treasury_10y": treasury, "cpi_yoy": cpi,
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

    # Synthetic quarterly earnings (~every 63 trading days) with random surprise.
    ev_rows = [{"ticker": tkr, "date": pd.Timestamp(d),
                "eps_surprise": float(rng.normal(2, 8))}
               for tkr in settings.tickers for d in dates[::63]]
    events = pd.DataFrame(ev_rows)

    panel = add_factor_decomposition(panel, window=settings.factor_window)
    panel = add_macro_context(panel)
    panel = add_earnings_context(panel, events, settings)

    return panel.dropna(subset=FEATURE_COLUMNS + ["ret_1d"])[_OUTPUT].reset_index(drop=True)
