"""Tests for the curated market-event calendar."""
from __future__ import annotations

from app.core import market_events as me


def test_event_for_known_dates():
    assert me.event_for("2020-03-16")["label"] == "COVID-19 crash"
    assert me.event_for("2023-03-13")["label"] == "SVB / banking crisis"
    assert me.event_for("2015-08-24")["label"] == "China 'Black Monday'"
    assert me.event_for("2019-07-01") is None          # quiet date -> no event


def test_event_for_prefers_most_specific_window():
    # Feb 25 2022 sits in both the year-long 2022 bear and the short Ukraine
    # window -> the specific event wins.
    assert me.event_for("2022-02-25")["label"] == "Russia invades Ukraine"
    # Mid-2022 is only covered by the broad regime.
    assert me.event_for("2022-06-15")["label"].startswith("2022 Fed")


def test_event_breakdown_counts_sorts_and_skips_non_events():
    dates = ["2020-03-16", "2020-03-18", "2023-03-13", "2019-01-01"]
    bd = me.event_breakdown(dates)
    counts = {b["label"]: b["count"] for b in bd}
    assert counts["COVID-19 crash"] == 2
    assert counts["SVB / banking crisis"] == 1
    assert all("count" in b and "label" in b for b in bd)
    assert bd == sorted(bd, key=lambda b: b["count"], reverse=True)
    # The non-event date contributes nothing.
    assert sum(b["count"] for b in bd) == 3
