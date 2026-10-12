"""
RCA Assistant – Background Scheduler
Generates synthetic incidents every N minutes (configurable).
Creates a ServiceNow incident, analyses it, and writes back the RCA.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_status: Dict[str, Any] = {
    "running": False,
    "last_incident": None,
    "last_writeback_status": None,
    "next_run": None,
    "error": None,
}


async def _run_cycle() -> None:
    from app.config import get_settings
    from app.incident_generator import generate_incident
    from app.rca_engine import analyze_incident
    from app.servicenow import get_snow_client

    settings = get_settings()
    snow = get_snow_client()

    logger.info("Scheduler: starting synthetic incident cycle.")
    try:
        incident = generate_incident()
        _status["last_incident"] = incident.incident_number

        # Create in ServiceNow (if connected)
        created_sys_id: Optional[str] = None
        if snow:
            try:
                async with __import__("httpx").AsyncClient(
                    auth=(settings.servicenow_username, settings.servicenow_password),
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=30,
                ) as client:
                    payload = {
                        "number": incident.incident_number,
                        "short_description": incident.short_description,
                        "description": incident.description,
                        "category": incident.category,
                        "priority": incident.priority,
                        "u_application_logs": incident.logs,
                        "u_recent_changes": incident.recent_changes,
                    }
                    resp = await client.post(
                        f"{settings.servicenow_instance_url}/api/now/table/incident",
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        created_sys_id = resp.json().get("result", {}).get("sys_id")
                        incident.sys_id = created_sys_id
                        logger.info("Scheduler: created SN incident %s (sys_id=%s)", incident.incident_number, created_sys_id)
            except Exception as exc:
                logger.warning("Scheduler: SN create failed: %s", exc)

        # Analyse
        rca = await analyze_incident(incident)

        # Update metrics
        _app_state["incidents_analyzed"] += 1
        _app_state["all_results"][incident.incident_number] = rca
        _update_metrics(rca)

        # Write back
        wb_status = "skipped (write-back disabled)"
        if settings.servicenow_writeback_enabled and snow and incident.sys_id:
            wb = await snow.write_rca_to_incident(incident, rca, rca.recommended_team)
            wb_status = "success" if wb.get("success") else f"failed: {wb.get('error')}"

        _status["last_writeback_status"] = wb_status
        _status["error"] = None
        logger.info("Scheduler: cycle complete. writeback=%s", wb_status)

    except Exception as exc:
        _status["error"] = str(exc)
        logger.error("Scheduler cycle error: %s", exc)

    # Update next run time
    global _scheduler
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("recurring_cycle")
        if job and job.next_run_time:
            _status["next_run"] = job.next_run_time.isoformat()


# Reference to shared app state — injected by main.py on startup
_app_state: Dict[str, Any] = {
    "incidents_analyzed": 0,
    "all_results": {},
    "confidence_sum": 0.0,
    "high_confidence_count": 0,
}


def _update_metrics(rca: Any) -> None:
    _app_state["confidence_sum"] = _app_state.get("confidence_sum", 0.0) + rca.confidence_score
    if rca.confidence_score >= 0.7:
        _app_state["high_confidence_count"] = _app_state.get("high_confidence_count", 0) + 1


def init_app_state(state: Dict[str, Any]) -> None:
    """Called from main.py to share the global state dict."""
    global _app_state
    _app_state = state


def start_scheduler(interval_minutes: int = 2) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("Scheduler already running.")
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_cycle,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="recurring_cycle",
        name="Synthetic Incident Cycle",
        replace_existing=True,
    )
    _scheduler.start()
    _status["running"] = True
    _status["error"] = None
    logger.info("Scheduler started (interval=%dm).", interval_minutes)
    # Update next run
    job = _scheduler.get_job("recurring_cycle")
    if job and job.next_run_time:
        _status["next_run"] = job.next_run_time.isoformat()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
    _status["running"] = False
    _status["next_run"] = None
    logger.info("Scheduler stopped.")


def get_scheduler_status() -> Dict[str, Any]:
    return dict(_status)

