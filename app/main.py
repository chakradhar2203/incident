"""
RCA Assistant – FastAPI Application
Mounts all API routes and serves the dashboard UI.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.scheduler import init_app_state, stop_scheduler

logger = logging.getLogger(__name__)

# ── Shared in-process state ───────────────────────────────────────────────────
_state: Dict[str, Any] = {
    "incidents_analyzed": 0,
    "all_results": {},       # incident_number → RCAResult
    "confidence_sum": 0.0,
    "high_confidence_count": 0,
    "runtime_config": {},    # overrides applied via /api/config
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Share state with scheduler
    init_app_state(_state)
    logger.info("RCA Assistant started.")
    yield
    stop_scheduler()
    logger.info("RCA Assistant stopped.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RCA Assistant",
        description="AI Incident Triage & Root Cause Analysis",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Import and register routers ───────────────────────────────────────────
    from app.routers import config, copilot, incidents, knowledge, scheduler, servicenow

    app.include_router(config.router,      prefix="/api/config",      tags=["Configuration"])
    app.include_router(incidents.router,   prefix="/api/incidents",   tags=["Incidents"])
    app.include_router(knowledge.router,   prefix="/api/knowledge",   tags=["Knowledge Base"])
    app.include_router(servicenow.router,  prefix="/api/servicenow",  tags=["ServiceNow"])
    app.include_router(scheduler.router,   prefix="/api/scheduler",   tags=["Scheduler"])
    app.include_router(copilot.router,     prefix="/api/copilot",     tags=["Copilot"])

    # ── Static files ──────────────────────────────────────────────────────────
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        index = os.path.join(static_dir, "index.html")
        return FileResponse(index)

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()

# ── Expose shared state to routers ────────────────────────────────────────────
def get_app_state() -> Dict[str, Any]:
    return _state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )

