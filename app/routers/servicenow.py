"""
Router: ServiceNow Integration
GET  /api/servicenow/test                 – test connection
GET  /api/servicenow/incidents            – fetch new incidents
POST /api/servicenow/decision             – record acceptance or rejection of RCA
POST /api/servicenow/resolve-webhook      – auto ingest resolved incidents into Firebase KB
GET  /api/servicenow/{number}             – fetch and analyze a specific incident
POST /api/servicenow/{number}/writeback   – push RCA to incident work notes
"""
from __future__ import annotations

import logging
import re
from typing import List

from fastapi import APIRouter, HTTPException

from app.models import IncidentInput, RCAResult, RCAFeedbackDecision, ResolveWebhookPayload
from app.servicenow import get_snow_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/test", summary="Test ServiceNow connectivity")
async def test_connection():
    snow = get_snow_client()
    if not snow:
        return {"success": False, "error": "ServiceNow not configured. Set instance URL and credentials."}
    return await snow.test_connection()


@router.get("/incidents", summary="Fetch new unanalyzed incidents from ServiceNow")
async def fetch_incidents(limit: int = 10) -> List[dict]:
    snow = get_snow_client()
    if not snow:
        raise HTTPException(status_code=503, detail="ServiceNow not configured.")
    incidents = await snow.get_new_incidents(limit=limit)
    return [i.model_dump() for i in incidents]


@router.post("/decision", summary="Record engineer acceptance or rejection of RCA recommendation")
async def record_decision(payload: RCAFeedbackDecision):
    from app.main import get_app_state
    state = get_app_state()
    decisions = state.setdefault("rca_decisions", {})
    decisions[payload.incident_number] = payload.model_dump()

    logger.info(
        "RCA %s for incident %s by engineer. Notes: %s",
        payload.decision.upper(),
        payload.incident_number,
        payload.engineer_notes or "None",
    )

    return {
        "success": True,
        "incident_number": payload.incident_number,
        "decision": payload.decision,
        "message": f"RCA recommendation {payload.decision} recorded successfully.",
    }


@router.post("/resolve-webhook", summary="Receive resolved ServiceNow incident and add to Firebase KB")
async def resolve_webhook(payload: ResolveWebhookPayload):
    """
    Called when a ServiceNow incident is resolved/closed.
    Automatically ingests the engineer-verified root cause and resolution notes
    into the Firebase Knowledge Base for future incident triage.
    """
    from app.knowledge_base import get_knowledge_base

    root_cause = payload.verified_root_cause.strip() or payload.close_notes.strip() or "Resolved per support notes"
    resolution = payload.close_notes.strip() or "Standard resolution applied"

    # Extract keywords from description, root cause and resolution
    text = f"{payload.short_description} {root_cause} {resolution}".lower()
    raw_words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
    stop = {"this", "that", "with", "have", "been", "from", "were", "they", "their", "when", "after", "issue"}
    keywords = list({w for w in raw_words if w not in stop})[:15]

    case = {
        "case_id": f"SN-{payload.incident_number}",
        "category": payload.category or "general",
        "description": payload.short_description or f"Resolved ServiceNow ticket {payload.incident_number}",
        "root_cause": root_cause,
        "resolution": resolution,
        "keywords": keywords,
        "assignment_group": payload.assignment_group or "Support Team",
        "verified": True,
        "source": "servicenow_resolved_webhook",
        "close_code": payload.close_code or "",
    }

    kb = get_knowledge_base()
    case_id = kb.add_case(case)

    logger.info(
        "Learned from ServiceNow incident %s! Saved to Firebase KB with ID: %s",
        payload.incident_number,
        case_id,
    )

    return {
        "success": True,
        "case_id": case_id,
        "incident_number": payload.incident_number,
        "message": f"Incident {payload.incident_number} successfully published to Firebase Knowledge Base.",
    }


@router.get("/{incident_number}", response_model=RCAResult, summary="Fetch incident from SN and analyze it")
async def fetch_and_analyze(incident_number: str):
    snow = get_snow_client()
    if not snow:
        raise HTTPException(status_code=503, detail="ServiceNow not configured.")

    incident = await snow.get_incident(incident_number)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_number} not found in ServiceNow.")

    from app.rca_engine import analyze_incident
    from app.routers.incidents import _update_metrics
    rca = await analyze_incident(incident)
    _update_metrics(rca)
    return rca


@router.post("/{incident_number}/writeback", summary="Write RCA back to ServiceNow incident")
async def writeback(incident_number: str):
    from app.main import get_app_state
    state = get_app_state()
    rca: RCAResult = state.get("all_results", {}).get(incident_number)
    if not rca:
        raise HTTPException(status_code=404, detail=f"No RCA found for {incident_number}. Analyze first.")

    snow = get_snow_client()
    if not snow:
        raise HTTPException(status_code=503, detail="ServiceNow not configured.")

    # We need the sys_id – try fetching the incident
    incident = await snow.get_incident(incident_number)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Could not retrieve {incident_number} from ServiceNow.")

    result = await snow.write_rca_to_incident(incident, rca, rca.recommended_team)
    return result
