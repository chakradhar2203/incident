// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow Business Rule – "Auto Publish Resolved Incident to RCA KB"
// ───────────────────────────────────────────────────────────────────────────
// When an engineer resolves an incident in ServiceNow, this Business Rule
// automatically posts the verified root cause & resolution notes to the
// RCA Assistant, which saves it directly into Firebase Firestore!
//
// INSTALLATION STEPS (ServiceNow PDI):
// 1. Navigate to: System Definition → Business Rules
// 2. Click New
// 3. Configure:
//    Name:        Auto Publish Resolved to RCA KB
//    Table:       Incident [incident]
//    Active:      ✅ Checked
//    Advanced:    ✅ Checked
// 4. In "When to run" tab:
//    When:        after
//    Order:       100
//    Update:      ✅ Checked
//    Filter Conditions:
//                 State [changes to] Resolved
//                 OR
//                 State [changes to] Closed
// 5. In "Advanced" tab -> Script:
//    Paste this script.
//    Update RCA_ASSISTANT_URL with your actual endpoint.
// 6. Click Submit.
// ═══════════════════════════════════════════════════════════════════════════

(function executeRule(current, previous /*null when async*/) {

  var RCA_ASSISTANT_URL = 'http://localhost:8000';  // ← Replace with your URL / ngrok tunnel

  var incidentNumber = current.number.toString();
  var closeNotes = current.close_notes ? current.close_notes.toString() : '';
  var shortDesc = current.short_description ? current.short_description.toString() : '';
  var category = current.category ? current.category.toString() : 'general';
  var closeCode = current.close_code ? current.close_code.getDisplayValue() : '';
  var assignmentGroup = current.assignment_group ? current.assignment_group.getDisplayValue() : '';

  // Only publish if resolution notes exist
  if (!closeNotes && !shortDesc) {
    gs.log('RCA KB Auto-Publish: Skipped ' + incidentNumber + ' because close notes are empty.');
    return;
  }

  var payload = {
    incident_number: incidentNumber,
    short_description: shortDesc,
    close_notes: closeNotes,
    close_code: closeCode,
    verified_root_cause: closeNotes, // Uses verified engineer resolution notes as ground truth
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
      gs.log('RCA KB Auto-Publish: Successfully saved ' + incidentNumber + ' to Firebase Firestore KB.');
    } else {
      gs.logWarning('RCA KB Auto-Publish HTTP ' + statusCode + ': ' + body);
    }
  } catch (e) {
    gs.logError('RCA KB Auto-Publish failed for ' + incidentNumber + ': ' + e.message);
  }

})(current, previous);

