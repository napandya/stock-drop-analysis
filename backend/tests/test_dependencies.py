"""Environment / dependency smoke tests.

These catch the class of failures that only show up at runtime when the venv is
built on a new Python with mismatched package versions -- exactly the errors that
turned ``/api/analyze`` into a 503:

* ``No module named 'distutils'`` -- distutils was removed from the stdlib in
  Python 3.12; ``setuptools`` must be installed to provide the shim.
* ``pandas-datareader`` being import-incompatible with the installed ``pandas``.
* ``yfinance`` / ``requests`` failing to import against the installed stack.

They are pure imports: no network, fast, deterministic. If any dependency in the
runtime path is missing or binary-incompatible, these fail in CI instead of in
front of a user.
"""
from __future__ import annotations

import importlib

import pytest

#: Every third-party module the *running* application imports (directly or via a
#: lazy ``import`` inside a function). Keep this in lock-step with the codebase.
RUNTIME_IMPORTS = [
    "fastapi",
    "pydantic",
    "pydantic_settings",
    "pandas",
    "numpy",
    "sklearn",
    "xgboost",
    "matplotlib",
    "seaborn",
    "tenacity",
    "yfinance",
    "requests",
    "vaderSentiment.vaderSentiment",
]


@pytest.mark.parametrize("module", RUNTIME_IMPORTS)
def test_runtime_dependency_importable(module: str):
    """Each runtime dependency imports cleanly against the installed stack."""
    importlib.import_module(module)


def test_distutils_available():
    """``distutils`` must resolve (stdlib pre-3.12, setuptools shim on 3.12+).

    yfinance and other libraries still ``import distutils``; without it the data
    fetch raises ``ModuleNotFoundError`` and the API returns 503.
    """
    importlib.import_module("distutils")
    importlib.import_module("distutils.version")


def test_data_pipeline_loaders_import():
    """The lazily-imported data loaders resolve without touching the network.

    ``_load_prices`` / ``_load_macro`` import their heavy deps at call time, so a
    broken dependency would otherwise stay hidden until a live request. Importing
    the module and its lazy deps surfaces the problem in the test run instead.
    """
    from app.core import data_pipeline

    assert hasattr(data_pipeline, "_load_prices")
    assert hasattr(data_pipeline, "_load_macro")
    # The deps these functions import lazily must be present.
    importlib.import_module("yfinance")
    importlib.import_module("requests")
