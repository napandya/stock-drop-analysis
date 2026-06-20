"""Domain-specific exceptions.

A small, explicit hierarchy makes error handling intentional: the API layer can
map each type to the right HTTP status, and callers can catch precisely what they
mean to handle instead of bare ``Exception``.
"""
from __future__ import annotations


class StockDropsError(Exception):
    """Base class for all application errors."""


class ConfigurationError(StockDropsError):
    """Raised when settings are invalid or inconsistent."""


class DataSourceError(StockDropsError):
    """Raised when an external data source (yfinance, FRED) cannot be reached
    or returns unusable data after all retries."""


class InsufficientDataError(StockDropsError):
    """Raised when a dataset is too small or empty to model reliably."""


class ModelError(StockDropsError):
    """Raised when a model fails to fit or score."""
