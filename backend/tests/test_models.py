"""Tests that each model module returns a well-formed result on synthetic data."""
from __future__ import annotations

import pytest

from app.models import classification, clustering, ensembles, regression


def _assert_base64_png(s: str):
    assert isinstance(s, str) and len(s) > 100   # non-trivial payload


def _assert_walk_forward(out):
    """Every supervised section reports a time-series validation block."""
    v = out["validation"]
    assert "walk-forward" in v["scheme"] and v["embargo_days"] >= 1
    assert v["n_folds"] >= 1
    for entry in v["cv"]:
        assert {"metric", "mean", "std"} <= entry.keys()


def test_regression_result(dataset, settings):
    out = regression.run(dataset, settings)
    assert {"title", "metrics", "figures", "validation"} <= out.keys()
    assert any(m["model"].startswith("Multiple") for m in out["metrics"])
    for m in out["metrics"]:
        assert {"R2", "MAE", "RMSE"} <= m.keys()
    _assert_walk_forward(out)
    _assert_base64_png(out["figures"]["pred_vs_actual"])


def test_classification_result(dataset, settings):
    out = classification.run(dataset, settings)
    assert "figures" in out and "drop_confusion" in out["figures"]
    _assert_walk_forward(out)
    # Fallback sentiment sample is active in tests -> a warning is expected.
    assert out["warnings"]


def test_ensembles_ranking(dataset, settings):
    out = ensembles.run(dataset, settings)
    assert out["ranking"], "expected a non-empty driver ranking"
    importances = [r["importance"] for r in out["ranking"]]
    assert importances == sorted(importances, reverse=True)   # ranked descending
    for m in out["metrics"]:
        assert 0.0 <= m["ROC_AUC"] <= 1.0
    _assert_walk_forward(out)


def test_clustering_result(dataset, settings):
    out = clustering.run(dataset, settings)
    assert out["best_k"] >= 2
    assert out["cluster_profiles"]
    assert 0.0 <= out["anomaly_detection"]["recall_of_drops"] <= 1.0
