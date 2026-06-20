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

from app.exceptions import ConfigurationError

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_ROOT = BASE_DIR.parent                              # stock_drops_app/

#: FinancialPhraseBank agreement level -> "sentence@sentiment" file shipped with
#: the dataset. Higher agreement = less label noise.
SENTIMENT_AGREEMENT_FILES = {
    "all": "Sentences_AllAgree.txt",
    "75": "Sentences_75Agree.txt",
    "66": "Sentences_66Agree.txt",
    "50": "Sentences_50Agree.txt",
}

#: Curated universe offered in the frontend picker. Users may also add any other
#: Yahoo Finance symbol; those get the "Unknown" sector (sector is metadata only,
#: never a model feature).
TICKER_CATALOG: list[dict[str, str]] = [
    {"ticker": "AAPL", "name": "Apple", "sector": "Technology"},
    {"ticker": "MSFT", "name": "Microsoft", "sector": "Technology"},
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "Technology"},
    {"ticker": "AMD", "name": "AMD", "sector": "Technology"},
    {"ticker": "INTC", "name": "Intel", "sector": "Technology"},
    {"ticker": "META", "name": "Meta Platforms", "sector": "Communication Services"},
    {"ticker": "GOOGL", "name": "Alphabet", "sector": "Communication Services"},
    {"ticker": "NFLX", "name": "Netflix", "sector": "Communication Services"},
    {"ticker": "SNAP", "name": "Snap", "sector": "Communication Services"},
    {"ticker": "DIS", "name": "Walt Disney", "sector": "Communication Services"},
    {"ticker": "AMZN", "name": "Amazon", "sector": "Consumer Discretionary"},
    {"ticker": "TSLA", "name": "Tesla", "sector": "Consumer Discretionary"},
    {"ticker": "NKE", "name": "Nike", "sector": "Consumer Discretionary"},
    {"ticker": "F", "name": "Ford", "sector": "Consumer Discretionary"},
    {"ticker": "BA", "name": "Boeing", "sector": "Industrials"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financials"},
    {"ticker": "BAC", "name": "Bank of America", "sector": "Financials"},
    {"ticker": "PYPL", "name": "PayPal", "sector": "Financials"},
    {"ticker": "COIN", "name": "Coinbase", "sector": "Financials"},
    {"ticker": "UBER", "name": "Uber", "sector": "Industrials"},
]

_CATALOG_SECTORS = {row["ticker"]: row["sector"] for row in TICKER_CATALOG}

#: Bounds on a user selection: enough stocks for the pooled models to be
#: meaningful, few enough to keep a request responsive.
MIN_TICKERS = 2
MAX_TICKERS = 8


def build_tickers(symbols: list[str]) -> dict[str, str]:
    """Normalise a user-supplied symbol list into a ``{ticker: sector}`` dict.

    Upper-cases, strips, de-duplicates (order-preserving) and validates the
    count. Sector comes from the catalog or defaults to ``"Unknown"``.
    """
    seen: dict[str, str] = {}
    for raw in symbols or []:
        sym = str(raw).strip().upper()
        if sym and sym not in seen:
            seen[sym] = _CATALOG_SECTORS.get(sym, "Unknown")
    if len(seen) < MIN_TICKERS:
        raise ConfigurationError(f"Select at least {MIN_TICKERS} tickers.")
    if len(seen) > MAX_TICKERS:
        raise ConfigurationError(f"Select at most {MAX_TICKERS} tickers.")
    return seen


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
    date_start: str = "2015-01-01"      # ~10y: more regimes, folds and earnings
    date_end: str = "2024-12-31"

    # -- Drop definition -----------------------------------------------------
    drop_method: Literal["fixed", "percentile"] = "fixed"
    drop_threshold: float = -0.05
    drop_percentile: float = 1.0

    # -- Macro (FRED) --------------------------------------------------------
    fred_series: dict[str, str] = Field(
        default_factory=lambda: {"DGS10": "treasury_10y", "CPIAUCSL": "cpi"}
    )

    # -- Attribution ---------------------------------------------------------
    factor_window: int = 60          # trailing days for rolling market/sector betas
    earnings_history_limit: int = 60  # quarters of earnings to request per ticker
    earnings_event_window: int = 4    # calendar days around an earnings date to tag

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
    #: Default sentiment CSV filename (the Kaggle download is "all-data.csv";
    #: this repo ships "FinancialPhraseBank.csv"). Override via env if needed.
    sentiment_csv_name: str = "FinancialPhraseBank.csv"
    #: Which FinancialPhraseBank annotator-agreement subset to train on. Higher
    #: agreement = cleaner labels (and the levels the source paper benchmarks):
    #: "all" (100%), "75", "66", "50", or "csv" to use the comma-separated file.
    sentiment_agreement: Literal["all", "75", "66", "50", "csv"] = "75"

    @property
    def sentiment_csv(self) -> Path:
        """Resolve the sentiment dataset: the chosen agreement file if present,
        otherwise the CSV (by known names), otherwise the default path."""
        candidates: list[str] = []
        if self.sentiment_agreement in SENTIMENT_AGREEMENT_FILES:
            candidates.append(SENTIMENT_AGREEMENT_FILES[self.sentiment_agreement])
        candidates += [self.sentiment_csv_name, "FinancialPhraseBank.csv", "all-data.csv"]
        for name in dict.fromkeys(candidates):
            path = self.data_dir / name
            if path.exists():
                return path
        return self.data_dir / self.sentiment_csv_name

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the settings."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
