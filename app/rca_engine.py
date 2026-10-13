"""
RCA Assistant – RCA Engine
Supports two analysis modes:
  • local  – deterministic keyword/pattern matching (no external AI needed)
  • ai     – Claude (Anthropic) powered analysis grounded in evidence + KB cases
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from app.models import (
    DiagnosticCommand,
    IncidentInput,
    RCAResult,
    SimilarCase,
)

logger = logging.getLogger(__name__)

# ── Evidence extraction patterns ──────────────────────────────────────────────
_PATTERNS = {
    "OOM / Memory": [
        r"OutOfMemoryError", r"OOMKilled", r"exit code 137", r"heap space",
        r"Cannot allocate memory", r"MemoryError",
    ],
    "Database": [
        r"connection pool", r"too many connections", r"deadlock",
        r"query timeout", r"FATAL.*database", r"pg_connect", r"ORA-\d+",
    ],
    "Network / Connectivity": [
        r"Connection refused", r"Connection timed out", r"ECONNREFUSED",
        r"network policy", r"DNS resolution", r"socket timeout",
    ],
    "HTTP Errors": [
        r"HTTP 5\d\d", r"HTTP 4\d\d", r"503 Service Unavailable",
        r"502 Bad Gateway", r"504 Gateway Timeout",
    ],
    "Disk / Storage": [
        r"No space left on device", r"disk full", r"ENOSPC",
        r"write failed", r"I/O error",
    ],
    "SSL / Auth": [
        r"certificate expired", r"SSL handshake", r"401 Unauthorized",
        r"403 Forbidden", r"authentication failed",
    ],
    "Deployment": [
        r"CrashLoopBackOff", r"ImagePullBackOff", r"deployment failed",
        r"rollback", r"pod restart", r"container exit",
    ],
    "Performance": [
        r"high CPU", r"response time", r"latency", r"slow query",
        r"timeout exceeded",
    ],
    "Configuration": [
        r"misconfiguration", r"invalid config", r"environment variable",
        r"config map", r"missing key",
    ],
}

_TEAM_MAP = {
    "OOM / Memory": "Application Support",
    "Database": "Database Team",
    "Network / Connectivity": "Infrastructure Team",
    "HTTP Errors": "Application Support",
    "Disk / Storage": "Infrastructure Team",
    "SSL / Auth": "Security Team",
    "Deployment": "DevOps Team",
    "Performance": "Database Team",
    "Configuration": "DevOps Team",
}

_ACTION_MAP: Dict[str, List[str]] = {
    "OOM / Memory": [
        "Review pod memory limits and requests",
        "Check heap dump for memory leaks",
        "Inspect recent code deployments for memory regressions",
        "Enable garbage-collection logging",
        "Consider horizontal scaling to distribute load",
    ],
    "Database": [
        "Identify and kill long-running or blocking queries",
        "Check connection pool configuration and limits",
        "Review slow query log",
        "Consider adding read replicas or caching layer",
        "Verify database resource utilisation",
    ],
    "Network / Connectivity": [
        "Verify network policies and firewall rules",
        "Check DNS resolution for affected services",
        "Review recent infrastructure or namespace changes",
        "Test connectivity between affected services",
        "Check load-balancer health checks",
    ],
    "HTTP Errors": [
        "Review application error logs around the failure window",
        "Check upstream service health",
        "Inspect load-balancer and ingress configuration",
        "Verify API contracts between services",
        "Review recent deployment history",
    ],
    "Disk / Storage": [
        "Check disk utilisation on affected servers",
        "Review and fix log-rotation configuration",
        "Identify and remove large or orphaned files",
        "Add disk usage monitoring alerts",
        "Consider expanding persistent volume",
    ],
    "SSL / Auth": [
        "Check TLS certificate expiry dates",
        "Verify certificate renewal automation",
        "Review authentication provider logs",
        "Rotate credentials if compromise is suspected",
        "Add certificate expiry alerting",
    ],
    "Deployment": [
        "Review pod crash logs with kubectl logs",
        "Check image pull secrets and registry availability",
        "Inspect Kubernetes events for the affected namespace",
        "Roll back deployment if issue is release-related",
        "Verify resource limits for new pods",
    ],
    "Performance": [
        "Profile slow endpoints or queries",
        "Check for missing database indexes",
        "Review caching configuration",
        "Assess horizontal scaling options",
        "Analyse CPU and memory profiles",
    ],
    "Configuration": [
        "Compare environment-specific configurations",
        "Check CI/CD pipeline stage isolation",
        "Review ConfigMap and Secret values",
        "Enable configuration drift detection",
        "Validate all required environment variables are set",
    ],
}

_CMD_MAP: Dict[str, List[DiagnosticCommand]] = {
    "OOM / Memory": [
        DiagnosticCommand(command="kubectl describe pod <pod-name> -n <namespace>", description="Show resource limits and OOM events", requires_approval=False),
        DiagnosticCommand(command="kubectl top pods -n <namespace>", description="Show live CPU/memory usage", requires_approval=False),
        DiagnosticCommand(command="jcmd <pid> VM.native_memory summary", description="Show JVM native memory breakdown", requires_approval=True),
    ],
    "Database": [
        DiagnosticCommand(command="SELECT pid, query, state FROM pg_stat_activity WHERE wait_event_type='Lock';", description="Show blocked PostgreSQL queries", requires_approval=False),
        DiagnosticCommand(command="SHOW max_connections;", description="Show PostgreSQL connection limit", requires_approval=False),
        DiagnosticCommand(command="SELECT pg_terminate_backend(<pid>);", description="Terminate a blocking query — use with caution", requires_approval=True),
    ],
    "Network / Connectivity": [
        DiagnosticCommand(command="kubectl get networkpolicy -n <namespace>", description="List network policies in namespace", requires_approval=False),
        DiagnosticCommand(command="kubectl exec -it <pod> -- curl -v <service-url>", description="Test connectivity from inside the pod", requires_approval=False),
        DiagnosticCommand(command="nslookup <service-name>.<namespace>.svc.cluster.local", description="DNS resolution test", requires_approval=False),
    ],
    "Disk / Storage": [
        DiagnosticCommand(command="df -h", description="Check disk usage on host", requires_approval=False),
        DiagnosticCommand(command="du -sh /var/log/*", description="Show log directory sizes", requires_approval=False),
        DiagnosticCommand(command="find /var/log -name '*.log' -mtime +7 -delete", description="Remove logs older than 7 days — DESTRUCTIVE", requires_approval=True),
    ],
    "SSL / Auth": [
        DiagnosticCommand(command="openssl s_client -connect <host>:443 | openssl x509 -noout -dates", description="Check certificate validity dates", requires_approval=False),
        DiagnosticCommand(command="kubectl get secret <tls-secret> -n <namespace> -o jsonpath='{.data.tls\\.crt}' | base64 -d | openssl x509 -noout -dates", description="Check Kubernetes TLS secret expiry", requires_approval=False),
    ],
    "Deployment": [
        DiagnosticCommand(command="kubectl rollout history deployment/<name> -n <namespace>", description="Show deployment revision history", requires_approval=False),
        DiagnosticCommand(command="kubectl rollout undo deployment/<name> -n <namespace>", description="Roll back to previous deployment — requires approval", requires_approval=True),
        DiagnosticCommand(command="kubectl get events -n <namespace> --sort-by=.lastTimestamp", description="Show recent Kubernetes events", requires_approval=False),
    ],
}


def extract_evidence(incident: IncidentInput) -> Tuple[List[str], str]:
    """
    Scan incident text for known error patterns.
    Returns (list_of_evidence_strings, dominant_category).
    """
    full_text = " ".join([
        incident.short_description,
        incident.description,
        incident.logs,
        incident.recent_changes,
    ])

    category_scores: Dict[str, int] = {}
    evidence: List[str] = []

    for cat, patterns in _PATTERNS.items():
        for pat in patterns:
            matches = re.findall(pat, full_text, re.IGNORECASE)
            if matches:
                evidence.append(f"[{cat}] Pattern matched: '{pat}' ({len(matches)}x)")
                category_scores[cat] = category_scores.get(cat, 0) + len(matches)

    dominant_category = (
        max(category_scores, key=lambda k: category_scores[k])
        if category_scores
        else "General"
    )
    return evidence, dominant_category


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_similar_cases(
    incident: IncidentInput,
    cases: List[Dict[str, Any]],
    top_n: int = 3,
) -> List[SimilarCase]:
    """
    Score each historical case against the incident and return the top N.
    Scoring uses keyword overlap + text similarity on description.
    """
    incident_text = " ".join([
        incident.short_description,
        incident.description,
        incident.logs,
        incident.category,
    ]).lower()

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for case in cases:
        kw_score = sum(
            1 for kw in case.get("keywords", [])
            if kw.lower() in incident_text
        ) / max(len(case.get("keywords", [1])), 1)

        desc_score = _text_similarity(
            incident.short_description + " " + incident.description,
            case.get("description", "") + " " + case.get("root_cause", ""),
        )

        # Category bonus
        cat_bonus = 0.2 if incident.category.lower() == case.get("category", "").lower() else 0.0

        total = 0.5 * kw_score + 0.3 * desc_score + 0.2 * cat_bonus
        scored.append((total, case))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        SimilarCase(
            case_id=c.get("case_id", "?"),
            description=c.get("description", ""),
            root_cause=c.get("root_cause", ""),
            resolution=c.get("resolution", ""),
            similarity_score=round(score, 3),
            category=c.get("category", ""),
        )
        for score, c in scored[:top_n]
        if score >= 0.30
    ]


# ── Local mode analysis ───────────────────────────────────────────────────────

def local_analysis(
    incident: IncidentInput,
    similar_cases: List[SimilarCase],
) -> RCAResult:
    evidence, dominant_cat = extract_evidence(incident)

    # Confidence based on evidence count and similarity
    top_sim = similar_cases[0].similarity_score if similar_cases else 0.0
    evidence_score = min(len(evidence) / 6, 1.0)
    confidence = round(0.4 * top_sim + 0.6 * evidence_score, 2)
    confidence = max(0.1, min(confidence, 0.95))

    confidence_label = (
        "high" if confidence >= 0.7
        else "medium" if confidence >= 0.4
        else "low"
    )

    if similar_cases:
        root_cause = (
            f"Likely related to {dominant_cat}. "
            f"Most similar historical case ({similar_cases[0].case_id}): "
            f"{similar_cases[0].root_cause}"
        )
    elif dominant_cat != "General":
        root_cause = (
            f"Pattern analysis indicates a {dominant_cat} related failure. "
            f"Review the identified evidence signals for confirmation."
        )
    else:
        root_cause = (
            "No strong pattern match found. Requires manual investigation. "
            "Review application and infrastructure logs for further signals."
        )

    actions = _ACTION_MAP.get(dominant_cat, [
        "Review all recent changes to the affected system",
        "Collect full application and infrastructure logs",
        "Escalate to the appropriate support team for investigation",
    ])

    commands = _CMD_MAP.get(dominant_cat, [])
    team = _TEAM_MAP.get(dominant_cat, "L2 Support")

    return RCAResult(
        incident_number=incident.incident_number,
        probable_root_cause=root_cause,
        confidence_score=confidence,
        confidence_label=confidence_label,
        evidence=evidence[:10],
        recommended_team=team,
        recommended_actions=actions,
        diagnostic_commands=commands,
        similar_cases=similar_cases,
        analysis_mode="local",
    )


# ── AI-assisted mode analysis ─────────────────────────────────────────────────

async def ai_analysis(
    incident: IncidentInput,
    similar_cases: List[SimilarCase],
    api_key: str,
    model: str,
) -> RCAResult:
    """Use Claude to generate a grounded RCA from incident evidence."""
    try:
        import anthropic

        evidence, dominant_cat = extract_evidence(incident)

        similar_text = "\n".join(
            f"- [{sc.case_id}] {sc.description} | Root cause: {sc.root_cause} "
            f"| Resolution: {sc.resolution} | Similarity: {sc.similarity_score:.0%}"
            for sc in similar_cases
        ) or "No closely matching historical cases found."

        evidence_text = "\n".join(f"- {e}" for e in evidence) or "No specific error patterns detected."

        prompt = f"""You are an expert Site Reliability Engineer performing Root Cause Analysis.

