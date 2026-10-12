"""
Router: Incident Copilot
POST /api/copilot/ask – Q&A over an analyzed incident using Claude
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import CopilotAnswer, CopilotQuestion

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask", response_model=CopilotAnswer, summary="Ask a question about an analyzed incident")
async def ask(payload: CopilotQuestion):
    from app.main import get_app_state
    from app.config import get_settings

    state = get_app_state()
    rca = state.get("all_results", {}).get(payload.incident_number)
    if not rca:
        raise HTTPException(
            status_code=404,
            detail=f"No RCA found for {payload.incident_number}. Analyze the incident first.",
        )

    settings = get_settings()

    if not settings.claude_api_key:
        # Local fallback answer
        answer = _local_fallback(payload.question, rca)
        return CopilotAnswer(
            incident_number=payload.incident_number,
            question=payload.question,
            answer=answer,
            sources=["local-rca"],
        )

    # Claude-powered answer
    try:
        import anthropic

        similar_text = "\n".join(
            f"- [{sc.case_id}] {sc.description} | Root cause: {sc.root_cause}"
            for sc in rca.similar_cases
        ) or "None"

        evidence_text = "\n".join(f"- {e}" for e in rca.evidence) or "None"

        system = (
            "You are a helpful incident analysis assistant. Answer questions concisely "
            "using ONLY the provided incident context. Do not speculate beyond the evidence."
        )

        user_msg = f"""## Incident Context
**Number**: {rca.incident_number}
**Probable Root Cause**: {rca.probable_root_cause}
**Confidence**: {rca.confidence_label} ({rca.confidence_score:.0%})
**Recommended Team**: {rca.recommended_team}

**Evidence Detected**:
{evidence_text}

**Similar Historical Cases**:
{similar_text}

**Recommended Actions**:
{chr(10).join('- ' + a for a in rca.recommended_actions)}

---
**Engineer Question**: {payload.question}

Answer based only on the above context. If the answer is not in the context, say so clearly."""

        client = anthropic.Anthropic(api_key=settings.claude_api_key)
        resp = client.messages.create(
            model=settings.claude_model,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        return CopilotAnswer(
            incident_number=payload.incident_number,
            question=payload.question,
            answer=resp.content[0].text.strip(),
            sources=[sc.case_id for sc in rca.similar_cases],
        )

    except Exception as exc:
        logger.error("Copilot error: %s", exc)
        return CopilotAnswer(
            incident_number=payload.incident_number,
            question=payload.question,
            answer=_local_fallback(payload.question, rca),
            sources=["local-rca"],
        )


def _local_fallback(question: str, rca) -> str:
    q = question.lower()
    if any(w in q for w in ["root cause", "cause", "why"]):
        return f"Probable root cause: {rca.probable_root_cause}"
    if any(w in q for w in ["team", "assign", "who"]):
        return f"Recommended assignment team: {rca.recommended_team}"
    if any(w in q for w in ["action", "fix", "resolve", "what to do"]):
        return "Recommended actions:\n" + "\n".join(f"• {a}" for a in rca.recommended_actions)
    if any(w in q for w in ["command", "diagnostic", "run"]):
        return "Diagnostic commands:\n" + "\n".join(
            f"• {c.command} — {c.description}" for c in rca.diagnostic_commands
        )
    if any(w in q for w in ["evidence", "log", "signal"]):
        return "Evidence detected:\n" + "\n".join(f"• {e}" for e in rca.evidence)
    if any(w in q for w in ["similar", "history", "before"]):
        if rca.similar_cases:
            return "Similar historical cases:\n" + "\n".join(
                f"• [{sc.case_id}] {sc.description[:100]}" for sc in rca.similar_cases
            )
        return "No closely matching historical cases were found."
    return (
        f"Based on the incident analysis: root cause is '{rca.probable_root_cause}' "
        f"with {rca.confidence_label} confidence. Recommended team: {rca.recommended_team}."
    )

