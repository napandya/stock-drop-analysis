"""Shared pytest fixtures.

All tests run against synthetic data so the suite is fast, deterministic and
needs no network access.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.core.data_pipeline import clear_cache, get_modeling_dataset


@pytest.fixture
def settings() -> Settings:
    """Settings forced into offline synthetic mode for tests."""
    return Settings(use_synthetic=True, min_rows_required=50)


@pytest.fixture(autouse=True)
def _clear_dataset_cache():
    """Ensure the dataset cache never leaks between tests."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def dataset(settings):
    return get_modeling_dataset(settings)
