// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow UI Action Script – "Publish to RCA KB"
// ───────────────────────────────────────────────────────────────────────────
// Form button for engineers to manually publish a resolved incident's
// verified root cause & solution directly into Firebase Firestore KB.
//
// INSTALLATION STEPS (ServiceNow PDI):
// 1. Go to System UI → UI Actions
// 2. Click New
// 3. Fill in:
//    Name:        Publish to RCA KB
//    Table:       Incident [incident]
//    Form button: ✅ checked
//    Action name: publish_to_rca_kb
//    Order:       140
//    Condition:   current.state == 6 || current.state == 7  (Resolved or Closed)
// 4. Paste this script
// 5. Update RCA_ASSISTANT_URL
// 6. Click Submit
// ═══════════════════════════════════════════════════════════════════════════
  
(function executeAction(/*GlideRecord*/ current, /*GlideRecord*/ previous) {

  var RCA_ASSISTANT_URL = 'https://rca-assistant.onrender.com';  // Live Render URL

  var incidentNumber = current.number.toString();
  var closeNotes = current.close_notes ? current.close_notes.toString() : '';
  var shortDesc = current.short_description ? current.short_description.toString() : '';
  var category = current.category ? current.category.toString() : 'general';
  var closeCode = current.close_code ? current.close_code.getDisplayValue() : '';
  var assignmentGroup = current.assignment_group ? current.assignment_group.getDisplayValue() : '';

  if (!closeNotes && !shortDesc) {
    gs.addErrorMessage('Cannot publish to KB: Close notes are empty. Please fill in resolution details first.');
    return;
  }

  var payload = {
    incident_number: incidentNumber,
    short_description: shortDesc,
    close_notes: closeNotes,
    close_code: closeCode,
    verified_root_cause: closeNotes,
    assignment_group: assignmentGroup,
    category: category
  };

  try {
    var req = new sn_ws.RESTMessageV2();
    req.setEndpoint(RCA_ASSISTANT_URL + '/api/servicenow/resolve-webhook');
    req.setHttpMethod('POST');
    req.setRequestHeader('Content-Type', 'application/json');
    req.setRequestHeader('Accept', 'application/json');
    req.setRequestBody(JSON.stringify(payload));

    var response = req.execute();
    var statusCode = response.getStatusCode();
    var body = response.getBody();

    if (statusCode === 200) {
      gs.addInfoMessage('✅ Incident ' + incidentNumber + ' successfully published to Firebase Knowledge Base!');
      current.work_notes = '📚 [RCA Assistant] Verified resolution published to Knowledge Base by ' + gs.getUserDisplayName();
      current.update();
    } else {
      gs.addErrorMessage('Failed to publish to KB (HTTP ' + statusCode + '): ' + body.substring(0, 200));
    }
  } catch (e) {
    gs.addErrorMessage('Error connecting to RCA Assistant: ' + e.message);
  }

})(current, previous);

