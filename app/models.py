"""
RCA Assistant – Shared Pydantic models
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Incident Input ────────────────────────────────────────────────────────────

class IncidentInput(BaseModel):
    incident_number: str = Field(..., examples=["INC0001234"])
    short_description: str
    description: str = ""
    category: str = "software"
    priority: str = "3 - Moderate"
    logs: str = ""
    recent_changes: str = ""
    application: str = ""
    environment: str = "production"
    # Populated by ServiceNow integration
    sys_id: Optional[str] = None
    assignment_group: Optional[str] = None


# ── RCA Output ────────────────────────────────────────────────────────────────

class DiagnosticCommand(BaseModel):
    command: str
    description: str
    requires_approval: bool = False


class SimilarCase(BaseModel):
    case_id: str
    description: str
    root_cause: str
    resolution: str
    similarity_score: float
    category: str = ""


class RCAResult(BaseModel):
    incident_number: str
    probable_root_cause: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_label: str = "medium"   # low / medium / high
    evidence: List[str] = []
    recommended_team: str = ""
    recommended_actions: List[str] = []
    diagnostic_commands: List[DiagnosticCommand] = []
    similar_cases: List[SimilarCase] = []
    analysis_mode: str = "local"
    writeback_status: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Feedback ──────────────────────────────────────────────────────────────────

class ResolutionFeedback(BaseModel):
    incident_number: str
    verified_root_cause: str
    resolution_notes: str
    final_assignment_group: str = ""
    incident_input: Optional[IncidentInput] = None


class ResolveWebhookPayload(BaseModel):
    incident_number: str
    short_description: str = ""
    close_notes: str = ""
    close_code: str = ""
    verified_root_cause: str = ""
    assignment_group: str = ""
    category: str = "general"


class RCAFeedbackDecision(BaseModel):
    incident_number: str
    decision: str = "accepted"  # "accepted" or "rejected"
    engineer_notes: Optional[str] = ""
    assignment_group: Optional[str] = ""


# ── Configuration API ─────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    servicenow_instance_url: Optional[str] = None
    servicenow_username: Optional[str] = None
    servicenow_password: Optional[str] = None
    servicenow_writeback_enabled: Optional[bool] = None
    claude_api_key: Optional[str] = None
    claude_model: Optional[str] = None
    firebase_service_account_path: Optional[str] = None
    firebase_project_id: Optional[str] = None
    analysis_mode: Optional[str] = None


class ConfigStatus(BaseModel):
    servicenow_instance_url: str
    servicenow_username: str
    servicenow_writeback_enabled: bool
    claude_configured: bool
    firebase_configured: bool
    analysis_mode: str
    scheduler_running: bool
    incidents_analyzed: int
    knowledge_cases: int
    average_confidence: float
    high_confidence_count: int


# ── Scheduler ─────────────────────────────────────────────────────────────────

class SchedulerStatus(BaseModel):
    running: bool
    last_incident: Optional[str] = None
    last_writeback_status: Optional[str] = None
    next_run: Optional[str] = None
    error: Optional[str] = None


# ── Copilot Q&A ───────────────────────────────────────────────────────────────

class CopilotQuestion(BaseModel):
    incident_number: str
    question: str


class CopilotAnswer(BaseModel):
    incident_number: str
    question: str
    answer: str
    sources: List[str] = []

