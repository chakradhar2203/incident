"""
RCA Assistant – Comprehensive Test Suite
Runs end-to-end tests across all core capabilities:
  1. System Health Check
  2. Configuration & Credentials Status
  3. Firebase Firestore Knowledge Base
  4. Claude AI / Grounded RCA Analysis
  5. Grounded Incident Copilot Q&A
  6. Engineer RCA Decision (Accept/Reject)
  7. Auto-Publishing Resolved Incident to Firebase KB
  8. Synthetic Incident Generator
"""
import json
import urllib.request
import urllib.error
import sys

API_BASE = "http://127.0.0.1:8080"


def print_header(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def api_call(endpoint, method="GET", data=None):
    url = f"{API_BASE}{endpoint}"
    encoded = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return json.loads(body), e.code
        except Exception:
            return {"error": body}, e.code
    except Exception as e:
        return {"error": str(e)}, 500


def test_health():
    print("[1/8] Testing System Health Check...")
    data, code = api_call("/health")
    if code == 200 and data.get("status") == "ok":
        print(f"      Status: OK (Version: {data.get('version')})")
        return True
    print(f"      FAILED: {data}")
    return False


def test_config():
    print("[2/8] Testing Configuration & Credentials...")
    data, code = api_call("/api/config")
    if code != 200:
        print(f"      FAILED to fetch config: {data}")
        return False

    claude_ok = data.get("claude_configured", False)
    fb_ok = data.get("firebase_configured", False)
    mode = data.get("analysis_mode", "local")
    sn_url = data.get("servicenow_instance_url") or "Not set"

    print(f"      Analysis Mode : {mode.upper()}")
    print(f"      Claude API    : {'CONFIGURED' if claude_ok else 'NOT SET'}")
    print(f"      Firebase KB   : {'CONNECTED' if fb_ok else 'IN-MEMORY'}")
    print(f"      ServiceNow URL: {sn_url}")
    return True


def test_knowledge_base():
    print("[3/8] Testing Firebase Firestore Knowledge Base...")
    data, code = api_call("/api/knowledge/stats")
    if code != 200:
        print(f"      FAILED to fetch KB stats: {data}")
        return False

    total = data.get("total_cases", 0)
    fb_conn = data.get("firebase_connected", False)
    cats = len(data.get("categories", {}))
    print(f"      Total Knowledge Cases: {total}")
    print(f"      Firestore Connected  : {'YES' if fb_conn else 'NO'}")
    print(f"      Distinct Categories  : {cats}")
    return total > 0


def test_rca_analysis():
    print("[4/8] Testing Grounded RCA Engine (Incident Triage)...")
    payload = {
        "incident_number": "INC-TEST-9999",
        "short_description": "Production database connection pool exhausted - orders failing",
        "description": "Users report 503 service unavailable when attempting checkout. Multiple connection pool timeouts.",
        "category": "database",
        "priority": "1 - Critical",
        "logs": "HikariPool-1 - Connection is not available, request timed out after 30000ms\nHTTP 503 Service Unavailable\nFATAL: remaining connection slots are reserved",
        "recent_changes": "Scheduled batch job started 15 minutes before failure.",
        "application": "checkout-service",
        "environment": "production"
    }

    data, code = api_call("/api/incidents/analyze", method="POST", data=payload)
    if code != 200:
        print(f"      FAILED: {data}")
        return False, None

    print(f"      Incident Number     : {data.get('incident_number')}")
    print(f"      Confidence Score    : {data.get('confidence_label', '').upper()} ({data.get('confidence_score', 0):.0%})")
    print(f"      Probable Root Cause : {data.get('probable_root_cause', '')[:85]}...")
    print(f"      Recommended Team    : {data.get('recommended_team')}")
    print(f"      Evidence Signals    : {len(data.get('evidence', []))} signals detected")
    print(f"      Similar Cases Found : {len(data.get('similar_cases', []))} historical matches")
    print(f"      Recommended Actions : {len(data.get('recommended_actions', []))} action steps")
    print(f"      Diagnostic Commands : {len(data.get('diagnostic_commands', []))} commands suggested")
    return True, data.get("incident_number")


def test_copilot(incident_num):
    print(f"[5/8] Testing Incident Copilot Q&A on {incident_num}...")
    if not incident_num:
        print("      SKIPPED: No incident available.")
        return True

    payload = {
        "incident_number": incident_num,
        "question": "What is the recommended team and the primary action to resolve this?"
    }
    data, code = api_call("/api/copilot/ask", method="POST", data=payload)
    if code != 200:
        print(f"      FAILED: {data}")
        return False

    ans = data.get("answer", "")
    print(f"      Question: {payload['question']}")
    print(f"      Answer  : {ans[:100]}...")
    return True


def test_decision(incident_num):
    print(f"[6/8] Testing Engineer RCA Decision (Accept/Reject)...")
    if not incident_num:
        print("      SKIPPED: No incident available.")
        return True

    payload = {
        "incident_number": incident_num,
        "decision": "accepted",
        "engineer_notes": "Engineer confirmed pool exhaustion matches monitoring metrics."
    }
    data, code = api_call("/api/servicenow/decision", method="POST", data=payload)
    if code != 200 or not data.get("success"):
        print(f"      FAILED: {data}")
        return False

    print(f"      Decision Recorded: {data.get('decision', '').upper()} for {incident_num}")
    return True


def test_resolve_webhook():
    print("[7/8] Testing Auto-Publishing Resolved Incident to Firebase KB...")
    payload = {
        "incident_number": "INC-RESOLVED-8888",
        "short_description": "Network latency spike due to route flap on core switch",
        "close_notes": "Replaced faulty SFP transceiver on interface TenGigE0/1. Routing stabilized and latency returned to <1ms.",
        "close_code": "Solved (Permanently)",
        "verified_root_cause": "Hardware transceiver degradation caused intermittent BGP link flapping.",
        "assignment_group": "Network Operations",
        "category": "network"
    }

    data, code = api_call("/api/servicenow/resolve-webhook", method="POST", data=payload)
    if code != 200 or not data.get("success"):
        print(f"      FAILED: {data}")
        return False

    case_id = data.get("case_id")
    print(f"      Generated KB Case ID: {case_id}")
    print(f"      Result: {data.get('message')}")

    # Verify Firestore count updated
    stats, _ = api_call("/api/knowledge/stats")
    print(f"      Updated Total KB Cases in Firestore: {stats.get('total_cases')}")
    return True


def test_generator():
    print("[8/8] Testing Synthetic Demo Incident Generator...")
    data, code = api_call("/api/incidents/generate", method="POST")
    if code != 200:
        print(f"      FAILED: {data}")
        return False

    print(f"      Generated Incident : {data.get('incident_number')}")
    print(f"      Generated Cause    : {data.get('probable_root_cause', '')[:80]}...")
    return True


def main():
    print_header("RCA Assistant – End-to-End Test Suite")
    print(f"Testing target: {API_BASE}\n")

    steps = [
        test_health,
        test_config,
        test_knowledge_base,
    ]

    all_passed = True
    for step in steps:
        if not step():
            all_passed = False
        print()

    # Step 4: RCA Analysis
    ok, inc_num = test_rca_analysis()
    if not ok:
        all_passed = False
    print()

    # Step 5: Copilot
    if not test_copilot(inc_num):
        all_passed = False
    print()

    # Step 6: Decision
    if not test_decision(inc_num):
        all_passed = False
    print()

    # Step 7: Resolve webhook
    if not test_resolve_webhook():
        all_passed = False
    print()

    # Step 8: Generator
    if not test_generator():
        all_passed = False
    print()

    print_header("Test Suite Summary")
    if all_passed:
        print("  ALL 8 TESTS COMPLETED SUCCESSFULLY!")
        print("  Your RCA Assistant is fully operational.")
    else:
        print("  SOME TESTS REPORTED WARNINGS OR ERRORS.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

