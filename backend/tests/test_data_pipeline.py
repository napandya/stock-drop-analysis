"""Tests for the data pipeline, caching and resiliency behaviour."""
from __future__ import annotations

import pandas as pd
import pytest

from app.config import Settings
from app.core import data_pipeline
from app.core.features import FEATURE_COLUMNS
from app.exceptions import DataSourceError


def test_synthetic_dataset_shape(dataset):
    assert isinstance(dataset, pd.DataFrame)
    assert not dataset.empty
    for col in FEATURE_COLUMNS + ["is_drop", "ret_1d", "ticker", "date"]:
        assert col in dataset.columns
    assert set(dataset["is_drop"].unique()) <= {0, 1}


def test_dataset_is_cached(settings):
    data_pipeline.clear_cache()
    first = data_pipeline.get_modeling_dataset(settings)
    # Mutating the returned copy must not affect the cached frame.
    first.loc[0, "ret_1d"] = 999
    second = data_pipeline.get_modeling_dataset(settings)
    assert second.loc[0, "ret_1d"] != 999


def test_no_nans_in_features(dataset):
    assert not dataset[FEATURE_COLUMNS].isna().any().any()


def test_real_fetch_failure_raises_datasource_error(monkeypatch):
    """If the price loader keeps failing, the pipeline surfaces a typed
    DataSourceError rather than a raw network exception."""
    s = Settings(use_synthetic=False, fetch_max_attempts=2, fetch_backoff_seconds=0.01)

    def _boom(_settings):
        raise ConnectionError("simulated network outage")

    monkeypatch.setattr(data_pipeline, "_load_prices", _boom)
    data_pipeline.clear_cache()
    with pytest.raises(DataSourceError):
        data_pipeline.get_modeling_dataset(s, use_cache=False)
