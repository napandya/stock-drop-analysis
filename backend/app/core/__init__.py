"""Core data, feature-engineering and attribution layer.

This is the only layer that reaches the network, and it is deliberately the most
heavily tested. Everything funnels through ``data_pipeline.get_modeling_dataset``,
which returns one tidy "modelling panel" (one row per stock-day) that every model
consumes — so the models never see raw vendor formats.

Modules and why they exist
--------------------------
* ``data_pipeline`` — fetch prices (yfinance), macro (FRED) and earnings, with
  retry/backoff, in-process caching and a typed ``DataSourceError`` on failure;
  a synthetic fallback keeps the whole app runnable offline.
* ``features``      — pure feature engineering and the drop label. Kept free of
  I/O so it is trivially unit-testable; this is also where the leakage rule is
  enforced (``ret_1d`` is excluded from ``FEATURE_COLUMNS``).
* ``synthetic``     — a realistic offline panel (with a real factor structure and
  injected crashes) so tests/CI/previews need no network.
* ``factors``       — systematic (market+sector) vs. idiosyncratic decomposition.
* ``macro_calendar``— rate-shock + FOMC context for each day.
* ``earnings``      — earnings dates + EPS surprise, the top single-name catalyst.
* ``market_events`` — curated global-event calendar for the narrative tie-in.
* ``validation``    — purged, walk-forward time-series splits (no look-ahead).

``factors``, ``macro_calendar``, ``earnings`` and ``market_events`` produce
*attribution-only* columns: same-day context used to explain a drop, never fed to
the models as predictors.
"""