## Incident Details
- **Number**: {incident.incident_number}
- **Short Description**: {incident.short_description}
- **Description**: {incident.description}
- **Category**: {incident.category}
- **Priority**: {incident.priority}
- **Application**: {incident.application or 'Not specified'}
- **Environment**: {incident.environment}
- **Recent Changes**: {incident.recent_changes or 'None reported'}

## Application / Infrastructure Logs
```
{incident.logs or 'No logs provided'}
```

## Detected Evidence Signals
{evidence_text}

## Similar Historical Cases
{similar_text}

## Your Task
Analyze this incident and provide a structured Root Cause Analysis JSON object.

Respond ONLY with a valid JSON object in this exact format:
{{
  "probable_root_cause": "Concise 1-3 sentence root cause explanation grounded strictly in the evidence",
  "confidence_score": 0.72,
  "evidence_used": ["evidence item 1", "evidence item 2"],
  "recommended_team": "Team Name",
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "diagnostic_commands": [
    {{"command": "traceroute ... or systemctl ...", "description": "Why run this", "requires_approval": false}}
  ]
}}

CRITICAL GROUNDING RULES:
1. STRICT GROUNDING: Base your analysis EXCLUSIVELY on the actual incident details and logs provided for incident {incident.incident_number}.
2. DO NOT borrow pod names, hostnames, service names (e.g., payment-api), change ticket numbers, or failure modes from historical cases if they do not exist in the current incident.
3. If the incident is about {incident.category} (e.g. Network/VPN), your root cause MUST address {incident.category}, NOT unrelated categories like Java heap OOM or Database pools!
4. The historical cases are only background references. If they are not relevant to the current symptoms, treat this as a NOVEL incident and diagnose solely from the reported logs and symptoms.
5. Provide diagnostic commands tailored specifically to the technology stack mentioned (e.g. for Network/VPN use ping, traceroute, ip route, netstat, systemctl, curl, etc.; do NOT suggest kubectl pod commands unless the incident is explicitly running on Kubernetes).
6. Set confidence_score honestly:
   - 0.80 - 0.95: ONLY if the logs provide clear, conclusive root cause proof or match a verified pattern.
   - 0.50 - 0.79: Probable root cause based on symptoms, but requires diagnostic command verification.
   - 0.20 - 0.49: Insufficient evidence or conflicting signals.
