"""Service layer.

Thin orchestration between the API and the model modules. Keeps the route
handlers trivial and gives one place to assemble dataset summaries.
"""
from __future__ import annotations

import pandas as pd

from app.config import Settings, build_tickers, get_settings
from app.core.data_pipeline import get_modeling_dataset
from app.exceptions import InsufficientDataError, ModelError
from app.logging_config import get_logger
from app.models import classification, clustering, ensembles, explain, regression

logger = get_logger(__name__)

#: section key -> (human title, module)
SECTIONS = {
    "regression": ("Member 1 -- Regression", regression),
    "classification": ("Member 2 -- Classification & Sentiment", classification),
    "ensembles": ("Member 3 -- Ensembles & Driver Ranking", ensembles),
    "clustering": ("Member 4 -- Clustering", clustering),
}


def dataset_summary(data: pd.DataFrame, settings: Settings) -> dict:
    n_drops = int(data["is_drop"].sum())
    return {
        "rows": int(len(data)),
        "tickers": sorted(data["ticker"].unique().tolist()),
        "date_start": str(data["date"].min().date()),
        "date_end": str(data["date"].max().date()),
        "drop_events": n_drops,
        "drop_rate": round(n_drops / len(data), 4),
        "synthetic": settings.use_synthetic,
    }


def run_section(section: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if section not in SECTIONS:
        raise KeyError(section)
    _, module = SECTIONS[section]
    data = get_modeling_dataset(settings)
    result = module.run(data, settings)
    result["dataset"] = dataset_summary(data, settings)
    return result


def _run_sections(data: pd.DataFrame, settings: Settings) -> dict:
    """Run every section, but degrade gracefully: a section that can't run on
    this particular selection (e.g. clustering with too few drops) becomes a
    titled placeholder with a warning instead of failing the whole request."""
    sections = {}
    for key, (title, module) in SECTIONS.items():
        try:
            sections[key] = module.run(data, settings)
        except (InsufficientDataError, ModelError) as exc:
            logger.warning("Section '%s' skipped: %s", key, exc)
            sections[key] = {"title": title, "metrics": [], "warnings": [str(exc)]}
    return sections


def run_all(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    data = get_modeling_dataset(settings)
    return {"dataset": dataset_summary(data, settings),
            "sections": _run_sections(data, settings)}


def run_selection(tickers: list[str], settings: Settings | None = None) -> dict:
    """Run the full pipeline on a user-chosen set of tickers and add
    per-company explanations of why each fell."""
    base = settings or get_settings()
    custom = base.model_copy(update={"tickers": build_tickers(tickers)})
    data = get_modeling_dataset(custom)
    return {
        "dataset": dataset_summary(data, custom),
        "sections": _run_sections(data, custom),
        "explanations": explain.explain_drops(data, custom),
    }
