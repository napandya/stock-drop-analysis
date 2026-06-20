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


def test_tickers_catalog():
    r = client.get("/api/tickers")
    assert r.status_code == 200
    catalog = r.json()["catalog"]
    assert catalog and {"ticker", "name", "sector"} <= catalog[0].keys()


def test_analyze_selection_returns_explanations():
    r = client.post("/api/analyze", json={"tickers": ["AAA", "BBB", "CCC"]})
    assert r.status_code == 200
    body = r.json()
    assert body["dataset"]["synthetic"] is True
    assert set(body["sections"]) >= {"regression", "classification", "ensembles", "clustering"}
    exp = body["explanations"]
    assert exp["title"] == "Why these stocks fell"
    assert {e["ticker"] for e in exp["explanations"]} == {"AAA", "BBB", "CCC"}


def test_analyze_selection_invalid_count_is_400():
    r = client.post("/api/analyze", json={"tickers": ["AAA"]})  # below minimum
    assert r.status_code == 400
    assert r.json()["error"] == "ConfigurationError"


def test_datasource_error_maps_to_503(monkeypatch):
    """A failed upstream fetch must surface as 503 with a typed error body --
    this is the exact path the distutils / pandas-datareader breakage hit."""
    from app.exceptions import DataSourceError
    import app.services.analysis_service as svc

    def _boom():
        raise DataSourceError("upstream unreachable")

    monkeypatch.setattr(svc, "run_all", _boom)
    r = client.get("/api/analyze")
    assert r.status_code == 503
    assert r.json()["error"] == "DataSourceError"
