"""Curated calendar of well-documented global/market events.

Lets the per-company explanations say *what was happening in the world* on a drop
day ("during the COVID-19 crash"), not just the statistical signature. These are
established, dated episodes — not invented narrative. When a date falls in more
than one window the **most specific** (shortest) window wins, so a sharp event
(e.g. the Ukraine invasion) takes priority over a broad regime (the 2022 bear).

Honest scope: this ties drops to *macro/market* events. True per-ticker, per-day
news sentiment would need a news/headlines feed and is not faked here.
"""
from __future__ import annotations

import pandas as pd

#: (start, end, label, description). Windows are inclusive calendar dates.
MARKET_EVENTS: list[tuple[str, str, str, str]] = [
    ("2015-08-18", "2015-08-31", "China 'Black Monday'",
     "Global selloff as China devalued the yuan and growth fears spiked (Aug 24, 2015)."),
    ("2016-01-04", "2016-02-12", "Early-2016 oil/China scare",
     "Collapsing oil prices and China slowdown fears drove a sharp risk-off start to 2016."),
    ("2016-06-24", "2016-06-29", "Brexit vote shock",
     "Markets fell after the UK voted to leave the EU (referendum June 23, 2016)."),
    ("2018-02-05", "2018-02-12", "'Volmageddon'",
     "A record VIX spike unwound short-volatility bets (Feb 5, 2018)."),
    ("2018-10-01", "2018-12-27", "Q4 2018 selloff",
     "Fed tightening and trade-war fears drove a ~20% market drawdown into late December."),
    ("2020-02-20", "2020-04-07", "COVID-19 crash",
     "The fastest bear market on record as the pandemic shut down the economy (Feb–Mar 2020)."),
    ("2022-02-24", "2022-03-09", "Russia invades Ukraine",
     "Risk-off and an energy/commodity shock after the invasion (Feb 24, 2022)."),
    ("2023-03-08", "2023-03-20", "SVB / banking crisis",
     "Silicon Valley Bank's collapse triggered a regional-bank panic (Mar 2023)."),
    ("2024-07-31", "2024-08-07", "Aug 2024 carry unwind",
     "A global selloff as the yen carry trade unwound and US recession fears flared (Aug 5, 2024)."),
    # Broad regime — lowest priority (longest window); only used when no sharp
    # event matches a date.
    ("2022-01-03", "2022-10-14", "2022 Fed rate-hiking bear market",
     "A year-long drawdown in long-duration/growth names as the Fed hiked aggressively."),
]


def event_for(date) -> dict | None:
    """Return the most specific market event covering ``date`` (or ``None``)."""
    d = pd.Timestamp(date).normalize()
    matches = [e for e in MARKET_EVENTS
               if pd.Timestamp(e[0]) <= d <= pd.Timestamp(e[1])]
    if not matches:
        return None
    # Shortest window = most specific.
    start, end, label, desc = min(
        matches, key=lambda e: (pd.Timestamp(e[1]) - pd.Timestamp(e[0])).days)
    return {"label": label, "description": desc}


def event_breakdown(dates) -> list[dict]:
    """Tally how many of the given (drop) dates fall in each event, most first."""
    counts: dict[str, int] = {}
    for dt in dates:
        ev = event_for(dt)
        if ev:
            counts[ev["label"]] = counts.get(ev["label"], 0) + 1
    return [{"label": k, "count": v}
            for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]
