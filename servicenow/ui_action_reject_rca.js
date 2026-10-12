// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow UI Action Script – "Reject RCA"
// ───────────────────────────────────────────────────────────────────────────
// INSTALLATION STEPS (ServiceNow PDI):
// 1. Go to System UI → UI Actions
// 2. Click New
// 3. Fill in:
//    Name:        Reject RCA
//    Table:       Incident [incident]
//    Form button: ✅ checked
//    Action name: reject_rca
//    Order:       130
//    Condition:   current.state != 6 && current.state != 7
// 4. Paste this entire script into the "Script" field
// 5. Update RCA_ASSISTANT_URL with your RCA Assistant URL (e.g., ngrok or server)
// 6. Click Submit
// ═══════════════════════════════════════════════════════════════════════════

(function executeAction(/*GlideRecord*/ current, /*GlideRecord*/ previous) {

  var RCA_ASSISTANT_URL = 'https://rca-assistant.onrender.com';  // Live Render URL

  var incidentNumber = current.number.toString();

  // 1. Send rejection decision to RCA Assistant
  var req = new sn_ws.RESTMessageV2();
  req.setEndpoint(RCA_ASSISTANT_URL + '/api/servicenow/decision');
  req.setHttpMethod('POST');
  req.setRequestHeader('Content-Type', 'application/json');
  req.setRequestHeader('Accept', 'application/json');

  var payload = {
    incident_number: incidentNumber,
    decision: 'rejected',
    engineer_notes: 'Engineer rejected AI RCA recommendation as inaccurate or not applicable.'
  };

  req.setRequestBody(JSON.stringify(payload));

  try {
    var response = req.execute();
    var statusCode = response.getStatusCode();
    if (statusCode !== 200) {
      gs.addWarningMessage('RCA Assistant decision sync returned HTTP ' + statusCode);
    }
  } catch (e) {
    gs.addWarningMessage('RCA Assistant offline, recorded locally: ' + e.message);
  }

  // 2. Add rejection note to Work Notes
  var note = '❌ [RCA Assistant Decision: REJECTED]\n';
  note += 'Engineer has reviewed and REJECTED the AI-generated Root Cause Analysis.\n';
  note += 'Reason: Diagnosis does not match actual root cause. Manual investigation proceeding.\n';
  note += 'Rejected by: ' + gs.getUserDisplayName() + ' at ' + new GlideDateTime().getDisplayValue();

  current.work_notes = note;
  current.update();

  gs.addErrorMessage('❌ AI RCA was rejected. Manual investigation notes logged for ' + incidentNumber);

})(current, previous);

