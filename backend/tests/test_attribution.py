"""Tests for factor decomposition (systematic vs idiosyncratic) and macro context."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.core import factors, macro_calendar
from app.core.data_pipeline import get_modeling_dataset
from app.services.analysis_service import dataset_summary


# --- factor decomposition --------------------------------------------------
def _toy_panel(n=200, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=n)
    mkt = rng.normal(0, 0.01, n)
    sec = 0.9 * mkt + rng.normal(0, 0.004, n)
    ret = 1.1 * mkt + 0.5 * sec + rng.normal(0, 0.008, n)
    ret[150] -= 0.20  # idiosyncratic crash
    return pd.DataFrame({"ticker": "X", "date": dates, "ret_1d": ret,
                         "market_ret": mkt, "sector_ret": sec})


def test_decomposition_is_exact_identity():
    out = factors.add_factor_decomposition(_toy_panel(), window=60)
    resid = (out["systematic_ret"] + out["idio_ret"] - out["ret_1d"]).abs()
    assert resid.max() < 1e-12          # idio is defined as ret - systematic
    assert out["systematic_ret"].iloc[:60].isna().all()   # no beta before window


def test_decomposition_recovers_factor_structure():
    """On a clean factor-built series, an ordinary day is mostly systematic and
    the injected crash is mostly idiosyncratic."""
    out = factors.add_factor_decomposition(_toy_panel(), window=60).reset_index(drop=True)
    crash = out.loc[150]
    assert crash["idio_ret"] < crash["systematic_ret"]    # crash dominated by idio
    assert factors.drop_attribution(crash["systematic_ret"], crash["ret_1d"])["type"] \
        == "stock-specific"


def test_drop_attribution_classification():
    assert factors.drop_attribution(-0.04, -0.05)["type"] == "market/sector-driven"
    assert factors.drop_attribution(-0.005, -0.05)["type"] == "stock-specific"
    assert factors.drop_attribution(-0.02, -0.05)["type"] == "mixed"
    # Not a drop / missing data -> unknown, no shares.
    assert factors.drop_attribution(float("nan"), -0.05)["type"] == "unknown"
    assert factors.drop_attribution(-0.01, 0.02)["type"] == "unknown"


def test_sector_etfs_for():
    etfs = factors.sector_etfs_for(["Technology", "Financials", "Unknown", "Technology"])
    assert etfs == ["XLK", "XLF"]      # mapped, deduped; Unknown dropped


# --- macro calendar --------------------------------------------------------
def test_add_macro_context_rate_change_and_fomc():
    df = pd.DataFrame({
        "ticker": ["X", "X", "Y", "Y"],
        "date": pd.to_datetime(["2022-03-16", "2022-03-17", "2022-03-16", "2022-03-17"]),
        "treasury_10y": [2.0, 2.15, 2.0, 2.15],
    })
    out = macro_calendar.add_macro_context(df)
    # 0.15 percentage-point jump = 15 bp.
    mar17 = out[out["date"] == "2022-03-17"]["rate_chg_bp"].iloc[0]
    assert round(mar17, 1) == 15.0
    # 2022-03-16 is a scheduled FOMC date.
    assert out[out["date"] == "2022-03-16"]["near_fomc"].all()


# --- end-to-end on the panel ----------------------------------------------
@pytest.fixture
def panel():
    s = Settings(use_synthetic=True, min_rows_required=50,
                 tickers={"AAA": "Technology", "BBB": "Financials"})
    return get_modeling_dataset(s, use_cache=False), s


def test_panel_has_attribution_columns(panel):
    data, _ = panel
    for col in ["sector_ret", "systematic_ret", "idio_ret", "idio_z",
                "rate_chg_bp", "near_fomc"]:
        assert col in data.columns
    # Decomposition identity holds across the whole panel where defined.
    defined = data.dropna(subset=["systematic_ret"])
    resid = (defined["systematic_ret"] + defined["idio_ret"] - defined["ret_1d"]).abs()
    assert resid.max() < 1e-9


def test_dataset_summary_reports_attribution_mix(panel):
    data, s = panel
    mix = dataset_summary(data, s)["drop_attribution"]
    assert set(mix) >= {"market/sector-driven", "stock-specific", "mixed"}
    assert sum(mix.values()) == int(data["is_drop"].sum())
