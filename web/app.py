"""
web/app.py
==========
FastAPI application factory for UGC Video Pro.

Usage:
    from web.app import create_app
    app = create_app(config)

Or via the project entry point (main.py):
    uvicorn main:app --host 0.0.0.0 --port 8000

Features:
    - CORS middleware with configurable origins
    - Static file serving at "/" (serves the SPA from static/)
    - API routers: /api/auth, /api/video, /api/admin
    - WebSocket: /api/ws/progress/{task_id}
    - Startup: creates DB tables, seeds admin, ensures data dirs exist
    - Global exception handlers for clean JSON error responses
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from web.database import init_db

logger = logging.getLogger(__name__)

# ── Module-level config store (set by create_app) ────────────────────────────────────────────
_app_config: dict = {}


def get_app_config() -> dict:
    """Return the config dict passed to create_app(). Used by routes_video."""
    return _app_config


# ── Data directories ────────────────────────────────────────────────────────────────

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/app/data"))


def _ensure_data_dirs() -> None:
    """Create required data directories if they don't exist."""
    dirs = [
        DATA_ROOT / "uploads",
        DATA_ROOT / "videos",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Data directory ready: {d}")


# ── Application factory ────────────────────────────────────────────────────────────────

def create_app(config: dict | None = None) -> FastAPI:
    """
    Build and return the FastAPI application.

    Args:
        config: Application configuration dict.  Keys used:
            web.cors_origins (list[str]) — allowed CORS origins (default: ["*"])
            web.title        (str)       — API title shown in docs
            web.version      (str)       — API version string

    Returns:
        Configured FastAPI application instance.
    """
    global _app_config
    _app_config = config or {}

    web_cfg: dict = _app_config.get("web", {})
    cors_origins: list[str] = web_cfg.get("cors_origins", ["*"])
    api_title: str = web_cfg.get("title", "UGC Video Pro API")
    api_version: str = web_cfg.get("version", "1.0.0")

    # ── Lifespan (startup / shutdown) ───────────────────────────────────────────────────
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ── Startup ──
        logger.info("Starting UGC Video Pro API…")
        _ensure_data_dirs()
        try:
            await init_db()
        except Exception as exc:
            logger.error(f"Database init failed: {exc}", exc_info=True)
            # Don't crash the process — the DB may come up later
        logger.info("Startup complete.")

        yield

        # ── Shutdown ──
        logger.info("Shutting down UGC Video Pro API.")

    # ── Create FastAPI instance ────────────────────────────────────────────────────────
    app = FastAPI(
        title=api_title,
        version=api_version,
        description=(
            "RESTful API for UGC Video Pro — AI-powered product video generation.\n\n"
            "Supports image-to-video, text-to-video, and URL-to-video modes "
            "with real-time WebSocket progress updates."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return consistent JSON structure for all HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return detailed validation errors as JSON."""
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": " → ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": "Validation error", "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unexpected server errors."""
        logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Internal server error"},
        )

    # ── API Routers ───────────────────────────────────────────────────────────────────────
    from web.routes_admin import router as admin_router
    from web.routes_auth import router as auth_router
    from web.routes_video import router as video_router
    from web.websocket import router as ws_router

    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(video_router, prefix="/api/video")
    app.include_router(admin_router, prefix="/api/admin")

    # WebSocket routes (no prefix — the path already starts with /progress)
    app.include_router(ws_router, prefix="/api/ws")

    # ── Health check ───────────────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["meta"], summary="Health check")
    async def health() -> dict:
        return {"status": "ok", "version": api_version}

    # ── Static files (SPA frontend) ──────────────────────────────────────────────────────
    # Mount last so it doesn't shadow the API routes.
    static_dir = Path(os.environ.get("STATIC_DIR", "/app/static"))
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info(f"Serving static files from {static_dir}")
    else:
        logger.warning(
            f"Static directory not found: {static_dir} — frontend will not be served. "
            "Set STATIC_DIR env var or build the frontend first."
        )

    return app
