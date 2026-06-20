"""Real-data contract test (opt-in: `pytest --run-live`).

Synthetic data is fast and deterministic but uses one tidy datetime resolution
and clean schemas, so it can't catch real-world format drift -- exactly how the
yfinance ``datetime64[s]`` vs parsed-earnings ``datetime64[us]`` mismatch slipped
through and 500'd the live endpoint. This test runs the *real* pipeline on a tiny
fetch and asserts the column/dtype contract every downstream consumer relies on.

It is skipped unless ``--run-live`` is passed, and skips itself (rather than
failing) when a data source is unreachable, so it never flakes a normal run.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.config import Settings
from app.core.data_pipeline import get_modeling_dataset
from app.core.features import ANALYSIS_COLUMNS, FEATURE_COLUMNS
from app.exceptions import DataSourceError
from app.models import explain

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_panel():
    """A small real panel: 2 liquid names over ~18 months (prices + FRED +
    earnings). Skips if any upstream source is unreachable."""
    s = Settings(use_synthetic=False, min_rows_required=50,
                 date_start="2023-01-01", date_end="2024-06-30",
                 tickers={"AAPL": "Technology", "MSFT": "Technology"})
    try:
        return get_modeling_dataset(s, use_cache=False), s
    except DataSourceError as exc:
        pytest.skip(f"data source unreachable: {exc}")


def test_live_panel_satisfies_schema_contract(live_panel):
    data, _ = live_panel
    expected = set(FEATURE_COLUMNS + ANALYSIS_COLUMNS
                   + ["ret_1d", "is_drop", "ticker", "sector", "date"])
    assert expected <= set(data.columns)
    assert not data.empty
    assert {"AAPL", "MSFT"} <= set(data["ticker"].unique())


def test_live_panel_dtypes_and_values(live_panel):
    data, _ = live_panel
    # The dtype that broke the earnings merge: date must be real datetimes.
    assert pd.api.types.is_datetime64_any_dtype(data["date"])
    assert set(data["is_drop"].unique()) <= {0, 1}
    assert not data[FEATURE_COLUMNS].isna().any().any()   # features fully populated
    # Decomposition identity holds where defined.
    d = data.dropna(subset=["systematic_ret"])
    assert ((d["systematic_ret"] + d["idio_ret"] - d["ret_1d"]).abs() < 1e-6).all()


def test_live_explanations_run_end_to_end(live_panel):
    """The full attribution path (factor + macro + earnings merge) must work on
    real data -- this is where the production 500 originated."""
    data, s = live_panel
    out = explain.explain_drops(data, s, worst_n=1)
    assert out["explanations"]
    for company in out["explanations"]:
        for event in company["events"]:
            assert "near_earnings" in event["earnings"]
            assert event["attribution"]["type"] in {
                "market/sector-driven", "stock-specific", "mixed", "unknown"}
