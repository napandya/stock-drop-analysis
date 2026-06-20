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


# --------------------------------------------------------------------------
# Opt-in "live" tests: hit real data sources to catch format/dtype drift that
# synthetic data can't. Skipped by default so the normal suite stays offline
# and deterministic; run with `pytest --run-live`.
# --------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="run tests marked @pytest.mark.live (require network).")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: exercises real data sources (needs network); opt-in via --run-live.")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip = pytest.mark.skip(reason="needs --run-live (network access)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
