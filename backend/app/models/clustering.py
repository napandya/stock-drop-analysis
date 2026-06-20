"""Member 4 -- Unsupervised analysis.

K-Means clusters the drop events into types (chosen by silhouette), and an
Isolation Forest flags anomalous days without using the drop label.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.config import Settings, get_settings
from app.core.features import FEATURE_COLUMNS
from app.exceptions import InsufficientDataError, ModelError
from app.logging_config import get_logger
from app.models._plot import DECLINE, NAVY, fig_to_base64

logger = get_logger(__name__)


def run(data: pd.DataFrame, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        drops = data[data["is_drop"] == 1].copy()
        if len(drops) < 10:
            raise InsufficientDataError(
                f"Only {len(drops)} drop events; need >=10 to cluster. "
                "Loosen the drop threshold or widen the window.")
        Xd = StandardScaler().fit_transform(drops[FEATURE_COLUMNS])

        ks = range(2, 8)
        inertias, sils = [], []
        for k in ks:
            km = KMeans(n_clusters=k, n_init=10, random_state=settings.random_state)
            labels = km.fit_predict(Xd)
            inertias.append(float(km.inertia_))
            sils.append(float(silhouette_score(Xd, labels)))
        best_k = list(ks)[int(np.argmax(sils))]

        km = KMeans(n_clusters=best_k, n_init=10, random_state=settings.random_state)
        drops["cluster"] = km.fit_predict(Xd)
        profile = drops.groupby("cluster")[FEATURE_COLUMNS + ["ret_1d"]].mean()
        profile["n_events"] = drops.groupby("cluster").size()
        profiles = profile.round(4).reset_index().to_dict(orient="records")

        coords = PCA(n_components=2, random_state=settings.random_state).fit_transform(Xd)

        import matplotlib.pyplot as plt
        fig1, ax1 = plt.subplots(figsize=(7, 4))
        ax1.plot(list(ks), inertias, "o-", color=NAVY, label="inertia")
        ax1.set_xlabel("Number of clusters (k)")
        ax1.set_ylabel("Inertia", color=NAVY)
        ax2 = ax1.twinx()
        ax2.plot(list(ks), sils, "s--", color=DECLINE, label="silhouette")
        ax2.set_ylabel("Silhouette score", color=DECLINE)
        ax1.set_title("Elbow & Silhouette for K-Means")

        fig2, ax = plt.subplots(figsize=(7, 5))
        sc = ax.scatter(coords[:, 0], coords[:, 1], c=drops["cluster"],
                        cmap="viridis", s=25, alpha=0.7)
        ax.set_xlabel("PCA component 1")
        ax.set_ylabel("PCA component 2")
        ax.set_title(f"Drop-Event Clusters (k={best_k})")
        fig2.colorbar(sc, ax=ax, label="cluster")

        # Isolation Forest anomaly detection on the full panel.
        Xall = StandardScaler().fit_transform(data[FEATURE_COLUMNS])
        iso = IsolationForest(contamination=0.03, random_state=settings.random_state)
        anomaly = (iso.fit_predict(Xall) == -1)
        total_drops = int(data["is_drop"].sum())
        caught = int((anomaly & (data["is_drop"] == 1)).sum())
        anomaly_summary = {
            "anomalies_flagged": int(anomaly.sum()),
            "drops_recovered": caught,
            "recall_of_drops": round(caught / max(total_drops, 1), 3),
        }
    except InsufficientDataError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Clustering failed: {exc}") from exc

    logger.info("Member 4 clustering complete (k=%d).", best_k)
    return {
        "title": "Clustering & Anomaly Detection",
        "best_k": best_k,
        "cluster_profiles": profiles,
        "anomaly_detection": anomaly_summary,
        "figures": {"elbow": fig_to_base64(fig1), "clusters": fig_to_base64(fig2)},
    }
