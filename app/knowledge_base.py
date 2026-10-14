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
    {
        "case_id": 'KC-CANDIDATE-001',
        "category": 'filesystem',
        "description": '/var filesystem full due to uncontrolled application log growth',
        "root_cause": 'Application entered an error loop causing log files in /var/log to grow continuously and exhaust filesystem space.',
        "resolution": 'Archive or rotate oversized logs following change approval',
        "keywords": ['write failed: No space left on device', 'log growth', 'No space left on device', 'df -h', 'disk full'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['/var utilization exceeds threshold', 'Application write failures', 'Filesystem reports zero available space'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-002',
        "category": 'cpu',
        "description": 'CPU saturation caused by runaway application process',
        "root_cause": 'Application process entered a processing loop after a malformed workload input.',
        "resolution": 'Engage application owner and restart service according to approved procedure if required',
        "keywords": ['Application warning messages repeating at high frequency', 'slow server', 'load average', 'high cpu', 'top'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['High CPU utilization', 'Elevated load average', 'Slow user response times'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-003',
        "category": 'cpu',
        "description": 'Memory pressure caused by application memory leak',
        "root_cause": 'Application failed to release allocated memory during transaction processing.',
        "resolution": 'Apply vendor-approved fix or restart service under change control',
        "keywords": ['Out of memory: Kill process', 'OOM', 'swap usage', 'memory leak'],
        "assignment_group": 'Application Support',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['Steadily reducing free memory', 'Swap utilization increasing', 'Service response degradation'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-004',
        "category": 'st',
        "description": 'LVM logical volume not mounted after storage presentation change',
        "root_cause": 'Logical volume path changed during approved storage reconfiguration and fstab was not updated.',
        "resolution": 'Update mount configuration according to approved storage documentation',
        "keywords": ['mount failure', 'fstab', 'lvm', 'mount: special device does not exist'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['Mount point unavailable', 'Application startup failures'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-005',
        "category": 'authentication',
        "description": 'SSSD authentication failures due to expired AD trust credentials',
        "root_cause": 'Machine account credentials no longer matched Active Directory trust relationship.',
        "resolution": 'Re-establish domain trust following approved directory-services procedure',
        "keywords": ['active directory', 'kerberos', 'Kerberos authentication failed', 'sssd: Backend is offline', 'sssd', 'Backend is offline'],
        "assignment_group": 'Security Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['Authentication denied for domain users', 'Local accounts continue to work'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-006',
        "category": 'dns_resolution',
        "description": 'DNS resolution failures caused by unreachable configured resolver',
        "root_cause": 'Primary configured DNS server became unreachable due to network path issue.',
        "resolution": 'Restore resolver connectivity or update configuration through approved process',
        "keywords": ['hostname', 'dns', 'Temporary failure in name resolution', 'temporary failure in name resolution', 'DNS lookup'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['Hostname lookups fail', 'IP-based communication succeeds'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-007',
        "category": 'certificates_and_tls',
        "description": 'SSH access failure due to expired server certificate in SSH gateway workflow',
        "root_cause": 'Required server certificate expired and was no longer trusted by access infrastructure.',
        "resolution": 'Install renewed certificate through approved procedure',
        "keywords": ['ssh access', 'certificate expired', 'certificate has expired'],
        "assignment_group": 'Security Team',
        "platform": 'RHEL/Linux',
        "priority": 'P3',
        "symptoms": ['Remote access rejected', 'Certificate validation errors'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-008',
        "category": 'patching_and_package-management_failures',
        "description": 'YUM or DNF patching failure due to repository metadata issues',
        "root_cause": 'Repository metadata publication failed on package management infrastructure.',
        "resolution": 'Correct repository metadata and re-run patch cycle',
        "keywords": ['Failed to synchronize cache', 'yum', 'Failed to synchronize cache for repo', 'dnf', 'repo failure'],
        "assignment_group": 'DevOps Team',
        "platform": 'RHEL/Linux',
        "priority": 'P3',
        "symptoms": ['Package update failures', 'Repository access errors'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-009',
        "category": 'time_synchronization',
        "description": 'NTP synchronization failure causing Kerberos authentication issues',
        "root_cause": 'NTP source became unreachable causing server clock drift beyond Kerberos tolerance.',
        "resolution": 'Restore NTP source connectivity',
        "keywords": ['ntp', 'kerberos', 'clock skew', 'Clock skew too great', 'chrony'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P2',
        "symptoms": ['Clock drift', 'Kerberos authentication problems'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-010',
        "category": 'backup_failures',
        "description": 'Backup failures caused by target filesystem capacity exhaustion',
        "root_cause": 'Backup repository reached capacity because retention expansion exceeded available storage.',
        "resolution": 'Expand storage or adjust retention according to approved policy',
        "keywords": ['backup failed', 'storage full', 'No space left on device'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'RHEL/Linux',
        "priority": 'P3',
        "symptoms": ['Backup job failures', 'Insufficient storage notifications'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-011',
        "category": 'scheduled_tasks_and_cron_jobs',
        "description": 'Critical cron job not executing due to invalid crontab entry',
        "root_cause": 'Cron entry contained invalid scheduling syntax introduced during maintenance.',
        "resolution": 'Correct cron definition',
        "keywords": ['crontab', 'cron', 'CRON job not executed as expected', 'scheduled task'],
        "assignment_group": 'DevOps Team',
        "platform": 'RHEL/Linux',
        "priority": 'P3',
        "symptoms": ['Scheduled task absent from execution history'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-012',
        "category": 'filesystem',
        "description": 'Windows Server system drive exhausted by IIS log accumulation',
        "root_cause": 'IIS logs accumulated because archival controls were not executed.',
        "resolution": 'Archive logs per approved retention policy',
        "keywords": ['c drive full', 'iis logs', 'Insufficient disk space', 'disk full'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['Low free disk space', 'IIS warnings and application errors'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-013',
        "category": 'service_and_process_failures',
        "description": 'Windows service failed to start because dependent service unavailable',
        "root_cause": 'Required Windows service dependency failed during startup and blocked application service startup.',
        "resolution": 'Restore dependent service and then start affected service',
        "keywords": ['The dependency service', 'The dependency service or group failed to start', 'event 7001', 'service failed', 'dependency service'],
        "assignment_group": 'Application Support',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['Application service stopped'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-014',
        "category": 'remote_access_through_ssh',
        "description": 'RDP access failure caused by Remote Desktop Services stopped',
        "root_cause": 'Remote Desktop Services was stopped after maintenance activity.',
        "resolution": 'Start service following operational approval',
        "keywords": ['remote access', 'Remote Desktop Services', 'Remote Desktop Services entered stopped state', 'rdp unavailable'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['RDP connection failure'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-015',
        "category": 'windows_update',
        "description": 'Windows Update installation failure due to insufficient system reserved space',
        "root_cause": 'Required update could not complete because reserved system partition capacity was insufficient.',
        "resolution": 'Adjust partition per approved Microsoft guidance',
        "keywords": ['windows update failed', 'Update installation failed'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Windows/Wintel',
        "priority": 'P3',
        "symptoms": ['Update rollback', 'Repeated installation failures'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-016',
        "category": 'antivirus',
        "description": 'Antivirus real-time scanning causing application latency',
        "root_cause": 'Real-time antivirus scanning processed application data paths and introduced excessive storage latency.',
        "resolution": 'Implement vendor-approved exclusions after security approval',
        "keywords": ['scan impact', 'disk queue', 'antivirus', 'Antivirus scan initiated', 'high latency'],
        "assignment_group": 'Security Team',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['High disk queue lengths', 'Application latency'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-017',
        "category": 'virtualization-related_problems',
        "description": 'Hyper-V guest performance degradation due to host CPU contention',
        "root_cause": 'One guest workload consumed disproportionate CPU resources on an oversubscribed host.',
        "resolution": 'Rebalance workloads using approved virtualization procedures',
        "keywords": ['cpu contention', 'Resource pressure warnings', 'vm performance', 'hyper-v', 'oversubscription'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['High host CPU utilization', 'Multiple VM performance complaints'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-018',
        "category": 'authentication',
        "description": 'Domain login failures caused by secure channel trust relationship issue',
        "root_cause": 'Computer secure channel no longer matched Active Directory records.',
        "resolution": 'Repair trust relationship using approved AD procedures',
        "keywords": ['The trust relationship between this workstation and the primary domain failed', 'domain login', 'secure channel', 'trust relationship failed', 'The trust relationship'],
        "assignment_group": 'Security Team',
        "platform": 'Windows/Wintel',
        "priority": 'P2',
        "symptoms": ['Domain authentication failures'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-019',
        "category": 'dns_resolution',
        "description": 'Cross-platform application outage caused by enterprise DNS service failure',
        "root_cause": 'Enterprise DNS service outage prevented hostname resolution across dependent applications.',
        "resolution": 'Restore DNS platform according to approved operational procedures',
        "keywords": ['hostname lookup failure', 'dns outage', 'Temporary failure in name resolution', 'DNS name does not exist'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Cross-platform',
        "priority": 'P1',
        "symptoms": ['Hostname failures on multiple platforms', 'IP connectivity remains functional'],
        "verified": True,
        "source": 'structured_kb',
    },
    {
        "case_id": 'KC-CANDIDATE-020',
        "category": 'time_synchronization',
        "description": 'Cross-platform authentication failures caused by time synchronization drift',
        "root_cause": 'Enterprise time source became unavailable, leading to clock drift outside Kerberos tolerance across Linux and Windows systems.',
        "resolution": 'Restore time synchronization service according to approved procedures',
        "keywords": ['kerberos failure', 'clock skew', 'Kerberos authentication failed', 'Clock skew too great', 'time drift'],
        "assignment_group": 'Infrastructure Team',
        "platform": 'Cross-platform',
        "priority": 'P1',
        "symptoms": ['Kerberos authentication failures', 'Time offset alerts'],
        "verified": True,
        "source": 'structured_kb',
    }

]


class FirebaseKnowledgeBase:
    """
    Firestore-backed knowledge base with in-memory fallback.
    """

    def __init__(self, service_account_path: str = "", project_id: str = ""):
        self._db = None
        self._collection = "rca_knowledge_base"
        self._history_collection = "rca_analysis_history"
        self._in_memory: List[Dict[str, Any]] = list(SEED_CASES)
        self._in_memory_history: Dict[str, Dict[str, Any]] = {}
        self._firebase_ready = False

        sa_json_env = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if sa_json_env:
            try:
                cert_data = json.loads(sa_json_env)
                self._init_firebase(cert_data, project_id)
                return
            except Exception as e:
                logger.warning("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON: %s", e)

        # Check standard and Render secret file paths
        candidate_paths = [
            service_account_path,
            "/etc/secrets/firebase-service-account.json",
            "firebase-service-account.json",
        ]
        chosen_path = next((p for p in candidate_paths if p and os.path.exists(p)), None)

        if chosen_path:
            self._init_firebase(chosen_path, project_id)
        else:
            logger.warning(
                "Firebase service account not found. Using in-memory knowledge base."
            )

    def _init_firebase(self, cred_source: Any, project_id: str) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_source)
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

    def save_analysis_result(self, rca_dict: Dict[str, Any]) -> None:
        """
        Persist an incident RCA analysis result to Firestore collection rca_analysis_history.
        """
        incident_number = rca_dict.get("incident_number", "UNKNOWN")
        analyzed_at = rca_dict.get("analyzed_at")
        if isinstance(analyzed_at, datetime):
            rca_dict["analyzed_at"] = analyzed_at.isoformat()
        elif not analyzed_at:
            rca_dict["analyzed_at"] = datetime.utcnow().isoformat()

        if self._firebase_ready:
            try:
                self._db.collection(self._history_collection).document(incident_number).set(rca_dict)
                logger.info("Saved analysis for %s to Firestore rca_analysis_history.", incident_number)
            except Exception as exc:
                logger.warning("Failed to save analysis to Firestore: %s — saving to in-memory.", exc)

        self._in_memory_history[incident_number] = rca_dict

    def get_all_analysis_results(self) -> List[Dict[str, Any]]:
        """
        Retrieve all past incident analyses from Firestore.
        """
        if self._firebase_ready:
            try:
                docs = self._db.collection(self._history_collection).stream()
                results = [doc.to_dict() for doc in docs]
                for r in results:
                    inc_num = r.get("incident_number")
                    if inc_num:
                        self._in_memory_history[inc_num] = r
                return results
            except Exception as exc:
                logger.warning("Failed to read analysis history from Firestore: %s — using in-memory.", exc)
        return list(self._in_memory_history.values())

    def get_analysis_result(self, incident_number: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single past analysis result from Firestore.
        """
        if self._firebase_ready:
            try:
                doc = self._db.collection(self._history_collection).document(incident_number).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as exc:
                logger.warning("Failed to fetch analysis for %s from Firestore: %s", incident_number, exc)
        return self._in_memory_history.get(incident_number)


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

