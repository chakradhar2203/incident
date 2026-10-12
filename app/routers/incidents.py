"""
Router: Incidents
POST /api/incidents/analyze       – submit an incident for RCA
GET  /api/incidents/{number}      – retrieve stored RCA result
GET  /api/incidents               – list all analyzed incidents
POST /api/incidents/feedback      – submit verified resolution feedback
POST /api/incidents/generate      – generate and analyze one synthetic incident
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.models import IncidentInput, RCAResult, ResolutionFeedback
from app.rca_engine import analyze_incident

logger = logging.getLogger(__name__)
router = APIRouter()


def _state() -> Dict[str, Any]:
    from app.main import get_app_state
    return get_app_state()


def _update_metrics(rca: RCAResult) -> None:
    s = _state()
    s["incidents_analyzed"] += 1
    s["all_results"][rca.incident_number] = rca
    s["confidence_sum"] = s.get("confidence_sum", 0.0) + rca.confidence_score
    if rca.confidence_score >= 0.7:
        s["high_confidence_count"] = s.get("high_confidence_count", 0) + 1


@router.post("/analyze", response_model=RCAResult, summary="Analyze an incident and generate RCA")
async def analyze(incident: IncidentInput):
    try:
        rca = await analyze_incident(incident)
    except Exception as exc:
        logger.error("Analysis error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    _update_metrics(rca)

    # ServiceNow write-back if enabled
    from app.config import get_settings
    s = get_settings()
    if s.servicenow_writeback_enabled and incident.sys_id:
        from app.servicenow import get_snow_client
        snow = get_snow_client()
        if snow:
            wb = await snow.write_rca_to_incident(incident, rca, rca.recommended_team)
            rca.writeback_status = "success" if wb.get("success") else f"failed: {wb.get('error')}"

    return rca


@router.get("", summary="List all analyzed incidents")
async def list_incidents() -> List[Dict[str, Any]]:
    results = _state().get("all_results", {})
    return [
        {
            "incident_number": r.incident_number,
            "probable_root_cause": r.probable_root_cause[:120],
            "confidence_score": r.confidence_score,
            "confidence_label": r.confidence_label,
            "recommended_team": r.recommended_team,
            "analysis_mode": r.analysis_mode,
            "analyzed_at": r.analyzed_at.isoformat(),
        }
        for r in results.values()
    ]


@router.get("/{incident_number}", response_model=RCAResult, summary="Get stored RCA result")
async def get_rca(incident_number: str):
    result = _state().get("all_results", {}).get(incident_number)
    if not result:
        raise HTTPException(status_code=404, detail=f"No RCA found for {incident_number}")
    return result


@router.post("/feedback", summary="Submit verified resolution feedback to knowledge base")
async def submit_feedback(feedback: ResolutionFeedback):
    from app.knowledge_base import get_knowledge_base

    kb = get_knowledge_base()
    case = {
        "case_id": f"FB-{feedback.incident_number}",
        "category": feedback.incident_input.category if feedback.incident_input else "general",
        "description": (
            feedback.incident_input.short_description if feedback.incident_input
            else f"Verified resolution for {feedback.incident_number}"
        ),
        "root_cause": feedback.verified_root_cause,
        "resolution": feedback.resolution_notes,
        "keywords": _extract_keywords(feedback.verified_root_cause + " " + feedback.resolution_notes),
        "assignment_group": feedback.final_assignment_group,
        "verified": True,
        "source_incident": feedback.incident_number,
    }
    case_id = kb.add_case(case)
    return {"success": True, "case_id": case_id, "message": "Feedback saved to knowledge base."}


@router.post("/generate", response_model=RCAResult, summary="Generate and analyze one synthetic incident")
async def generate_and_analyze():
    from app.incident_generator import generate_incident
    incident = generate_incident()
    return await analyze(incident)


def _extract_keywords(text: str) -> list:
    import re
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stop = {"this", "that", "with", "have", "been", "from", "were", "they", "their", "when"}
    return list({w for w in words if w not in stop})[:15]

