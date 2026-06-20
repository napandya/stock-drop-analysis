"""API integration tests using FastAPI's TestClient.

The settings cache is overridden to force synthetic mode so the API never hits
the network during testing.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _force_synthetic():
    """Override the settings dependency with offline synthetic settings."""
    get_settings.cache_clear()
    app.dependency_overrides = {}
    # Patch the cached singleton used across the app.
    import app.config as cfg
    cfg.get_settings.cache_clear()
    cfg._test_settings = Settings(use_synthetic=True, min_rows_required=50)
    original = cfg.get_settings

    def _synthetic():
        return cfg._test_settings

    cfg.get_settings = _synthetic
    # Re-point modules that imported the symbol directly.
    import app.services.analysis_service as svc
    import app.core.data_pipeline as dp
    svc.get_settings = _synthetic
    dp.get_settings = _synthetic
    yield
    cfg.get_settings = original


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_sections_listed():
    r = client.get("/api/sections")
    keys = {s["key"] for s in r.json()["sections"]}
    assert {"regression", "classification", "ensembles", "clustering"} <= keys


def test_unknown_section_404():
    assert client.get("/api/analyze/nonsense").status_code == 404


def test_analyze_ensembles():
    r = client.get("/api/analyze/ensembles")
    assert r.status_code == 200
    body = r.json()
    assert body["ranking"]
    assert "dataset" in body and body["dataset"]["synthetic"] is True
