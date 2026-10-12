"""
Router: Knowledge Base
GET  /api/knowledge          – list all cases
GET  /api/knowledge/{id}     – get single case
POST /api/knowledge          – add a case manually
DELETE /api/knowledge/{id}   – remove a case (in-memory only)
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.knowledge_base import get_knowledge_base

router = APIRouter()


@router.get("", summary="List all knowledge base cases")
async def list_cases() -> List[Dict[str, Any]]:
    kb = get_knowledge_base()
    return kb.get_all_cases()


@router.get("/stats", summary="Knowledge base statistics")
async def kb_stats():
    kb = get_knowledge_base()
    cases = kb.get_all_cases()
    categories = {}
    for c in cases:
        cat = c.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    return {
        "total_cases": len(cases),
        "firebase_connected": kb.is_firebase_connected,
        "categories": categories,
    }


@router.get("/{case_id}", summary="Get a single knowledge case")
async def get_case(case_id: str):
    kb = get_knowledge_base()
    for case in kb.get_all_cases():
        if case.get("case_id") == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")


@router.post("", summary="Add a knowledge case manually")
async def add_case(case: Dict[str, Any]):
    kb = get_knowledge_base()
    case_id = kb.add_case(case)
    return {"success": True, "case_id": case_id}

