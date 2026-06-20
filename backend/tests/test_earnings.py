"""Tests for the earnings-catalyst overlay (offline; no network)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.core import earnings
from app.core.data_pipeline import get_modeling_dataset


def _panel():
    dates = pd.bdate_range("2022-01-03", periods=30)
    return pd.DataFrame({"ticker": "X", "date": dates})


def test_add_earnings_context_tags_window_and_surprise():
    s = Settings(earnings_event_window=4)
    events = pd.DataFrame({"ticker": ["X"], "date": [pd.Timestamp("2022-01-13")],
                           "eps_surprise": [-8.5]})
    out = earnings.add_earnings_context(_panel(), events, s)

    near = out[out["near_earnings"]]
    assert not near.empty
    # Every tagged row is within the calendar-day window of the announcement.
    assert (near["date"] - pd.Timestamp("2022-01-13")).abs().max() <= pd.Timedelta(days=4)
    # The surprise is attached to the tagged rows, and rows far away are untagged.
    assert (near["eps_surprise"] == -8.5).all()
    assert not out.loc[out["date"] == pd.Timestamp("2022-01-03"), "near_earnings"].iloc[0]


def test_add_earnings_context_handles_no_events():
    out = earnings.add_earnings_context(_panel(), pd.DataFrame(
        columns=["ticker", "date", "eps_surprise"]), Settings())
    assert not out["near_earnings"].any()
    assert out["eps_surprise"].isna().all()


def test_earnings_context_for_payload():
    row = {"near_earnings": True, "eps_surprise": -12.34}
    ctx = earnings.earnings_context_for(row)
    assert ctx == {"near_earnings": True, "eps_surprise": -12.3}
    # Missing surprise -> None, not NaN.
    assert earnings.earnings_context_for({"near_earnings": False,
                                          "eps_surprise": np.nan})["eps_surprise"] is None


def test_panel_carries_earnings_columns():
    s = Settings(use_synthetic=True, min_rows_required=50,
                 tickers={"AAA": "Technology", "BBB": "Financials"})
    data = get_modeling_dataset(s, use_cache=False)
    assert {"near_earnings", "eps_surprise"} <= set(data.columns)
    assert data["near_earnings"].any()      # synthetic generates quarterly earnings
