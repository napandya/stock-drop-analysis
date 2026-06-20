"""Unit tests for feature engineering and drop labelling."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.core.features import FEATURE_COLUMNS, build_features, label_drops
from app.exceptions import InsufficientDataError


def test_label_drops_fixed_threshold():
    s = Settings(drop_method="fixed", drop_threshold=-0.05)
    returns = pd.Series([-0.10, -0.05, -0.02, 0.03])
    flags = label_drops(returns, s)
    assert flags.tolist() == [True, True, False, False]


def test_label_drops_percentile():
    s = Settings(drop_method="percentile", drop_percentile=25.0)
    returns = pd.Series([-0.10, -0.04, 0.0, 0.05])
    flags = label_drops(returns, s)
    assert flags.iloc[0]            # the worst day is below the 25th percentile
    assert not flags.iloc[-1]


def test_label_drops_empty_percentile_raises():
    s = Settings(drop_method="percentile")
    with pytest.raises(InsufficientDataError):
        label_drops(pd.Series([np.nan, np.nan]), s)


def test_no_leakage_ret_1d_excluded():
    # The same-day return must never appear among the predictors.
    assert "ret_1d" not in FEATURE_COLUMNS


def test_build_features_too_small_raises():
    s = Settings(min_rows_required=10_000, use_synthetic=True)
    # Build a tiny price frame that cannot meet the row requirement.
    dates = pd.bdate_range("2022-01-01", periods=30)
    prices = pd.DataFrame({
        "date": list(dates) * 1, "ticker": "AAA", "sector": "Tech",
        "close": np.linspace(100, 110, 30), "volume": 1e6,
        "market_close": np.linspace(4000, 4100, 30),
        "vix_close": np.linspace(20, 22, 30),
    })
    macro = pd.DataFrame({"date": dates, "treasury_10y": 2.5, "cpi_yoy": 3.0})
    with pytest.raises(InsufficientDataError):
        build_features(prices, macro, s)
