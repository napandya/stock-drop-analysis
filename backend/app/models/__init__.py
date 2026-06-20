"""Analysis sections and explanations.

Each module exposes a ``run(data, settings) -> dict`` that takes the shared
modelling panel and returns metrics + base64 figures, so the service layer can
treat them uniformly. The four sections map to the course's four "members":

* ``regression``     — Member 1: linear / multiple / tree regression of the
                       daily return (how much of the move is explainable).
* ``classification`` — Member 2: drop vs. no-drop classifiers, plus a TF-IDF /
                       VADER news-sentiment task.
* ``ensembles``      — Member 3: Random Forest + XGBoost, whose averaged feature
                       importances give the headline driver ranking.
* ``clustering``     — Member 4: K-Means drop "types" + Isolation-Forest anomalies.

``explain`` is the project's interpretive layer: for a chosen set of tickers it
ranks each stock's worst-drop drivers and attaches the systematic/idiosyncratic
split, macro/earnings/event context and a plain-language narrative.

Design choices shared across the supervised sections: time-aware
(walk-forward) validation rather than a leaky random split, class-imbalance
handling, and feature scaling where the model needs it. ``_plot`` centralises the
headless Matplotlib → base64 rendering so figures travel as JSON.
"""
