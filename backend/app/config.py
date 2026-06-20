"""Application configuration.

Settings are defined with ``pydantic-settings`` so they can be overridden by
environment variables (e.g. ``DROP_THRESHOLD=-0.07``) without editing code, which
keeps the analysis reproducible and twelve-factor friendly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_ROOT = BASE_DIR.parent                              # stock_drops_app/


class Settings(BaseSettings):
    """Strongly-typed, validated application settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # -- Case-study universe -------------------------------------------------
    tickers: dict[str, str] = Field(
        default_factory=lambda: {
            "META": "Communication Services",
            "NFLX": "Communication Services",
            "SNAP": "Communication Services",
            "NVDA": "Technology",
            "BA": "Industrials",
            "BAC": "Financials",
        }
    )
    market_index: str = "^GSPC"
    vix_index: str = "^VIX"

    # -- Study window --------------------------------------------------------
    date_start: str = "2021-01-01"
    date_end: str = "2024-12-31"

    # -- Drop definition -----------------------------------------------------
    drop_method: Literal["fixed", "percentile"] = "fixed"
    drop_threshold: float = -0.05
    drop_percentile: float = 1.0

    # -- Macro (FRED) --------------------------------------------------------
    fred_series: dict[str, str] = Field(
        default_factory=lambda: {"DGS10": "treasury_10y", "CPIAUCSL": "cpi"}
    )

    # -- Resiliency ----------------------------------------------------------
    fetch_max_attempts: int = 4         # retries for transient data-source errors
    fetch_backoff_seconds: float = 1.5  # exponential backoff base
    fetch_timeout_seconds: float = 30.0

    # -- Data / behaviour ----------------------------------------------------
    use_synthetic: bool = False         # True => offline, illustrative data only
    random_state: int = 42
    min_rows_required: int = 100        # guard against silently-empty datasets

    # -- Paths ---------------------------------------------------------------
    data_dir: Path = BASE_DIR / "data"
    sentiment_csv_name: str = "all-data.csv"

    @property
    def sentiment_csv(self) -> Path:
        return self.data_dir / self.sentiment_csv_name

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the settings."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
