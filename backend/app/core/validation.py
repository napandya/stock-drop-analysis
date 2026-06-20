"""Time-aware validation for the panel models.

The stock models predict a same-day outcome from features, so a random
train/test split (a) trains on the future to predict the past and (b) ignores
serial structure -- both inflate the scores. These helpers split strictly by
**date** (all tickers share the split) and purge an **embargo** of trading days
between train and test, because several features use trailing windows (20-day
volatility, 60-day betas) that would otherwise straddle the boundary and leak.

Two schemes:
* ``chrono_holdout`` -- one out-of-sample split (last fraction of dates), used
  for the reported metrics, figures and the driver ranking.
* ``purged_walk_forward`` -- expanding-window folds, used to report how stable a
  metric is across time (mean +/- std), which is the honest headline number.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _unique_dates(dates) -> np.ndarray:
    return np.array(sorted(pd.to_datetime(pd.Series(dates)).unique()))


def chrono_holdout(dates, test_frac: float = 0.3, embargo: int = 5):
    """Return boolean ``(train_mask, test_mask)`` for a single chronological
    split: the last ``test_frac`` of unique dates are the test set, with an
    ``embargo`` of dates immediately before the test dropped from training."""
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    uniq = _unique_dates(d)
    n_test = max(1, int(round(len(uniq) * test_frac)))
    test_dates = uniq[-n_test:]
    train_pool = uniq[:-n_test]
    train_dates = train_pool[:-embargo] if embargo and len(train_pool) > embargo else train_pool
    return d.isin(train_dates).to_numpy(), d.isin(test_dates).to_numpy()


def purged_walk_forward(dates, n_splits: int = 4, embargo: int = 5):
    """Yield expanding-window ``(train_mask, test_mask)`` folds. Fold *i* trains
    on all dates before test block *i* (minus the embargo) and tests on block *i*."""
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    uniq = _unique_dates(d)
    if len(uniq) < (n_splits + 1) * 2:
        n_splits = max(1, len(uniq) // 2 - 1)
    blocks = np.array_split(uniq, n_splits + 1)

    folds = []
    for i in range(1, len(blocks)):
        test_dates = blocks[i]
        train_pool = uniq[uniq < test_dates[0]]
        train_dates = (train_pool[:-embargo]
                       if embargo and len(train_pool) > embargo else train_pool)
        tr = d.isin(train_dates).to_numpy()
        te = d.isin(test_dates).to_numpy()
        if tr.sum() >= 10 and te.sum() >= 5:
            folds.append((tr, te))
    return folds


def cv_summary(X, y, dates, fit_score, n_splits: int = 4, embargo: int = 5) -> dict:
    """Run ``fit_score(Xtr, ytr, Xte, yte) -> {metric: value}`` across
    walk-forward folds and aggregate to ``mean``/``std`` per metric.

    ``fit_score`` may return ``None`` for an unusable fold (e.g. a test block
    with a single class); such folds are skipped.
    """
    folds = purged_walk_forward(dates, n_splits, embargo)
    rows = []
    for tr, te in folds:
        res = fit_score(X[tr], y[tr], X[te], y[te])
        if res:
            rows.append(res)
    if not rows:
        return {"n_folds": 0, "embargo_days": embargo, "cv": []}
    metrics = rows[0].keys()
    cv = [{"metric": k,
           "mean": round(float(np.mean([r[k] for r in rows])), 4),
           "std": round(float(np.std([r[k] for r in rows])), 4)}
          for k in metrics]
    return {"n_folds": len(rows), "embargo_days": embargo, "cv": cv}
