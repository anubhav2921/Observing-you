"""
backend/app/main.py — FastAPI Application Entrypoint.
Exposes REST APIs, WebSocket streaming endpoints, and serves dashboard assets.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import api_router
from backend.app.api.websocket import ws_router
from backend.app.core.config import AUDIO_DIR, REPO_ROOT
from backend.app.models.loader import verify_model_files


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager."""
    print("=" * 60)
    print("  AI Study Focus Monitor — Backend Initializing")
    print("=" * 60)
    model_status = verify_model_files()
    print(f"[Startup] Verified model assets: {model_status}")
    print("[Startup] REST & WebSocket services ready.")
    yield
    print("[Shutdown] Releasing backend resources...")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="AI Study Focus Monitor API",
        version="2.0.0",
        description="Real-time multi-modal computer vision monitor for study focus, posture, and fatigue analytics.",
        lifespan=lifespan,
    )

    # Enforce HTTPS on cloud proxies (e.g. Render) to guarantee webcam API (getUserMedia) access
    @app.middleware("http")
    async def redirect_http_to_https(request: Request, call_next):
        proto = request.headers.get("x-forwarded-proto", "").lower()
        if proto == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(url), status_code=301)
        return await call_next(request)

    # Cross-Origin Resource Sharing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include REST API & WebSocket Routers
    app.include_router(api_router)
    app.include_router(ws_router)

    # Static Assets Mounts
    icons_dir = REPO_ROOT / "assets" / "icons"
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(icons_dir, exist_ok=True)

    app.mount("/assets/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio_assets")
    app.mount("/assets/icons", StaticFiles(directory=str(icons_dir)), name="icon_assets")

    frontend_dir = REPO_ROOT / "frontend"
    frontend_dist = frontend_dir / "dist"
    frontend_src = frontend_dir / "src"

    if (frontend_src / "styles").is_dir():
        app.mount("/css", StaticFiles(directory=str(frontend_src / "styles")), name="css")
    if frontend_src.is_dir():
        app.mount("/js", StaticFiles(directory=str(frontend_src)), name="js")
        app.mount("/src", StaticFiles(directory=str(frontend_src)), name="src")
    if (frontend_dir / "public").is_dir():
        app.mount("/public", StaticFiles(directory=str(frontend_dir / "public")), name="public")

    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        # Production build exists
        dist_assets = frontend_dist / "assets"
        if dist_assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(dist_assets)), name="dist_assets")

        @app.get("/", response_class=HTMLResponse)
        async def serve_index() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def serve_dev_index() -> FileResponse:
            index_file = frontend_dir / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
            return HTMLResponse("<h3>AI Study Focus Monitor: Frontend index.html not found.</h3>")

    return app


app = create_app()
