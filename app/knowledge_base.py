"""
RCA Assistant – Firebase Knowledge Base Service
Stores and retrieves verified historical incident cases using Firestore.
Falls back gracefully to in-memory storage when Firebase is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── In-memory seed data (bundled historical cases) ───────────────────────────
SEED_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "HIST-001",
        "category": "memory",
        "description": "Java heap space exhaustion causing OOMKilled pods with exit code 137",
        "root_cause": "JVM heap limit set too low for peak traffic; memory leak in connection pool.",
        "resolution": "Increased pod memory limits to 4Gi, updated heap flags to -Xmx3g, patched connection pool leak.",
        "keywords": ["OutOfMemoryError", "heap", "OOMKilled", "137", "java", "memory"],
        "assignment_group": "Application Support",
        "verified": True,
        "created_at": "2024-01-15T10:00:00Z",
    },
    {
        "case_id": "HIST-002",
        "category": "database",
        "description": "PostgreSQL connection pool exhaustion causing HTTP 503 responses",
        "root_cause": "Max connection limit reached due to long-running queries blocking connection release.",
        "resolution": "Killed blocking queries, increased max_connections, added PgBouncer pooler.",
        "keywords": ["503", "connection pool", "postgresql", "database", "timeout"],
        "assignment_group": "Database Team",
        "verified": True,
        "created_at": "2024-02-03T08:30:00Z",
    },
    {
        "case_id": "HIST-003",
        "category": "network",
        "description": "Kubernetes pod network policy blocking inter-service communication",
        "root_cause": "Newly applied network policy denied egress to internal services after a namespace migration.",
        "resolution": "Updated NetworkPolicy to allow correct egress rules; re-applied namespace labels.",
        "keywords": ["network policy", "kubernetes", "pod", "connection refused", "namespace"],
        "assignment_group": "Infrastructure Team",
        "verified": True,
        "created_at": "2024-02-20T14:15:00Z",
    },
    {
        "case_id": "HIST-004",
        "category": "deployment",
        "description": "Rolling deployment caused HTTP 500 errors due to incompatible API schema change",
        "root_cause": "New service version introduced a breaking REST API change without backward compatibility.",
        "resolution": "Rolled back deployment, added API versioning, implemented feature flag for gradual rollout.",
        "keywords": ["500", "deployment", "api", "rollback", "schema", "breaking change"],
        "assignment_group": "Application Support",
        "verified": True,
        "created_at": "2024-03-10T11:45:00Z",
    },
    {
        "case_id": "HIST-005",
        "category": "storage",
        "description": "Disk space exhaustion on application servers causing write failures",
        "root_cause": "Log rotation misconfigured; logs accumulated over weeks filling the /var partition.",
        "resolution": "Cleared old logs, fixed logrotate config, added disk usage alerts.",
        "keywords": ["disk full", "no space", "write failed", "storage", "log rotation", "partition"],
        "assignment_group": "Infrastructure Team",
        "verified": True,
        "created_at": "2024-03-28T16:20:00Z",
    },
    {
        "case_id": "HIST-006",
        "category": "authentication",
        "description": "Authentication failures after SSL certificate expiration",
        "root_cause": "TLS certificate expired; renewal automation failed silently.",
        "resolution": "Renewed certificate manually, fixed auto-renewal cronjob, added certificate expiry alerting.",
        "keywords": ["ssl", "tls", "certificate", "expired", "authentication", "401", "handshake"],
        "assignment_group": "Security Team",
        "verified": True,
        "created_at": "2024-04-05T09:00:00Z",
    },
    {
        "case_id": "HIST-007",
        "category": "performance",
        "description": "High CPU usage causing application slowdown and increased response times",
        "root_cause": "Unoptimised SQL query running full table scan due to missing index after schema migration.",
        "resolution": "Added composite index on queried columns; query execution time dropped from 8s to 50ms.",
        "keywords": ["cpu", "slow", "performance", "response time", "sql", "index", "query"],
        "assignment_group": "Database Team",
        "verified": True,
        "created_at": "2024-04-22T13:30:00Z",
    },
    {
        "case_id": "HIST-008",
        "category": "configuration",
        "description": "Service misconfiguration after environment variable override in production",
        "root_cause": "CI/CD pipeline incorrectly promoted staging environment variables to production.",
        "resolution": "Reverted environment variables, fixed pipeline stage isolation, added config drift detection.",
        "keywords": ["configuration", "environment variable", "cicd", "staging", "production", "misconfiguration"],
        "assignment_group": "DevOps Team",
        "verified": True,
        "created_at": "2024-05-14T10:10:00Z",
    },
]


class FirebaseKnowledgeBase:
    """
    Firestore-backed knowledge base with in-memory fallback.
    """

    def __init__(self, service_account_path: str = "", project_id: str = ""):
        self._db = None
        self._collection = "rca_knowledge_base"
        self._in_memory: List[Dict[str, Any]] = list(SEED_CASES)
        self._firebase_ready = False

        if service_account_path and os.path.exists(service_account_path):
            self._init_firebase(service_account_path, project_id)
        else:
            logger.warning(
                "Firebase service account not found at '%s'. "
                "Using in-memory knowledge base.",
                service_account_path,
            )

    def _init_firebase(self, service_account_path: str, project_id: str) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                options: Dict[str, Any] = {}
                if project_id:
                    options["projectId"] = project_id
                firebase_admin.initialize_app(credential=cred, options=options or None)

            self._db = firestore.client()
            self._firebase_ready = True
            logger.info("Firebase Firestore connected (project: %s).", project_id or "default")

            # Seed Firestore if the collection is empty
            self._seed_firestore()
        except Exception as exc:
            logger.error("Firebase init failed: %s — falling back to in-memory.", exc)
            self._firebase_ready = False

    def _seed_firestore(self) -> None:
        """Write seed cases to Firestore if collection is empty."""
        try:
            col_ref = self._db.collection(self._collection)
            if len(col_ref.limit(1).get()) == 0:
                for case in SEED_CASES:
                    col_ref.document(case["case_id"]).set(case)
                logger.info("Seeded %d historical cases into Firestore.", len(SEED_CASES))
        except Exception as exc:
            logger.warning("Could not seed Firestore: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_all_cases(self) -> List[Dict[str, Any]]:
        if self._firebase_ready:
            try:
                docs = self._db.collection(self._collection).stream()
                return [doc.to_dict() for doc in docs]
            except Exception as exc:
                logger.warning("Firestore read failed: %s — using in-memory.", exc)
        return list(self._in_memory)

    def add_case(self, case: Dict[str, Any]) -> str:
        case_id = case.get("case_id") or f"CASE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        case["case_id"] = case_id
        case["created_at"] = datetime.utcnow().isoformat() + "Z"

        if self._firebase_ready:
            try:
                self._db.collection(self._collection).document(case_id).set(case)
                logger.info("Saved case %s to Firestore.", case_id)
                return case_id
            except Exception as exc:
                logger.warning("Firestore write failed: %s — saving to in-memory.", exc)

        # Fallback: update in-memory list
        self._in_memory = [c for c in self._in_memory if c.get("case_id") != case_id]
        self._in_memory.append(case)
        return case_id

    def count(self) -> int:
        return len(self.get_all_cases())

    @property
    def is_firebase_connected(self) -> bool:
        return self._firebase_ready


# ── Module-level singleton ────────────────────────────────────────────────────
_kb_instance: Optional[FirebaseKnowledgeBase] = None


def get_knowledge_base() -> FirebaseKnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        from app.config import get_settings
        s = get_settings()
        _kb_instance = FirebaseKnowledgeBase(
            service_account_path=s.firebase_service_account_path,
            project_id=s.firebase_project_id,
        )
    return _kb_instance