7. Flag any commands that are potentially destructive with requires_approval: true.
8. Do not suggest running commands automatically.
"""

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[^\n]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        import json
        data = json.loads(raw)

        confidence = float(data.get("confidence_score", 0.5))
        confidence_label = (
            "high" if confidence >= 0.7
            else "medium" if confidence >= 0.4
            else "low"
        )

        commands = [
            DiagnosticCommand(
                command=cmd.get("command", ""),
                description=cmd.get("description", ""),
                requires_approval=cmd.get("requires_approval", False),
            )
            for cmd in data.get("diagnostic_commands", [])
        ]

        return RCAResult(
            incident_number=incident.incident_number,
            probable_root_cause=data.get("probable_root_cause", "Unable to determine."),
            confidence_score=round(confidence, 2),
            confidence_label=confidence_label,
            evidence=data.get("evidence_used", evidence)[:10],
            recommended_team=data.get("recommended_team", "L2 Support"),
            recommended_actions=data.get("recommended_actions", []),
            diagnostic_commands=commands,
            similar_cases=similar_cases,
            analysis_mode="ai",
        )

    except Exception as exc:
        logger.error("Claude analysis failed: %s — falling back to local.", exc)
        return local_analysis(incident, similar_cases)


# ── Public entrypoint ─────────────────────────────────────────────────────────

async def analyze_incident(incident: IncidentInput) -> RCAResult:
    """
    Main entry point: retrieve KB cases, find similar ones, run analysis.
    """
    from app.config import get_settings
    from app.knowledge_base import get_knowledge_base

    settings = get_settings()
    kb = get_knowledge_base()
    all_cases = kb.get_all_cases()
    similar_cases = find_similar_cases(incident, all_cases)

    # Always use AI analysis mode when Claude API key is available
    if settings.claude_api_key:
        result = await ai_analysis(
            incident, similar_cases,
            api_key=settings.claude_api_key,
            model=settings.claude_model,
        )
    else:
        result = local_analysis(incident, similar_cases)

    logger.info(
        "RCA complete for %s: mode=%s confidence=%s team=%s",
        incident.incident_number,
        result.analysis_mode,
        result.confidence_label,
        result.recommended_team,
    )
    return result

