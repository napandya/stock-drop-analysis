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


def test_macro_fetch_failure_raises_datasource_error(monkeypatch):
    """A persistently failing macro loader also surfaces a typed error (so the
    FRED path is covered, not just prices)."""
    s = Settings(use_synthetic=False, fetch_max_attempts=2, fetch_backoff_seconds=0.01)

    monkeypatch.setattr(data_pipeline, "_load_prices", lambda _s: pd.DataFrame())

    def _boom(_settings):
        raise TimeoutError("FRED unreachable")

    monkeypatch.setattr(data_pipeline, "_load_macro", _boom)
    data_pipeline.clear_cache()
    with pytest.raises(DataSourceError):
        data_pipeline.get_modeling_dataset(s, use_cache=False)


# --- FRED CSV parsing (no network) ----------------------------------------
# A representative monthly fredgraph.csv payload, including FRED's "." marker
# for a missing daily observation that falls on a non-trading day.
_FRED_SAMPLE = (
    "observation_date,DGS10,CPIAUCSL\n"
    "2021-01-01,.,261.582\n"
    "2021-02-01,1.16,263.014\n"
    "2022-01-01,1.78,281.933\n"
    "2022-02-01,1.93,284.182\n"
)


def test_parse_fred_csv_basic():
    s = Settings()
    macro = data_pipeline._parse_fred_csv(_FRED_SAMPLE, s)
    assert list(macro.columns) == ["date", "treasury_10y", "cpi_yoy"]
    assert pd.api.types.is_datetime64_any_dtype(macro["date"])
    # The "." missing value must be coerced to NaN then forward-filled, never
    # left as the literal string that broke arithmetic downstream.
    assert macro["treasury_10y"].dtype.kind == "f"
    # 12-month CPI change is computed (NaN for the first year is expected).
    assert "cpi_yoy" in macro.columns


def test_parse_fred_csv_accepts_legacy_date_column():
    """FRED has historically used both 'DATE' and 'observation_date'."""
    s = Settings()
    legacy = _FRED_SAMPLE.replace("observation_date", "DATE")
    macro = data_pipeline._parse_fred_csv(legacy, s)
    assert "date" in macro.columns


def test_parse_fred_csv_missing_series_raises():
    """A response missing a requested series is a hard error, not silent NaNs."""
    s = Settings()
    bad = "observation_date,DGS10\n2021-02-01,1.16\n"  # CPIAUCSL absent
    with pytest.raises(ValueError):
        data_pipeline._parse_fred_csv(bad, s)


def test_parse_fred_csv_rejects_html_with_clear_error():
    """An HTML error/rate-limit page must raise an actionable ValueError, not a
    cryptic pandas 'Error tokenizing data'."""
    s = Settings()
    html = "<!DOCTYPE html>\n<html><body><p>Service unavailable</p></body></html>\n"
    with pytest.raises(ValueError, match="did not return CSV"):
        data_pipeline._parse_fred_csv(html, s)


def test_read_fred_csv_single_series():
    """Per-series payloads (how _load_macro now fetches) parse to date + code."""
    single = "observation_date,DGS10\n2021-02-01,1.16\n2021-02-02,1.13\n"
    frame = data_pipeline._read_fred_csv(single)
    assert list(frame.columns) == ["date", "DGS10"]
    assert pd.api.types.is_datetime64_any_dtype(frame["date"])


def test_cpi_yoy_computed_on_monthly_observations():
    """CPI year-over-year must reflect a 12-*month* change, not 12 daily rows.

    Build 13 monthly CPI points growing 0.5%/month alongside a daily-cadence
    treasury column; the 13th month's YoY should be a real, non-NaN value.
    """
    s = Settings()
    rows = ["observation_date,DGS10,CPIAUCSL"]
    cpi = 100.0
    for i in range(13):  # 2021-01 .. 2022-01
        year = 2021 + (i // 12)
        month = (i % 12) + 1
        rows.append(f"{year}-{month:02d}-01,1.50,{cpi:.3f}")
        cpi *= 1.005
    macro = data_pipeline._parse_fred_csv("\n".join(rows) + "\n", s)

    last = macro.iloc[-1]["cpi_yoy"]
    assert pd.notna(last)
    # 12 months of +0.5% compounding ≈ 6.17% YoY.
    assert 5.5 < last < 7.0
