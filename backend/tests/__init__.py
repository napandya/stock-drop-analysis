"""Test package.

The suite runs offline on synthetic data by default (fast, deterministic, no
network), so the data sources can be flaky without breaking CI. The one
exception is the opt-in real-data contract test (``pytest --run-live``), which
hits live sources to catch format/dtype drift that synthetic data can't.
"""
