"""
RCA Assistant – Synthetic Incident Generator
Produces realistic-looking demo incidents for recurring scheduler demos.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Dict, List

from app.models import IncidentInput

_TEMPLATES: List[Dict[str, str]] = [
    {
        "short_description": "Production service OOMKilled – payment-api pods restarting",
        "description": "The payment-api deployment in the prod namespace is experiencing repeated pod restarts. Kubernetes reports OOMKilled with exit code 137. Heap dumps show memory growing steadily over 6 hours before eviction.",
        "category": "memory",
        "priority": "1 - Critical",
        "logs": "java.lang.OutOfMemoryError: Java heap space\n\tat java.util.Arrays.copyOf(Arrays.java:3210)\n\tat org.springframework.core.ResolvableType.getGenerics(ResolvableType.java:561)\nOOMKilled exit code 137\nkubernetes: pod payment-api-7d9f6b5c4-xkp2q restarted 8 times",
        "recent_changes": "Heap size reduced from -Xmx4g to -Xmx2g in last deployment (ticket CHG0045678)",
        "application": "payment-api",
    },
    {
        "short_description": "HTTP 503 errors on order-service – database connection pool exhausted",
        "description": "Users are experiencing 503 Service Unavailable errors when placing orders. Application logs show HikariCP connection pool at maximum capacity. Database queries are taking over 30 seconds.",
        "category": "database",
        "priority": "2 - High",
        "logs": "HikariPool-1 - Connection is not available, request timed out after 30000ms\ncom.zaxxer.hikari.pool.HikariPool: Pool stats (total=50, active=50, idle=0, waiting=23)\nHTTP 503 Service Unavailable\norg.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved for non-replication superuser connections",
        "recent_changes": "Database maintenance window last night; max_connections parameter not restored",
        "application": "order-service",
    },
    {
        "short_description": "SSL certificate expired – API gateway returning 401",
        "description": "API Gateway is rejecting all HTTPS requests with SSL handshake failures. Certificate expiry date was 2024-11-01. Auto-renewal via cert-manager did not execute due to a misconfiguration in the ClusterIssuer.",
        "category": "authentication",
        "priority": "1 - Critical",
        "logs": "SSL_ERROR_RX_RECORD_TOO_LONG\nERR_CERT_DATE_INVALID\nTLS handshake failed: certificate has expired\nHTTP 401 Unauthorized\ncert-manager: ClusterIssuer 'letsencrypt-prod' is not ready: ACME account not registered",
        "recent_changes": "ClusterIssuer updated 2 weeks ago to change ACME email address",
        "application": "api-gateway",
    },
    {
        "short_description": "Disk space full on app-server-03 – log writes failing",
        "description": "Application servers are unable to write logs. Monitoring alerts show /var partition at 100% capacity. logrotate has not been running due to a cron misconfiguration applied last month.",
        "category": "storage",
        "priority": "2 - High",
        "logs": "No space left on device (ENOSPC)\nOSError: [Errno 28] No space left on device: '/var/log/app/app.log'\ndu -sh: /var/log 47G\ndf -h: /dev/sda1 100% /var",
        "recent_changes": "Logrotate configuration updated by automation script on 2024-10-01",
        "application": "app-server-03",
    },
    {
        "short_description": "Network policy blocking inter-service calls after namespace migration",
        "description": "The inventory-service cannot reach the catalogue-service after the namespace migration completed this morning. ECONNREFUSED errors are appearing in service mesh logs. All other services in the new namespace are healthy.",
        "category": "network",
        "priority": "2 - High",
        "logs": "Error: connect ECONNREFUSED catalogue-service.apps-v2.svc.cluster.local:8080\nkubectl get networkpolicy: deny-all-ingress (applies to all pods)\nno matching allow rule found for source inventory-service\nHTTP 503: upstream connect error",
        "recent_changes": "Namespace renamed from 'apps' to 'apps-v2' during migration; network policies not updated",
        "application": "inventory-service",
    },
    {
        "short_description": "CrashLoopBackOff after deployment – config map missing key",
        "description": "The reporting-service pods are in CrashLoopBackOff state following the latest deployment. Container exits immediately with code 1. Startup logs show a missing required environment variable DATABASE_REPLICA_URL.",
        "category": "deployment",
        "priority": "2 - High",
        "logs": "Error: Required environment variable DATABASE_REPLICA_URL is not set\nProcess exited with code 1\nkubernetes: Back-off restarting failed container\nCrashLoopBackOff: restart count 15",
        "recent_changes": "New ConfigMap deployed for reporting-service; DATABASE_REPLICA_URL not included",
        "application": "reporting-service",
    },
    {
        "short_description": "High CPU usage – missing index causing full table scan",
        "description": "The analytics dashboard is timing out and CPU on the primary database server is at 95%. Slow query log shows a report query taking 45+ seconds, performing a full table scan on the events table with 80M rows.",
        "category": "performance",
        "priority": "3 - Moderate",
        "logs": "Query_time: 47.234 Lock_time: 0.001 Rows_examined: 81234567\nSELECT * FROM events WHERE tenant_id = ? AND created_at > ? ORDER BY created_at\nEXPLAIN: type=ALL (full table scan), rows=81234567\nCPU: 95.2% (db-primary-01)",
        "recent_changes": "Schema migration last week added tenant_id column; index was not created",
        "application": "analytics-api",
    },
]


def generate_incident(prefix: str = "INC") -> IncidentInput:
    template = random.choice(_TEMPLATES)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    number = f"{prefix}{random.randint(1000000, 9999999)}"

    return IncidentInput(
        incident_number=number,
        short_description=template["short_description"],
        description=template["description"],
        category=template["category"],
        priority=template["priority"],
        logs=template["logs"],
        recent_changes=template["recent_changes"],
        application=template["application"],
        environment="production",
    )

