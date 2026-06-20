"""FastAPI application.

Exposes the analysis as a small JSON API and serves the static frontend. Domain
exceptions are mapped to meaningful HTTP status codes by global handlers so route
code stays clean.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.exceptions import (ConfigurationError, DataSourceError,
                            InsufficientDataError, ModelError, StockDropsError)
from app.logging_config import get_logger
from app.services import analysis_service

logger = get_logger(__name__)

app = FastAPI(
    title="Stock Drop-Driver Analysis API",
    version="1.0.0",
    description="Identify and rank the drivers behind significant stock price drops.",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Exception handlers: map domain errors -> HTTP status codes
# --------------------------------------------------------------------------
_STATUS = {
    DataSourceError: 503,        # upstream unavailable
    InsufficientDataError: 422,  # unprocessable
    ConfigurationError: 400,
    ModelError: 500,
}


@app.exception_handler(StockDropsError)
async def _domain_error_handler(request: Request, exc: StockDropsError):
    status = next((s for t, s in _STATUS.items() if isinstance(exc, t)), 500)
    logger.error("%s -> HTTP %d: %s", type(exc).__name__, status, exc)
    return JSONResponse(status_code=status,
                        content={"error": type(exc).__name__, "detail": str(exc)})


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "synthetic": s.use_synthetic,
            "tickers": list(s.tickers), "drop_threshold": s.drop_threshold}


@app.get("/api/sections")
def sections() -> dict:
    return {"sections": [{"key": k, "title": t}
                         for k, (t, _) in analysis_service.SECTIONS.items()]}


@app.get("/api/analyze/{section}")
def analyze(section: str) -> dict:
    if section not in analysis_service.SECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown section '{section}'.")
    return analysis_service.run_section(section)


@app.get("/api/analyze")
def analyze_all() -> dict:
    return analysis_service.run_all()


# --------------------------------------------------------------------------
# Serve the built React frontend (mounted last so /api/* wins).
# Run ``npm run build`` in ../frontend to produce the dist/ bundle. During UI
# development use ``npm run dev`` instead (Vite serves on :5173 and proxies to
# this API), so the absence of dist/ here is expected and not an error.
# --------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
else:
    logger.warning(
        "Frontend bundle not found at %s -- run 'npm run build' in frontend/, "
        "or use 'npm run dev' for the Vite dev server.", _FRONTEND_DIST,
    )
