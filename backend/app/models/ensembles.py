"""Member 3 -- Tree ensembles and driver ranking.

Random Forest and XGBoost classify drop vs. no-drop; their averaged feature
importances give the project's core deliverable: a ranking of the drivers behind
sharp declines.
"""
from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score, roc_curve)
from xgboost import XGBClassifier

from app.config import Settings, get_settings
from app.core.features import FEATURE_COLUMNS
from app.core.validation import chrono_holdout, cv_summary
from app.exceptions import ModelError
from app.logging_config import get_logger
from app.models._plot import NAVY, fig_to_base64

logger = get_logger(__name__)


def run(data: pd.DataFrame, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        X, y = data[FEATURE_COLUMNS], data["is_drop"]
        # Chronological out-of-sample split so the ROC/ranking are not leaked.
        tr, te = chrono_holdout(data["date"])
        Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
        n_pos = max(int(ytr.sum()), 1)
        scale_pos_weight = (len(ytr) - n_pos) / n_pos

        models = {
            "Random Forest": RandomForestClassifier(
                n_estimators=300, max_depth=8, class_weight="balanced",
                random_state=settings.random_state, n_jobs=-1),
            "XGBoost": XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.9, colsample_bytree=0.9,
                scale_pos_weight=scale_pos_weight, eval_metric="logloss",
                random_state=settings.random_state),
        }
        rows, importances, roc_data = [], {}, {}
        for name, model in models.items():
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            proba = model.predict_proba(Xte)[:, 1]
            rows.append({"model": name,
                         "accuracy": float(accuracy_score(yte, pred)),
                         "F1": float(f1_score(yte, pred, zero_division=0)),
                         "ROC_AUC": float(roc_auc_score(yte, proba))})
            importances[name] = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS)
            roc_data[name] = roc_curve(yte, proba)

        imp = pd.DataFrame(importances)
        imp["mean"] = imp.mean(axis=1)
        imp = imp.sort_values("mean", ascending=False)
        ranking = [{"feature": f, "importance": float(v)}
                   for f, v in imp["mean"].items()]

        # Walk-forward stability of the Random Forest across time. A fold whose
        # test block has a single class is unusable for ROC-AUC, so skip it.
        def _fit_score(xa, ya, xb, yb):
            if ya.nunique() < 2 or yb.nunique() < 2:
                return None
            m = RandomForestClassifier(n_estimators=150, max_depth=8,
                                       class_weight="balanced",
                                       random_state=settings.random_state, n_jobs=-1)
            m.fit(xa, ya)
            proba = m.predict_proba(xb)[:, 1]
            return {"ROC_AUC": float(roc_auc_score(yb, proba)),
                    "F1": float(f1_score(yb, (proba >= 0.5).astype(int), zero_division=0))}

        validation = cv_summary(X, y, data["date"], _fit_score)
        validation["scheme"] = "chronological holdout (last 30%, 5-day embargo) + walk-forward CV"

        import matplotlib.pyplot as plt
        fig1, ax = plt.subplots(figsize=(8, 5))
        order = imp.sort_values("mean")
        ax.barh(order.index, order["mean"], color=NAVY)
        ax.set_xlabel("Mean feature importance (RF + XGBoost)")
        ax.set_title("Drivers Ranked by Association with Sharp Drops")

        fig2, ax2 = plt.subplots(figsize=(6, 5))
        for name, (fpr, tpr, _) in roc_data.items():
            auc = next(r["ROC_AUC"] for r in rows if r["model"] == name)
            ax2.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")
        ax2.plot([0, 1], [0, 1], "--", color="gray", lw=1)
        ax2.set_xlabel("False positive rate")
        ax2.set_ylabel("True positive rate")
        ax2.set_title("ROC Curves")
        ax2.legend()
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Ensemble modelling failed: {exc}") from exc

    logger.info("Member 3 ensembles complete.")
    return {
        "title": "Ensembles & Driver Ranking",
        "metrics": rows,
        "ranking": ranking,
        "validation": validation,
        "figures": {"feature_importance": fig_to_base64(fig1),
                    "roc": fig_to_base64(fig2)},
    }
