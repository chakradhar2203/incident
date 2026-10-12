"""
Router: Scheduler
POST /api/scheduler/start   – start recurring incident generation
POST /api/scheduler/stop    – stop scheduler
GET  /api/scheduler/status  – get current status
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.models import SchedulerStatus
from app.scheduler import get_scheduler_status, start_scheduler, stop_scheduler

router = APIRouter()


@router.post("/start", summary="Start the recurring synthetic incident scheduler")
async def start(interval_minutes: int = 0):
    s = get_settings()
    mins = interval_minutes or s.scheduler_interval_minutes
    start_scheduler(interval_minutes=mins)
    return {"success": True, "message": f"Scheduler started (every {mins} minutes)."}


@router.post("/stop", summary="Stop the scheduler")
async def stop():
    stop_scheduler()
    return {"success": True, "message": "Scheduler stopped."}


@router.get("/status", summary="Get scheduler status")
async def status() -> SchedulerStatus:
    s = get_scheduler_status()
    return SchedulerStatus(**s)

