// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow UI Action Script – "Write RCA to Incident"
// ───────────────────────────────────────────────────────────────────────────
// Add this as a second button: pushes a previously analyzed RCA from the
// RCA Assistant back into this incident's work notes manually.
//
// Name:        Write RCA Notes
// Table:       Incident [incident]
// Form button: ✅ checked
// Condition:   current.state != 6
// ═══════════════════════════════════════════════════════════════════════════

(function executeAction(/*GlideRecord*/ current, /*GlideRecord*/ previous) {

  var RCA_ASSISTANT_URL = 'http://localhost:8000';  // ← Replace with your URL

  var req = new sn_ws.RESTMessageV2();
  req.setEndpoint(RCA_ASSISTANT_URL + '/api/servicenow/' + current.number + '/writeback');
  req.setHttpMethod('POST');
  req.setRequestHeader('Content-Type', 'application/json');
  req.setRequestHeader('Accept', 'application/json');

  var response;
  try {
    response = req.execute();
  } catch (e) {
    gs.addErrorMessage('RCA Write-back: Failed to connect – ' + e.message);
    return;
  }

  var statusCode = response.getStatusCode();
  var body       = response.getBody();

  if (statusCode === 200) {
    var result;
    try { result = JSON.parse(body); } catch (_) { result = {}; }
    if (result.success) {
      gs.addInfoMessage('✅ RCA notes written to this incident successfully.');
    } else {
      gs.addErrorMessage('RCA Write-back failed: ' + (result.error || 'unknown error'));
    }
  } else if (statusCode === 404) {
    gs.addErrorMessage(
      'No RCA found for ' + current.number +
      '. Please run "Run RCA Analysis" first.'
    );
  } else {
    gs.addErrorMessage('RCA Write-back HTTP ' + statusCode + ': ' + body.substring(0, 200));
  }

})(current, previous);

