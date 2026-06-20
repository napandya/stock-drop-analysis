"""Member 1 -- Regression of drop magnitude.

Linear, Multiple and Decision Tree regression of the daily return, evaluated
with R-squared, MAE and RMSE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor

from app.config import Settings, get_settings
from app.core.features import FEATURE_COLUMNS
from app.core.validation import chrono_holdout, cv_summary
from app.exceptions import ModelError
from app.logging_config import get_logger
from app.models._plot import DECLINE, NAVY, fig_to_base64

logger = get_logger(__name__)


def _metrics(name: str, y_true, y_pred) -> dict:
    return {
        "model": name,
        "R2": float(r2_score(y_true, y_pred)),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


def run(data: pd.DataFrame, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        X, y = data[FEATURE_COLUMNS], data["ret_1d"]
        # Chronological out-of-sample split (no look-ahead) instead of a random one.
        tr, te = chrono_holdout(data["date"])
        Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]

        rows = []
        lin1 = LinearRegression().fit(Xtr[["market_ret"]], ytr)
        rows.append(_metrics("Simple Linear (market_ret)", yte,
                             lin1.predict(Xte[["market_ret"]])))
        linm = LinearRegression().fit(Xtr, ytr)
        pm = linm.predict(Xte)
        rows.append(_metrics("Multiple Linear (all drivers)", yte, pm))
        tree = DecisionTreeRegressor(max_depth=5, random_state=settings.random_state)
        tree.fit(Xtr, ytr)
        rows.append(_metrics("Decision Tree (depth=5)", yte, tree.predict(Xte)))

        # Walk-forward stability of the multiple-linear model across time.
        def _fit_score(xa, ya, xb, yb):
            p = LinearRegression().fit(xa, ya).predict(xb)
            return {"R2": float(r2_score(yb, p)),
                    "RMSE": float(np.sqrt(mean_squared_error(yb, p)))}

        validation = cv_summary(X, y, data["date"], _fit_score)
        validation["scheme"] = "chronological holdout (last 30%, 5-day embargo) + walk-forward CV"

        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(yte, pm, s=10, alpha=0.4, color=NAVY)
        lims = [min(yte.min(), pm.min()), max(yte.max(), pm.max())]
        ax.plot(lims, lims, "--", color=DECLINE, lw=1.2, label="perfect fit")
        ax.set_xlabel("Actual daily return")
        ax.set_ylabel("Predicted daily return")
        ax.set_title("Multiple Linear Regression: Predicted vs. Actual")
        ax.legend()
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Regression failed: {exc}") from exc

    logger.info("Member 1 regression complete.")
    return {
        "title": "Regression -- Drop Magnitude",
        "metrics": rows,
        "validation": validation,
        "figures": {"pred_vs_actual": fig_to_base64(fig)},
    }
