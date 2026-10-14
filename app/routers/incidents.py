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

from fastapi import APIRouter, HTTPException, Body, Query

from app.models import IncidentInput, RCAResult, ResolutionFeedback, RCAFeedbackDecision
from app.rca_engine import analyze_incident

logger = logging.getLogger(__name__)
router = APIRouter()


def _state() -> Dict[str, Any]:
    from app.main import get_app_state
    return get_app_state()


def _update_metrics(rca: RCAResult) -> None:
    s = _state()
    s["all_results"][rca.incident_number] = rca
    s["incidents_analyzed"] = len(s["all_results"])
    s["confidence_sum"] = sum(
        (r.confidence_score if hasattr(r, "confidence_score") else float(r.get("confidence_score", 0.0)))
        for r in s["all_results"].values()
    )
    s["high_confidence_count"] = sum(
        1 for r in s["all_results"].values()
        if (r.confidence_score if hasattr(r, "confidence_score") else float(r.get("confidence_score", 0.0))) >= 0.7
    )

    # Persist analysis result to Firestore
    try:
        from app.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        kb.save_analysis_result(rca.model_dump())
    except Exception as exc:
        logger.warning("Could not persist analysis to Firestore: %s", exc)


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
    from app.knowledge_base import get_knowledge_base
    kb = get_knowledge_base()
    all_res = kb.get_all_analysis_results()
    if not all_res:
        all_res = [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in _state().get("all_results", {}).values()
        ]

    # Sort newest first
    all_res.sort(key=lambda x: str(x.get("analyzed_at", "")), reverse=True)

    return [
        {
            "incident_number": r.get("incident_number", "?"),
            "probable_root_cause": (r.get("probable_root_cause") or "")[:120],
            "confidence_score": float(r.get("confidence_score", 0.0)),
            "confidence_label": r.get("confidence_label", "medium"),
            "recommended_team": r.get("recommended_team", ""),
            "analysis_mode": r.get("analysis_mode", "local"),
            "decision": r.get("decision", "pending"),
            "decision_notes": r.get("decision_notes", ""),
            "decided_at": str(r.get("decided_at", "")),
            "analyzed_at": str(r.get("analyzed_at", "")),
        }
        for r in all_res
    ]


@router.get("/history/decisions", summary="List evaluated incidents (Accepted and Rejected only, exempting pending)")
async def list_evaluated_incidents() -> List[Dict[str, Any]]:
    from app.knowledge_base import get_knowledge_base
    kb = get_knowledge_base()
    all_res = kb.get_all_analysis_results()
    if not all_res:
        all_res = [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in _state().get("all_results", {}).values()
        ]

    # Strictly exempt the pending state: only include 'accepted' or 'rejected'
    evaluated = [
        r for r in all_res
        if str(r.get("decision", "")).lower().strip() in ("accepted", "rejected")
    ]

    # Sort newest decided_at / analyzed_at first
    evaluated.sort(
        key=lambda x: str(x.get("decided_at") or x.get("analyzed_at", "")),
        reverse=True,
    )

    return [
        {
            "incident_number": r.get("incident_number", "?"),
            "decision": str(r.get("decision", "")).lower().strip(),
            "decision_notes": r.get("decision_notes", ""),
            "decided_at": str(r.get("decided_at") or r.get("analyzed_at", "")),
            "probable_root_cause": r.get("probable_root_cause", ""),
            "confidence_score": float(r.get("confidence_score", 0.0)),
            "confidence_label": r.get("confidence_label", "medium"),
            "recommended_team": r.get("recommended_team", ""),
            "analysis_mode": r.get("analysis_mode", "local"),
            "analyzed_at": str(r.get("analyzed_at", "")),
        }
        for r in evaluated
    ]


@router.post("/{incident_number}/decision", summary="Submit engineer acceptance/rejection decision")
async def submit_incident_decision(
    incident_number: str,
    payload: RCAFeedbackDecision = Body(...),
):
    from app.knowledge_base import get_knowledge_base
    kb = get_knowledge_base()
    kb.update_analysis_decision(
        incident_number=incident_number,
        decision=payload.decision,
        engineer_notes=payload.engineer_notes or "",
    )
    s = _state()
    if incident_number in s.get("all_results", {}):
        r = s["all_results"][incident_number]
        if isinstance(r, dict):
            r["decision"] = payload.decision
            r["decision_notes"] = payload.engineer_notes or ""
        elif hasattr(r, "decision"):
            r.decision = payload.decision
            r.decision_notes = payload.engineer_notes or ""

    return {"success": True, "incident_number": incident_number, "decision": payload.decision}


@router.get("/{incident_number}", response_model=RCAResult, summary="Get stored RCA result")
async def get_rca(incident_number: str):
    res = _state().get("all_results", {}).get(incident_number)
    if not res:
        from app.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        doc = kb.get_analysis_result(incident_number)
        if doc:
            res = RCAResult(**doc)
            _state()["all_results"][incident_number] = res

    if not res:
        raise HTTPException(status_code=404, detail=f"No RCA found for {incident_number}")
    return res if isinstance(res, RCAResult) else RCAResult(**res)


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

