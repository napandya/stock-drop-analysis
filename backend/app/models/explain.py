"""Per-company drop explanations.

Answers the question "why did *this* stock fall?" for each selected ticker.
For a stock's worst drop day we score every driver by

    contribution = model_importance(feature) x directed_abnormality(feature)

where *model_importance* comes from a Random Forest trained on the selected
panel, and *directed_abnormality* is how many standard deviations the feature
sat from its normal level **in the direction associated with drops** (so a
calm-VIX day is not credited as a reason for a crash). The top features become
plain-language reasons. This is deliberately dependency-free and stays tied to
the same model family used for the driver ranking -- no SHAP required.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from app.config import Settings, get_settings
from app.core.features import FEATURE_COLUMNS
from app.exceptions import ModelError
from app.logging_config import get_logger

logger = get_logger(__name__)

#: Human phrasing for (feature, direction) pairs. ``direction`` is the sign of
#: the day's z-score: -1 = far below normal, +1 = far above normal.
_PHRASES: dict[str, dict[int, str]] = {
    "market_ret":     {-1: "the broad market sold off sharply", 1: "moved against an up market"},
    "vix":            {1: "market fear (VIX) was elevated", -1: "volatility was unusually low"},
    "vix_change":     {1: "volatility spiked that day", -1: "volatility eased"},
    "volume_z":       {1: "trading volume was abnormally high", -1: "trading volume was unusually thin"},
    "volatility_20d": {1: "the stock had been highly volatile recently", -1: "recent volatility was low"},
    "ret_prev":       {-1: "it had already fallen the prior day", 1: "it had risen the prior day"},
    "momentum_5d":    {-1: "5-day momentum was weak/negative", 1: "5-day momentum was strong"},
    "treasury_10y":   {1: "10-year Treasury yields were high", -1: "10-year yields were low"},
    "cpi_yoy":        {1: "inflation (CPI YoY) was elevated", -1: "inflation was low"},
}


def _phrase(feature: str, z: float) -> str:
    direction = 1 if z >= 0 else -1
    return _PHRASES.get(feature, {}).get(direction, f"{feature.replace('_', ' ')} was abnormal")


def explain_drops(data: pd.DataFrame, settings: Settings | None = None,
                  worst_n: int = 2, top_features: int = 4) -> dict:
    """Return per-ticker explanations for each stock's worst drop event(s)."""
    settings = settings or get_settings()
    try:
        X, y = data[FEATURE_COLUMNS], data["is_drop"]
        rf = RandomForestClassifier(
            n_estimators=200, max_depth=8, class_weight="balanced",
            random_state=settings.random_state, n_jobs=-1).fit(X, y)
        importance = pd.Series(rf.feature_importances_, index=FEATURE_COLUMNS)

        # Standardisation baseline and the drop-associated direction per feature.
        mu = X.mean()
        sigma = X.std(ddof=0).replace(0, np.nan)
        # Sign of correlation with is_drop: which way does a feature lean on drops?
        drop_dir = X.apply(lambda c: np.sign(np.corrcoef(c, y)[0, 1]) or 1.0)

        explanations = []
        for tkr in sorted(data["ticker"].unique()):
            events = data[(data["ticker"] == tkr) & (data["is_drop"] == 1)]
            worst = events.nsmallest(worst_n, "ret_1d")
            ev_out = []
            for _, row in worst.iterrows():
                z = (row[FEATURE_COLUMNS] - mu) / sigma
                directed = (z * drop_dir).clip(lower=0)        # only drop-ward abnormality
                score = (importance * directed).sort_values(ascending=False)
                reasons = [
                    {
                        "feature": feat,
                        "z_score": round(float(z[feat]), 2),
                        "importance": round(float(importance[feat]), 4),
                        "contribution": round(float(score[feat]), 4),
                        "explanation": _phrase(feat, float(z[feat])),
                    }
                    for feat in score.index[:top_features] if score[feat] > 0
                ]
                ev_out.append({
                    "date": pd.Timestamp(row["date"]).date().isoformat(),
                    "return_pct": round(float(row["ret_1d"]) * 100, 2),
                    "reasons": reasons,
                })
            explanations.append({
                "ticker": tkr,
                "sector": settings.tickers.get(tkr, "Unknown"),
                "total_drops": int(len(events)),
                "events": ev_out,
            })
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Explanation step failed: {exc}") from exc

    logger.info("Per-company explanations built for %d tickers.", len(explanations))
    return {
        "title": "Why these stocks fell",
        "explanations": explanations,
        "global_importance": [
            {"feature": f, "importance": round(float(v), 4)}
            for f, v in importance.sort_values(ascending=False).items()
        ],
    }
