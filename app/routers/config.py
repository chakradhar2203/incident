"""
Router: Configuration & Status
GET  /api/config        – return current (sanitised) config
POST /api/config        – update runtime config
GET  /api/config/status – return full operational status
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import ConfigStatus, ConfigUpdate

router = APIRouter()


@router.get("", summary="Get current (sanitised) configuration")
async def get_config():
    s = get_settings()
    from app.main import get_app_state
    state = get_app_state()
    n = state["incidents_analyzed"]
    avg_conf = (state["confidence_sum"] / n) if n > 0 else 0.0

    return {
        "servicenow_instance_url": s.servicenow_instance_url,
        "servicenow_username": s.servicenow_username,
        "servicenow_writeback_enabled": s.servicenow_writeback_enabled,
        "claude_configured": bool(s.claude_api_key),
        "firebase_configured": _firebase_status(),
        "analysis_mode": state.get("runtime_config", {}).get("analysis_mode", s.analysis_mode),
        "incidents_analyzed": n,
        "knowledge_cases": _kb_count(),
        "average_confidence": round(avg_conf, 3),
        "high_confidence_count": state["high_confidence_count"],
        # Passwords / keys are NEVER returned
    }


@router.post("", summary="Update runtime configuration")
async def update_config(update: ConfigUpdate):
    """
    Applies runtime overrides. Sensitive values are stored in process memory only.
    """
    from app.config import get_settings
    from app import servicenow as snow_mod
    s = get_settings()

    from app.main import get_app_state
    state = get_app_state()
    rc = state.setdefault("runtime_config", {})

    if update.servicenow_instance_url is not None:
        rc["servicenow_instance_url"] = update.servicenow_instance_url
        s.servicenow_instance_url = update.servicenow_instance_url
        snow_mod.reset_snow_client()

    if update.servicenow_username is not None:
        s.servicenow_username = update.servicenow_username
        snow_mod.reset_snow_client()

    if update.servicenow_password is not None:
        s.servicenow_password = update.servicenow_password
        snow_mod.reset_snow_client()

    if update.servicenow_writeback_enabled is not None:
        s.servicenow_writeback_enabled = update.servicenow_writeback_enabled

    if update.claude_api_key is not None:
        s.claude_api_key = update.claude_api_key

    if update.claude_model is not None:
        s.claude_model = update.claude_model

    if update.analysis_mode is not None:
        s.analysis_mode = update.analysis_mode
        rc["analysis_mode"] = update.analysis_mode

    if update.firebase_service_account_path is not None:
        s.firebase_service_account_path = update.firebase_service_account_path
        # Reinitialise KB
        import app.knowledge_base as kb_mod
        kb_mod._kb_instance = None

    if update.firebase_project_id is not None:
        s.firebase_project_id = update.firebase_project_id

    return {"success": True, "message": "Configuration updated."}


def _kb_count() -> int:
    try:
        from app.knowledge_base import get_knowledge_base
        return get_knowledge_base().count()
    except Exception:
        return 0


def _firebase_status() -> bool:
    try:
        from app.knowledge_base import get_knowledge_base
        return get_knowledge_base().is_firebase_connected
    except Exception:
        return False

