"""Earnings catalysts.

The largest single-name drops are usually *events*, and the most common event is
an earnings report. Yahoo exposes the announcement dates **and** the EPS surprise
(reported vs. consensus) back ~12 years for established names, so we can flag
whether a fall landed on/around earnings and whether the company missed.

``eps_surprise`` and ``near_earnings`` are attribution-only columns -- they
explain a drop, they are not model features. The fetch is best-effort: Yahoo's
earnings endpoint scrapes and can be flaky, so a failure for a ticker simply
leaves it untagged rather than failing the request.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger(__name__)

EARNINGS_COLUMNS = ["near_earnings", "eps_surprise"]


def fetch_earnings_events(tickers, settings: Settings) -> pd.DataFrame:
    """Return ``[ticker, date, eps_surprise]`` earnings events within the study
    window. Best-effort per ticker; never raises."""
    import yfinance as yf

    rows = []
    for tkr in tickers:
        try:
            ed = yf.Ticker(tkr).get_earnings_dates(limit=settings.earnings_history_limit)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("Earnings fetch failed for %s: %s", tkr, exc)
            continue
        if ed is None or ed.empty:
            continue
        e = ed.reset_index()
        date_col = next((c for c in e.columns if "Date" in str(c)), e.columns[0])
        surp_col = next((c for c in e.columns if "Surprise" in str(c)), None)
        e = e.rename(columns={date_col: "date", surp_col: "eps_surprise"})
        e["date"] = pd.to_datetime(e["date"], utc=True).dt.tz_localize(None).dt.normalize()
        e["ticker"] = tkr
        if "eps_surprise" not in e.columns:
            e["eps_surprise"] = np.nan
        rows.append(e[["ticker", "date", "eps_surprise"]])

    if not rows:
        return pd.DataFrame(columns=["ticker", "date", "eps_surprise"])
    out = pd.concat(rows, ignore_index=True)
    start, end = pd.Timestamp(settings.date_start), pd.Timestamp(settings.date_end)
    return out[(out["date"] >= start) & (out["date"] <= end)].reset_index(drop=True)


def add_earnings_context(panel: pd.DataFrame, events: pd.DataFrame | None,
                         settings: Settings) -> pd.DataFrame:
    """Tag each stock-day with ``near_earnings`` and the matched ``eps_surprise``.

    A day is "near earnings" if it falls within ``earnings_event_window`` calendar
    days of one of that ticker's announcements (a window wide enough to bridge a
    weekend, since reports after the close move the next trading day).
    """
    panel = panel.copy()
    # Coerce to a common datetime resolution: yfinance prices land as
    # datetime64[s] on pandas 3.0 while parsed earnings dates are [us], and
    # merge_asof refuses to join keys of differing resolution.
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel["near_earnings"] = False
    panel["eps_surprise"] = np.nan
    if events is None or events.empty:
        return panel

    events = events.copy()
    events["date"] = pd.to_datetime(events["date"]).astype("datetime64[ns]")

    tol = pd.Timedelta(days=settings.earnings_event_window)
    for tkr, ev in events.groupby("ticker"):
        eds = ev.dropna(subset=["date"]).sort_values("date").copy()
        if eds.empty:
            continue
        eds["_match"] = True
        sub = panel[panel["ticker"] == tkr].sort_values("date")
        if sub.empty:
            continue
        m = pd.merge_asof(sub[["date"]], eds[["date", "eps_surprise", "_match"]],
                          on="date", direction="nearest", tolerance=tol)
        panel.loc[sub.index, "near_earnings"] = m["_match"].fillna(False).to_numpy()
        panel.loc[sub.index, "eps_surprise"] = m["eps_surprise"].to_numpy()
    return panel


def earnings_context_for(row) -> dict:
    """Per-event earnings context for an explanation payload."""
    near = bool(row.get("near_earnings", False))
    surp = row.get("eps_surprise")
    return {
        "near_earnings": near,
        "eps_surprise": (round(float(surp), 1) if pd.notna(surp) else None),
    }
