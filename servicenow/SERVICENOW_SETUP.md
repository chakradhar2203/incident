# ServiceNow PDI Setup Guide

This guide explains how to install the RCA Assistant integration, form buttons (**Run RCA**, **Accept RCA**, **Reject RCA**, **Publish to KB**), and automated **Resolve-to-KB** Business Rule on your ServiceNow PDI incident form.

---

## Prerequisites
- Access to a ServiceNow Personal Developer Instance (PDI)
- RCA Assistant running (local port 8000 exposed via ngrok or public IP)
- A ServiceNow integration user account (or your admin credentials)

---

## Step 1: Create Custom Fields (Optional but Recommended)

Navigate to **System Definition → Tables** → Search for `Incident` (`incident`).

Add two fields to capture raw troubleshooting signals:
| Field Label | Field Name | Type | Length |
|-------------|------------|------|--------|
| Application Logs | `u_application_logs` | String | 65535 |
| Recent Changes | `u_recent_changes` | String | 1000 |

---

## Step 2: Install Incident Form Buttons (UI Actions)

Navigate to **System UI → UI Actions** and click **New** for each of the following buttons:

### 1. Button: "Run RCA Analysis"
* **Name**: `Run RCA Analysis`
* **Table**: `Incident [incident]`
* **Form button**: ✅ Checked
* **Action name**: `run_rca_analysis`
* **Order**: `100`
* **Condition**: `current.state != 6 && current.state != 7` (Active incidents only)
* **Script**: Copy from [`ui_action_run_rca.js`](ui_action_run_rca.js)
* **Action**: Calls RCA Assistant with incident logs + description, retrieves Claude AI analysis, and formats work notes on the ticket.

### 2. Button: "Accept RCA"
* **Name**: `Accept RCA`
* **Table**: `Incident [incident]`
* **Form button**: ✅ Checked
* **Action name**: `accept_rca`
* **Order**: `120`
* **Condition**: `current.state != 6 && current.state != 7`
* **Script**: Copy from [`ui_action_accept_rca.js`](ui_action_accept_rca.js)
* **Action**: Records engineer acceptance, adds confirmation to Work Notes, ensures state is In Progress, and logs approval in RCA Assistant.

### 3. Button: "Reject RCA"
* **Name**: `Reject RCA`
* **Table**: `Incident [incident]`
* **Form button**: ✅ Checked
* **Action name**: `reject_rca`
* **Order**: `130`
* **Condition**: `current.state != 6 && current.state != 7`
* **Script**: Copy from [`ui_action_reject_rca.js`](ui_action_reject_rca.js)
* **Action**: Flags the AI recommendation as rejected, records reason in Work Notes, and logs feedback to RCA Assistant to prevent false learning.

### 4. Button: "Publish to RCA KB" (Manual 1-Click Publishing)
* **Name**: `Publish to RCA KB`
* **Table**: `Incident [incident]`
* **Form button**: ✅ Checked
* **Action name**: `publish_to_rca_kb`
* **Order**: `140`
* **Condition**: `current.state == 6 || current.state == 7` (Resolved or Closed incidents)
* **Script**: Copy from [`ui_action_publish_to_kb.js`](ui_action_publish_to_kb.js)
* **Action**: Extracts verified close notes and publishes the ticket straight to Firebase Firestore as a new Knowledge Case.

---

## Step 3: Automatic Publishing on Incident Resolution (Business Rule)

To automatically store resolved incidents in Firebase Firestore without requiring the engineer to click a button:

1. Navigate to **System Definition → Business Rules**
2. Click **New**
3. Configure:
   * **Name**: `Auto Publish Resolved to RCA KB`
   * **Table**: `Incident [incident]`
   * **Active**: ✅ Checked
   * **Advanced**: ✅ Checked
4. In **When to run** tab:
   * **When**: `after`
   * **Order**: `100`
   * **Update**: ✅ Checked
   * **Filter Conditions**:
     * `State` `changes to` `Resolved`
     * **OR** `State` `changes to` `Closed`
5. In **Advanced** tab -> **Script**:
   * Paste the contents of [`business_rule_publish_kb_on_resolve.js`](business_rule_publish_kb_on_resolve.js)
   * Set `RCA_ASSISTANT_URL` to your RCA Assistant URL (e.g. `https://xxxx.ngrok-free.app`)
6. Click **Submit**.

---

## Step 4: Connecting Localhost to ServiceNow PDI via ngrok

A ServiceNow PDI runs in the cloud and cannot reach `http://localhost:8000` directly. Expose your local RCA Assistant with **ngrok**:

```bash
# In terminal:
ngrok http 8000

```

Copy the generated URL (e.g., `https://abc-123.ngrok-free.app`) and replace `http://localhost:8000` inside:
1. `ui_action_run_rca.js`
2. `ui_action_accept_rca.js`
3. `ui_action_reject_rca.js`
4. `ui_action_publish_to_kb.js`
5. `business_rule_publish_kb_on_resolve.js`

---

## Step 5: Verification & End-to-End Workflow

1. **Trigger RCA**: Open an incident in ServiceNow → Click **Run RCA Analysis**.
2. **Review Result**: Examine work notes with Probable Cause, Evidence, Confidence, Diagnostic Commands.
3. **Accept / Reject**: Click **Accept RCA** (confirms recommendation) or **Reject RCA** (notes manual triage required).
4. **Resolve & Auto-Learn**: When fixing the incident, enter **Resolution Notes** (`close_notes`) and set state to **Resolved**.
5. **Knowledge Base Update**: Check the RCA Assistant Dashboard (**Knowledge Base** tab) or call `/api/knowledge/stats` — the incident automatically appears as `SN-INCXXXXXX` stored in Firebase Firestore!
