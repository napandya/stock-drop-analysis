"""Macro context for drop attribution.

Two complementary signals tell you whether a fall was a macro/rates event:

1. **Rate shock (data-driven, always correct):** the same-day change in the
   10-year Treasury yield, in basis points. A large jump means a rates/duration
   move, which disproportionately hits long-duration growth names.

2. **FOMC proximity (calendar overlay):** scheduled FOMC announcement dates are
   public and stable, so we tag drops that land on/near one.

Honest limitation: a *true* surprise needs actual-vs-consensus data (CPI/PCE
prints, the dot plot), which requires a paid feed and is **not** included. The
rate-shock magnitude is the unbiased proxy used here. CPI release dates are
deliberately not hard-coded to avoid shipping wrong dates; extend
``_extra_event_dates`` if you wire a real macro-calendar source.
"""
from __future__ import annotations

import pandas as pd

#: Scheduled FOMC statement dates, 2021-2025. Public Fed calendar; verify/extend
#: as needed. Used only as an overlay -- the rate-shock signal is primary.
FOMC_DATES: list[str] = [
    # 2021
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16",
    "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
    "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
]

#: Extension point for additional event dates (e.g. CPI prints from a feed).
_extra_event_dates: list[str] = []


def add_macro_context(df: pd.DataFrame, near_days: int = 1) -> pd.DataFrame:
    """Add ``rate_chg_bp`` and ``near_fomc`` columns to a dated panel.

    ``rate_chg_bp`` is the day-over-day change in ``treasury_10y`` (basis points),
    computed on the per-date yield so it is identical across stocks on a day.
    ``near_fomc`` flags rows within ``near_days`` of a scheduled FOMC date.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    if "treasury_10y" in df.columns:
        # One yield per calendar date; diff on the date-level series, map back.
        per_date = df[["date", "treasury_10y"]].drop_duplicates("date").sort_values("date")
        per_date["rate_chg_bp"] = per_date["treasury_10y"].diff() * 100.0
        df = df.merge(per_date[["date", "rate_chg_bp"]], on="date", how="left")
    else:
        df["rate_chg_bp"] = pd.NA

    events = pd.to_datetime(FOMC_DATES + _extra_event_dates)
    if len(events):
        offsets = pd.to_timedelta(range(-near_days, near_days + 1), unit="D")
        windowed = {e + off for e in events for off in offsets}
        df["near_fomc"] = df["date"].isin(windowed)
    else:
        df["near_fomc"] = False
    return df


def macro_context_for(row) -> dict:
    """Per-event macro context summary for an explanation payload."""
    bp = row.get("rate_chg_bp")
    near = bool(row.get("near_fomc", False))
    return {
        "rate_chg_bp": (round(float(bp), 1) if pd.notna(bp) else None),
        "near_fomc": near,
    }
