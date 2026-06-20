"""Tests for time-aware (purged, walk-forward) validation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core import validation


def _panel_dates(n_days=120, tickers=3):
    """A pooled panel's date column: each date repeated once per ticker."""
    days = pd.bdate_range("2021-01-04", periods=n_days)
    return pd.Series(np.repeat(days.values, tickers))


def test_chrono_holdout_is_ordered_and_embargoed():
    dates = _panel_dates()
    tr, te = validation.chrono_holdout(dates, test_frac=0.3, embargo=5)
    d = pd.to_datetime(dates.reset_index(drop=True))

    assert not (tr & te).any()                       # disjoint
    train_max, test_min = d[tr].max(), d[te].min()
    assert train_max < test_min                      # train strictly precedes test
    # The embargo leaves a gap of more than one trading day before the test set.
    gap_days = np.busday_count(train_max.date(), test_min.date())
    assert gap_days >= 5


def test_walk_forward_folds_have_no_leakage_and_expand():
    dates = _panel_dates()
    folds = validation.purged_walk_forward(dates, n_splits=4, embargo=5)
    assert len(folds) >= 2
    d = pd.to_datetime(dates.reset_index(drop=True))

    prev_train = -1
    for tr, te in folds:
        assert not (tr & te).any()                   # no row in both
        assert d[tr].max() < d[te].min()             # train precedes test, purged
        assert tr.sum() > prev_train                 # expanding window
        prev_train = tr.sum()


def test_cv_summary_aggregates_metrics():
    dates = _panel_dates()
    n = len(dates)
    X = pd.DataFrame({"f": np.arange(n, dtype=float)})
    y = pd.Series(np.arange(n) % 2)

    def fit_score(xa, ya, xb, yb):
        return {"acc": float((yb == yb.mode().iloc[0]).mean())}

    out = validation.cv_summary(X, y, dates, fit_score, n_splits=4)
    assert out["n_folds"] >= 2
    assert out["cv"][0]["metric"] == "acc"
    assert 0.0 <= out["cv"][0]["mean"] <= 1.0


def test_cv_summary_skips_unusable_folds():
    """Folds where fit_score returns None (e.g. single-class) are dropped."""
    dates = _panel_dates()
    X = pd.DataFrame({"f": np.zeros(len(dates))})
    y = pd.Series(np.zeros(len(dates), dtype=int))

    out = validation.cv_summary(X, y, dates, lambda *a: None)
    assert out["n_folds"] == 0 and out["cv"] == []
