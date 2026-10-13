"""
RCA Assistant – ServiceNow Integration Service
Handles incident retrieval and write-back via the ServiceNow REST API.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.models import IncidentInput, RCAResult

logger = logging.getLogger(__name__)

# ── ServiceNow table / field constants ───────────────────────────────────────
INCIDENT_TABLE = "incident"
FIELDS = ",".join([
    "number", "short_description", "description", "category",
    "priority", "sys_id", "assignment_group", "state",
    "u_application_logs", "u_recent_changes", "cmdb_ci",
])


class ServiceNowClient:
    """Thin async wrapper around the ServiceNow Table API."""

    def __init__(self, instance_url: str, username: str, password: str):
        self.base_url = instance_url.rstrip("/")
        self._auth = (username, password)
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            auth=self._auth,
            headers=self._headers,
            timeout=30,
        )

    # ── Connectivity check ────────────────────────────────────────────────────

    async def test_connection(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/now/table/{INCIDENT_TABLE}?sysparm_limit=1"
        try:
            async with self._client() as c:
                resp = await c.get(url)
                resp.raise_for_status()
                return {"success": True, "status_code": resp.status_code}
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ── Incident retrieval ────────────────────────────────────────────────────

    async def get_incident(self, incident_number: str) -> Optional[IncidentInput]:
        url = (
            f"{self.base_url}/api/now/table/{INCIDENT_TABLE}"
            f"?sysparm_query=number={incident_number}"
            f"&sysparm_fields={FIELDS}&sysparm_limit=1"
        )
        try:
            async with self._client() as c:
                resp = await c.get(url)
                resp.raise_for_status()
                records = resp.json().get("result", [])
                if not records:
                    return None
                return self._map_to_incident(records[0])
        except Exception as exc:
            logger.error("Failed to get incident %s: %s", incident_number, exc)
            return None

    async def get_new_incidents(self, limit: int = 10) -> list[IncidentInput]:
        """Fetch recently created incidents not yet worked on."""
        url = (
            f"{self.base_url}/api/now/table/{INCIDENT_TABLE}"
            f"?sysparm_query=state=1^ORDERBYDESCsys_created_on"
            f"&sysparm_fields={FIELDS}&sysparm_limit={limit}"
        )
        try:
            async with self._client() as c:
                resp = await c.get(url)
                resp.raise_for_status()
                return [self._map_to_incident(r) for r in resp.json().get("result", [])]
        except Exception as exc:
            logger.error("Failed to fetch new incidents: %s", exc)
            return []

    def _map_to_incident(self, record: Dict[str, Any]) -> IncidentInput:
        def _str(v: Any) -> str:
            if isinstance(v, dict):
                return v.get("display_value", v.get("value", "")) or ""
            return str(v) if v else ""

        return IncidentInput(
            incident_number=_str(record.get("number")),
            short_description=_str(record.get("short_description")),
            description=_str(record.get("description")),
            category=_str(record.get("category")) or "software",
            priority=_str(record.get("priority")) or "3 - Moderate",
            logs=_str(record.get("u_application_logs")),
            recent_changes=_str(record.get("u_recent_changes")),
            application=_str(record.get("cmdb_ci")),
            sys_id=_str(record.get("sys_id")),
            assignment_group=_str(record.get("assignment_group")),
        )

    # ── Write-back ────────────────────────────────────────────────────────────

    async def write_rca_to_incident(
        self,
        incident: IncidentInput,
        rca: RCAResult,
        assignment_group: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add the RCA as a work note and optionally set the assignment group.
        Returns a status dict.
        """
        if not incident.sys_id:
            return {"success": False, "error": "No sys_id – cannot write back."}

        note = self._format_work_note(rca)
        payload: Dict[str, Any] = {
            "work_notes": note,
            "state": "2",  # In Progress
        }
        if assignment_group:
            payload["assignment_group"] = {"display_value": assignment_group}

        url = f"{self.base_url}/api/now/table/{INCIDENT_TABLE}/{incident.sys_id}"
        try:
            async with self._client() as c:
                resp = await c.patch(url, json=payload)
                resp.raise_for_status()
                return {"success": True, "incident": incident.incident_number}
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ── Create incident ───────────────────────────────────────────────────────

    async def create_incident(self, incident: IncidentInput) -> Dict[str, Any]:
        """Create a new incident ticket in ServiceNow."""
        payload: Dict[str, Any] = {
            "short_description": incident.short_description,
            "description": incident.description,
            "category": incident.category.lower(),
            "priority": incident.priority[0] if incident.priority and incident.priority[0].isdigit() else "2",
            "state": "1",  # New
        }
        if incident.logs:
            payload["u_application_logs"] = incident.logs
            payload["comments"] = f"Application / Infrastructure Logs:\n{incident.logs}"
        if incident.recent_changes:
            payload["u_recent_changes"] = incident.recent_changes
        if incident.application:
            payload["cmdb_ci"] = incident.application

        url = f"{self.base_url}/api/now/table/{INCIDENT_TABLE}"
        try:
            async with self._client() as c:
                resp = await c.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json().get("result", {})
                num = data.get("number")
                sys_id = data.get("sys_id")
                return {
                    "success": True,
                    "number": num,
                    "sys_id": sys_id,
                    "link": f"{self.base_url}/nav_to.do?uri=incident.do?sys_id={sys_id}",
                }
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
        except Exception as exc:
            logger.error("Failed to create incident in ServiceNow: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _format_work_note(rca: RCAResult) -> str:
        lines = [
            "⚠️  [AI-GENERATED RCA — REQUIRES ENGINEER REVIEW BEFORE ACTION]",
            "",
            f"🔍 Probable Root Cause: {rca.probable_root_cause}",
            f"📊 Confidence: {rca.confidence_label.upper()} ({rca.confidence_score:.0%})",
            f"👥 Recommended Team: {rca.recommended_team}",
            "",
            "📋 Evidence:",
        ]
        for ev in rca.evidence:
            lines.append(f"  • {ev}")
        lines += ["", "✅ Recommended Actions:"]
        for act in rca.recommended_actions:
            lines.append(f"  • {act}")
        if rca.diagnostic_commands:
            lines += ["", "🔧 Diagnostic Commands (do not run without approval):"]
            for cmd in rca.diagnostic_commands:
                approval = " ⚠️ REQUIRES APPROVAL" if cmd.requires_approval else ""
                lines.append(f"  $ {cmd.command}{approval}")
                lines.append(f"    {cmd.description}")
        if rca.similar_cases:
            lines += ["", "🕰️  Similar Historical Cases:"]
            for sc in rca.similar_cases:
                lines.append(
                    f"  • [{sc.case_id}] {sc.description[:80]}… "
                    f"(similarity {sc.similarity_score:.0%})"
                )
        lines += ["", f"Analysis performed at: {rca.analyzed_at.isoformat()} UTC"]
        return "\n".join(lines)


# ── Module-level singleton ────────────────────────────────────────────────────
_snow_client: Optional[ServiceNowClient] = None


def get_snow_client() -> Optional[ServiceNowClient]:
    global _snow_client
    if _snow_client is None:
        from app.config import get_settings
        s = get_settings()
        if s.servicenow_instance_url and s.servicenow_username:
            _snow_client = ServiceNowClient(
                s.servicenow_instance_url,
                s.servicenow_username,
                s.servicenow_password,
            )
    return _snow_client


def reset_snow_client() -> None:
    global _snow_client
    _snow_client = None

