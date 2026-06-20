"""Tests for ticker selection, per-company explanations and the POST API."""
from __future__ import annotations

import pytest

from app.config import (MAX_TICKERS, MIN_TICKERS, TICKER_CATALOG, Settings,
                        build_tickers)
from app.core.data_pipeline import get_modeling_dataset
from app.exceptions import ConfigurationError
from app.models import explain


# --- build_tickers ---------------------------------------------------------
def test_build_tickers_normalises_and_dedupes():
    out = build_tickers([" aapl ", "MSFT", "msft", "nvda"])
    assert list(out) == ["AAPL", "MSFT", "NVDA"]          # upper, order-preserving, deduped
    assert out["AAPL"] == "Technology"                    # sector from catalog
    assert out["NVDA"] == "Technology"


def test_build_tickers_unknown_symbol_gets_unknown_sector():
    out = build_tickers(["AAPL", "ZZZZ"])
    assert out["ZZZZ"] == "Unknown"


def test_build_tickers_enforces_bounds():
    with pytest.raises(ConfigurationError):
        build_tickers(["AAPL"])                           # below MIN_TICKERS
    with pytest.raises(ConfigurationError):
        build_tickers([f"T{i}" for i in range(MAX_TICKERS + 1)])


def test_catalog_shape():
    assert len(TICKER_CATALOG) >= MIN_TICKERS
    for row in TICKER_CATALOG:
        assert {"ticker", "name", "sector"} <= row.keys()


# --- explanations ----------------------------------------------------------
@pytest.fixture
def selection_dataset():
    s = Settings(use_synthetic=True, min_rows_required=50,
                 tickers={"AAA": "Technology", "BBB": "Financials", "CCC": "Industrials"})
    return get_modeling_dataset(s, use_cache=False), s


def test_explain_drops_structure(selection_dataset):
    data, s = selection_dataset
    out = explain.explain_drops(data, s, worst_n=2, top_features=4)
    assert out["title"] == "Why these stocks fell"
    assert {e["ticker"] for e in out["explanations"]} == set(s.tickers)
    assert out["global_importance"]

    for company in out["explanations"]:
        assert company["total_drops"] >= 0
        for event in company["events"]:
            assert event["return_pct"] < 0                # a drop is a negative return
            assert len(event["reasons"]) <= 4
            # Each event carries systematic/idiosyncratic attribution and macro context.
            assert event["attribution"]["type"] in {
                "market/sector-driven", "stock-specific", "mixed", "unknown"}
            assert "rate_chg_bp" in event["macro"] and "near_fomc" in event["macro"]
            assert "near_earnings" in event["earnings"]
            for r in event["reasons"]:
                assert r["contribution"] > 0              # only drop-ward reasons kept
                assert isinstance(r["explanation"], str) and r["explanation"]
