// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow UI Action Script – "Accept RCA"
// ───────────────────────────────────────────────────────────────────────────
// INSTALLATION STEPS (ServiceNow PDI):
// 1. Go to System UI → UI Actions
// 2. Click New
// 3. Fill in:
//    Name:        Accept RCA
//    Table:       Incident [incident]
//    Form button: ✅ checked
//    Action name: accept_rca
//    Order:       120
//    Condition:   current.state != 6 && current.state != 7
// 4. Paste this entire script into the "Script" field
// 5. Update RCA_ASSISTANT_URL with your RCA Assistant URL (e.g., ngrok or server)
// 6. Click Submit
// ═══════════════════════════════════════════════════════════════════════════

(function executeAction(/*GlideRecord*/ current, /*GlideRecord*/ previous) {

  var RCA_ASSISTANT_URL = 'https://rca-assistant.onrender.com';  // Live Render URL

  var incidentNumber = current.number.toString();

  // 1. Send acceptance decision to RCA Assistant
  var req = new sn_ws.RESTMessageV2();
  req.setEndpoint(RCA_ASSISTANT_URL + '/api/servicenow/decision');
  req.setHttpMethod('POST');
  req.setRequestHeader('Content-Type', 'application/json');
  req.setRequestHeader('Accept', 'application/json');

  var payload = {
    incident_number: incidentNumber,
    decision: 'accepted',
    engineer_notes: 'Engineer confirmed RCA recommendations on incident form.'
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

  // 2. Add confirmation to Work Notes
  var note = '✅ [RCA Assistant Decision: ACCEPTED]\n';
  note += 'Engineer has reviewed and accepted the AI-generated Root Cause Analysis.\n';
  note += 'Diagnosis and proposed mitigation steps are verified for execution.\n';
  note += 'Accepted by: ' + gs.getUserDisplayName() + ' at ' + new GlideDateTime().getDisplayValue();

  current.work_notes = note;

  // 3. Ensure incident is marked In Progress
  if (current.state == '1') {
    current.state = '2'; // In Progress
  }

  current.update();
  gs.addInfoMessage('✅ RCA recommendation accepted. Work notes updated for ' + incidentNumber);

})(current, previous);

