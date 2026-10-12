"""
RCA Assistant – Knowledge Base Loader
Loads the 20 candidate cases, deduplicates against existing, and stores unique ones in Firebase via API.
"""
import json
import urllib.request
import urllib.error
from difflib import SequenceMatcher

API_BASE = "http://localhost:8000"

# ── The 20 candidate cases ────────────────────────────────────────────────────
CANDIDATES = [
  {
    "case_id": "KC-CANDIDATE-001",
    "title": "/var filesystem full due to uncontrolled application log growth",
    "platform": "RHEL/Linux",
    "category": "Filesystem or disk-space exhaustion",
    "priority": "P2",
    "confirmed_root_cause": "Application entered an error loop causing log files in /var/log to grow continuously and exhaust filesystem space.",
    "resolution_steps": [{"action": "Archive or rotate oversized logs following change approval", "command_or_tool": "logrotate", "requires_approval": True}],
    "related_case_keywords": ["No space left on device", "df -h", "disk full", "log growth"],
    "symptoms": ["/var utilization exceeds threshold", "Application write failures", "Filesystem reports zero available space"],
    "log_messages": ["No space left on device", "write failed: No space left on device"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-002",
    "title": "CPU saturation caused by runaway application process",
    "platform": "RHEL/Linux",
    "category": "CPU, memory and load problems",
    "priority": "P2",
    "confirmed_root_cause": "Application process entered a processing loop after a malformed workload input.",
    "resolution_steps": [{"action": "Engage application owner and restart service according to approved procedure if required", "command_or_tool": "systemctl restart <service>", "requires_approval": True}],
    "related_case_keywords": ["high cpu", "load average", "top", "slow server"],
    "symptoms": ["High CPU utilization", "Elevated load average", "Slow user response times"],
    "log_messages": ["Application warning messages repeating at high frequency"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-003",
    "title": "Memory pressure caused by application memory leak",
    "platform": "RHEL/Linux",
    "category": "CPU, memory and load problems",
    "priority": "P2",
    "confirmed_root_cause": "Application failed to release allocated memory during transaction processing.",
    "resolution_steps": [{"action": "Apply vendor-approved fix or restart service under change control", "command_or_tool": "systemctl restart <service>", "requires_approval": True}],
    "related_case_keywords": ["memory leak", "OOM", "swap usage"],
    "symptoms": ["Steadily reducing free memory", "Swap utilization increasing", "Service response degradation"],
    "log_messages": ["Out of memory: Kill process"],
    "assignment_group": "Application Support",
  },
  {
    "case_id": "KC-CANDIDATE-004",
    "title": "LVM logical volume not mounted after storage presentation change",
    "platform": "RHEL/Linux",
    "category": "Storage latency, LVM and mount failures",
    "priority": "P2",
    "confirmed_root_cause": "Logical volume path changed during approved storage reconfiguration and fstab was not updated.",
    "resolution_steps": [{"action": "Update mount configuration according to approved storage documentation", "command_or_tool": "/etc/fstab", "requires_approval": True}],
    "related_case_keywords": ["lvm", "mount failure", "fstab", "mount: special device does not exist"],
    "symptoms": ["Mount point unavailable", "Application startup failures"],
    "log_messages": ["mount: special device does not exist"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-005",
    "title": "SSSD authentication failures due to expired AD trust credentials",
    "platform": "RHEL/Linux",
    "category": "Authentication, Active Directory, LDAP, Kerberos and SSSD",
    "priority": "P2",
    "confirmed_root_cause": "Machine account credentials no longer matched Active Directory trust relationship.",
    "resolution_steps": [{"action": "Re-establish domain trust following approved directory-services procedure", "command_or_tool": "realm", "requires_approval": True}],
    "related_case_keywords": ["sssd", "kerberos", "active directory", "Backend is offline", "Kerberos authentication failed"],
    "symptoms": ["Authentication denied for domain users", "Local accounts continue to work"],
    "log_messages": ["sssd: Backend is offline", "Kerberos authentication failed"],
    "assignment_group": "Security Team",
  },
  {
    "case_id": "KC-CANDIDATE-006",
    "title": "DNS resolution failures caused by unreachable configured resolver",
    "platform": "RHEL/Linux",
    "category": "DNS resolution",
    "priority": "P2",
    "confirmed_root_cause": "Primary configured DNS server became unreachable due to network path issue.",
    "resolution_steps": [{"action": "Restore resolver connectivity or update configuration through approved process", "command_or_tool": "NetworkManager configuration", "requires_approval": True}],
    "related_case_keywords": ["temporary failure in name resolution", "dns", "DNS lookup", "hostname"],
    "symptoms": ["Hostname lookups fail", "IP-based communication succeeds"],
    "log_messages": ["Temporary failure in name resolution"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-007",
    "title": "SSH access failure due to expired server certificate in SSH gateway workflow",
    "platform": "RHEL/Linux",
    "category": "Certificates and TLS",
    "priority": "P3",
    "confirmed_root_cause": "Required server certificate expired and was no longer trusted by access infrastructure.",
    "resolution_steps": [{"action": "Install renewed certificate through approved procedure", "command_or_tool": "openssl", "requires_approval": True}],
    "related_case_keywords": ["certificate expired", "ssh access", "certificate has expired"],
    "symptoms": ["Remote access rejected", "Certificate validation errors"],
    "log_messages": ["certificate has expired"],
    "assignment_group": "Security Team",
  },
  {
    "case_id": "KC-CANDIDATE-008",
    "title": "YUM or DNF patching failure due to repository metadata issues",
    "platform": "RHEL/Linux",
    "category": "Patching and package-management failures",
    "priority": "P3",
    "confirmed_root_cause": "Repository metadata publication failed on package management infrastructure.",
    "resolution_steps": [{"action": "Correct repository metadata and re-run patch cycle", "command_or_tool": "Repository management tooling", "requires_approval": True}],
    "related_case_keywords": ["dnf", "yum", "repo failure", "Failed to synchronize cache"],
    "symptoms": ["Package update failures", "Repository access errors"],
    "log_messages": ["Failed to synchronize cache for repo"],
    "assignment_group": "DevOps Team",
  },
  {
    "case_id": "KC-CANDIDATE-009",
    "title": "NTP synchronization failure causing Kerberos authentication issues",
    "platform": "RHEL/Linux",
    "category": "Time synchronization",
    "priority": "P2",
    "confirmed_root_cause": "NTP source became unreachable causing server clock drift beyond Kerberos tolerance.",
    "resolution_steps": [{"action": "Restore NTP source connectivity", "command_or_tool": "chronyd", "requires_approval": True}],
    "related_case_keywords": ["clock skew", "ntp", "chrony", "Clock skew too great", "kerberos"],
    "symptoms": ["Clock drift", "Kerberos authentication problems"],
    "log_messages": ["Clock skew too great"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-010",
    "title": "Backup failures caused by target filesystem capacity exhaustion",
    "platform": "RHEL/Linux",
    "category": "Backup failures",
    "priority": "P3",
    "confirmed_root_cause": "Backup repository reached capacity because retention expansion exceeded available storage.",
    "resolution_steps": [{"action": "Expand storage or adjust retention according to approved policy", "command_or_tool": "Backup management console", "requires_approval": True}],
    "related_case_keywords": ["backup failed", "storage full", "No space left on device"],
    "symptoms": ["Backup job failures", "Insufficient storage notifications"],
    "log_messages": ["No space left on device"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-011",
    "title": "Critical cron job not executing due to invalid crontab entry",
    "platform": "RHEL/Linux",
    "category": "Scheduled tasks and cron jobs",
    "priority": "P3",
    "confirmed_root_cause": "Cron entry contained invalid scheduling syntax introduced during maintenance.",
    "resolution_steps": [{"action": "Correct cron definition", "command_or_tool": "crontab -e", "requires_approval": True}],
    "related_case_keywords": ["cron", "scheduled task", "crontab"],
    "symptoms": ["Scheduled task absent from execution history"],
    "log_messages": ["CRON job not executed as expected"],
    "assignment_group": "DevOps Team",
  },
  {
    "case_id": "KC-CANDIDATE-012",
    "title": "Windows Server system drive exhausted by IIS log accumulation",
    "platform": "Windows/Wintel",
    "category": "Filesystem or disk-space exhaustion",
    "priority": "P2",
    "confirmed_root_cause": "IIS logs accumulated because archival controls were not executed.",
    "resolution_steps": [{"action": "Archive logs per approved retention policy", "command_or_tool": "IIS Manager", "requires_approval": True}],
    "related_case_keywords": ["iis logs", "c drive full", "Insufficient disk space", "disk full"],
    "symptoms": ["Low free disk space", "IIS warnings and application errors"],
    "log_messages": ["Insufficient disk space"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-013",
    "title": "Windows service failed to start because dependent service unavailable",
    "platform": "Windows/Wintel",
    "category": "Service and process failures",
    "priority": "P2",
    "confirmed_root_cause": "Required Windows service dependency failed during startup and blocked application service startup.",
    "resolution_steps": [{"action": "Restore dependent service and then start affected service", "command_or_tool": "Services console", "requires_approval": True}],
    "related_case_keywords": ["event 7001", "service failed", "dependency service", "The dependency service"],
    "symptoms": ["Application service stopped"],
    "log_messages": ["The dependency service or group failed to start"],
    "assignment_group": "Application Support",
  },
  {
    "case_id": "KC-CANDIDATE-014",
    "title": "RDP access failure caused by Remote Desktop Services stopped",
    "platform": "Windows/Wintel",
    "category": "Remote access through SSH or RDP",
    "priority": "P2",
    "confirmed_root_cause": "Remote Desktop Services was stopped after maintenance activity.",
    "resolution_steps": [{"action": "Start service following operational approval", "command_or_tool": "services.msc", "requires_approval": True}],
    "related_case_keywords": ["rdp unavailable", "Remote Desktop Services", "remote access"],
    "symptoms": ["RDP connection failure"],
    "log_messages": ["Remote Desktop Services entered stopped state"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-015",
    "title": "Windows Update installation failure due to insufficient system reserved space",
    "platform": "Windows/Wintel",
    "category": "Windows Update",
    "priority": "P3",
    "confirmed_root_cause": "Required update could not complete because reserved system partition capacity was insufficient.",
    "resolution_steps": [{"action": "Adjust partition per approved Microsoft guidance", "command_or_tool": "Disk Management", "requires_approval": True}],
    "related_case_keywords": ["windows update failed", "Update installation failed"],
    "symptoms": ["Update rollback", "Repeated installation failures"],
    "log_messages": ["Update installation failed"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-016",
    "title": "Antivirus real-time scanning causing application latency",
    "platform": "Windows/Wintel",
    "category": "Antivirus or endpoint-agent impact",
    "priority": "P2",
    "confirmed_root_cause": "Real-time antivirus scanning processed application data paths and introduced excessive storage latency.",
    "resolution_steps": [{"action": "Implement vendor-approved exclusions after security approval", "command_or_tool": "Endpoint protection console", "requires_approval": True}],
    "related_case_keywords": ["antivirus", "high latency", "disk queue", "scan impact"],
    "symptoms": ["High disk queue lengths", "Application latency"],
    "log_messages": ["Antivirus scan initiated"],
    "assignment_group": "Security Team",
  },
  {
    "case_id": "KC-CANDIDATE-017",
    "title": "Hyper-V guest performance degradation due to host CPU contention",
    "platform": "Windows/Wintel",
    "category": "Virtualization-related problems",
    "priority": "P2",
    "confirmed_root_cause": "One guest workload consumed disproportionate CPU resources on an oversubscribed host.",
    "resolution_steps": [{"action": "Rebalance workloads using approved virtualization procedures", "command_or_tool": "Hyper-V management tools", "requires_approval": True}],
    "related_case_keywords": ["hyper-v", "cpu contention", "oversubscription", "vm performance"],
    "symptoms": ["High host CPU utilization", "Multiple VM performance complaints"],
    "log_messages": ["Resource pressure warnings"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-018",
    "title": "Domain login failures caused by secure channel trust relationship issue",
    "platform": "Windows/Wintel",
    "category": "Authentication, Active Directory, LDAP, Kerberos and SSSD",
    "priority": "P2",
    "confirmed_root_cause": "Computer secure channel no longer matched Active Directory records.",
    "resolution_steps": [{"action": "Repair trust relationship using approved AD procedures", "command_or_tool": "Active Directory tools", "requires_approval": True}],
    "related_case_keywords": ["trust relationship failed", "domain login", "secure channel", "The trust relationship"],
    "symptoms": ["Domain authentication failures"],
    "log_messages": ["The trust relationship between this workstation and the primary domain failed"],
    "assignment_group": "Security Team",
  },
  {
    "case_id": "KC-CANDIDATE-019",
    "title": "Cross-platform application outage caused by enterprise DNS service failure",
    "platform": "Cross-platform",
    "category": "DNS resolution",
    "priority": "P1",
    "confirmed_root_cause": "Enterprise DNS service outage prevented hostname resolution across dependent applications.",
    "resolution_steps": [{"action": "Restore DNS platform according to approved operational procedures", "command_or_tool": "DNS management platform", "requires_approval": True}],
    "related_case_keywords": ["dns outage", "hostname lookup failure", "Temporary failure in name resolution", "DNS name does not exist"],
    "symptoms": ["Hostname failures on multiple platforms", "IP connectivity remains functional"],
    "log_messages": ["Temporary failure in name resolution", "DNS name does not exist"],
    "assignment_group": "Infrastructure Team",
  },
  {
    "case_id": "KC-CANDIDATE-020",
    "title": "Cross-platform authentication failures caused by time synchronization drift",
    "platform": "Cross-platform",
    "category": "Time synchronization",
    "priority": "P1",
    "confirmed_root_cause": "Enterprise time source became unavailable, leading to clock drift outside Kerberos tolerance across Linux and Windows systems.",
    "resolution_steps": [{"action": "Restore time synchronization service according to approved procedures", "command_or_tool": "chronyd and Windows Time Service", "requires_approval": True}],
    "related_case_keywords": ["clock skew", "kerberos failure", "time drift", "Clock skew too great", "Kerberos authentication failed"],
    "symptoms": ["Kerberos authentication failures", "Time offset alerts"],
    "log_messages": ["Clock skew too great", "Kerberos authentication failed"],
    "assignment_group": "Infrastructure Team",
  },
]


def api_get(path):
    r = urllib.request.urlopen(API_BASE + path)
    return json.loads(r.read())


def api_post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()}


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def transform_candidate(c):
    """Convert rich candidate format → simple KB case format used by rca_engine."""
    resolution_text = "; ".join(
        step.get("action", "") for step in c.get("resolution_steps", [])
    )
    keywords = list(set(
        c.get("related_case_keywords", []) +
        c.get("log_messages", [])[:3]
    ))
    return {
        "case_id": c["case_id"],
        "category": c["category"].split(",")[0].split("or")[0].strip().lower().replace(" ", "_"),
        "description": c["title"],
        "root_cause": c["confirmed_root_cause"],
        "resolution": resolution_text,
        "keywords": keywords,
        "assignment_group": c.get("assignment_group", "Infrastructure Team"),
        "platform": c.get("platform", ""),
        "priority": c.get("priority", "P2"),
        "symptoms": c.get("symptoms", []),
        "verified": True,
        "source": "structured_kb",
    }


def main():
    print("=" * 65)
    print("  RCA Assistant – Knowledge Base Loader")
    print("=" * 65)

    # 1. Fetch existing cases
    existing = api_get("/api/knowledge")
    existing_ids = {c.get("case_id") for c in existing}
    existing_descriptions = [c.get("description", "") for c in existing]

    print(f"\nExisting cases in KB: {len(existing)}")
    print(f"Candidate cases to evaluate: {len(CANDIDATES)}")
    print()

    # 2. Evaluate each candidate
    to_load = []
    skipped = []

    print(f"{'Case ID':<22} {'Status':<10} {'Reason'}")
    print("-" * 65)

    for cand in CANDIDATES:
        # Duplicate case_id check
        if cand["case_id"] in existing_ids:
            print(f"{cand['case_id']:<22} SKIP       Duplicate case_id")
            skipped.append((cand["case_id"], "duplicate case_id"))
            continue

        # Semantic similarity check (title vs existing descriptions)
        max_sim = max(
            (similarity(cand["title"], d) for d in existing_descriptions),
            default=0.0,
        )
        if max_sim >= 0.75:
            print(f"{cand['case_id']:<22} SKIP       Too similar ({max_sim:.0%}): {cand['title'][:40]}")
            skipped.append((cand["case_id"], f"similar {max_sim:.0%}"))
            continue

        print(f"{cand['case_id']:<22} UNIQUE     {cand['title'][:42]}")
        to_load.append(cand)

    print("-" * 65)
    print(f"\nUnique cases to load: {len(to_load)}")
    print(f"Skipped (duplicates): {len(skipped)}")

    if not to_load:
        print("\nNothing to load. KB is already up to date.")
        return

    # 3. Load unique cases into Firebase via API
    print("\nLoading into Firebase Firestore...")
    loaded = 0
    failed = 0

    for cand in to_load:
        kb_case = transform_candidate(cand)
        result = api_post("/api/knowledge", kb_case)
        if "case_id" in result and "error" not in result:
            print(f"  [OK] {kb_case['case_id']} – {kb_case['description'][:50]}")
            loaded += 1
        else:
            print(f"  [FAIL] {kb_case['case_id']} – {result}")
            failed += 1

    # 4. Final stats
    print()
    final = api_get("/api/knowledge/stats")
    print("=" * 65)
    print(f"  Loaded:         {loaded} new cases")
    print(f"  Failed:         {failed}")
    print(f"  Skipped:        {len(skipped)}")
    print(f"  Total KB cases: {final['total_cases']}")
    print(f"  Firebase:       {'Connected' if final['firebase_connected'] else 'In-Memory'}")
    print("=" * 65)


if __name__ == "__main__":
    main()

