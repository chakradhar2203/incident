// ═══════════════════════════════════════════════════════════════════════════
// ServiceNow UI Action Script – "Run RCA Analysis"
// ───────────────────────────────────────────────────────────────────────────
// INSTALLATION STEPS (ServiceNow PDI):
// 1. Go to System UI → UI Actions
// 2. Click New
// 3. Fill in:
//    Name:       Run RCA Analysis
//    Table:      Incident [incident]
//    Form button: ✅ checked
//    Action name: run_rca_analysis
//    Condition:  current.state != 6  (exclude resolved incidents)
// 4. Paste this entire script into the "Script" field
// 5. Save and impersonate a user / test from an incident record
//
// IMPORTANT: Replace RCA_ASSISTANT_URL with your actual RCA Assistant URL.
// For local testing, use an ngrok or similar tunnel URL.
// ═══════════════════════════════════════════════════════════════════════════

(function executeAction(/*GlideRecord*/ current, /*GlideRecord*/ previous) {

  var RCA_ASSISTANT_URL = 'http://localhost:8000';  // ← Replace with your URL

  // ── Build payload from current incident ───────────────────────────────────
  var payload = {
    incident_number:   current.number.toString(),
    short_description: current.short_description.toString(),
    description:       current.description.toString(),
    category:          current.category.toString(),
    priority:          current.priority.getDisplayValue(),
    logs:              current.u_application_logs ? current.u_application_logs.toString() : '',
    recent_changes:    current.u_recent_changes   ? current.u_recent_changes.toString()   : '',
    application:       current.cmdb_ci.getDisplayValue(),
    environment:       'production',
    sys_id:            current.sys_id.toString(),
    assignment_group:  current.assignment_group.getDisplayValue()
  };

  // ── Call RCA Assistant API ────────────────────────────────────────────────
  var req  = new sn_ws.RESTMessageV2();
  req.setEndpoint(RCA_ASSISTANT_URL + '/api/incidents/analyze');
  req.setHttpMethod('POST');
  req.setRequestHeader('Content-Type', 'application/json');
  req.setRequestHeader('Accept', 'application/json');
  req.setRequestBody(JSON.stringify(payload));

  var response;
  try {
    response = req.execute();
  } catch (e) {
    gs.addErrorMessage('RCA Assistant: Failed to connect – ' + e.message);
    return;
  }

  var statusCode = response.getStatusCode();
  var body       = response.getBody();

  if (statusCode !== 200) {
    gs.addErrorMessage('RCA Assistant returned HTTP ' + statusCode + ': ' + body.substring(0, 300));
    return;
  }

  // ── Parse result and write work note ─────────────────────────────────────
  var rca;
  try {
    rca = JSON.parse(body);
  } catch (e) {
    gs.addErrorMessage('RCA Assistant: Invalid JSON response – ' + e.message);
    return;
  }

  // Format work note
  var confidence = Math.round((rca.confidence_score || 0) * 100) + '%';
  var note = '⚠️  [AI-GENERATED RCA — REQUIRES ENGINEER REVIEW BEFORE ACTION]\n\n';
  note += '🔍 Probable Root Cause: ' + (rca.probable_root_cause || 'N/A') + '\n';
  note += '📊 Confidence: ' + (rca.confidence_label || '').toUpperCase() + ' (' + confidence + ')\n';
  note += '👥 Recommended Team: ' + (rca.recommended_team || 'N/A') + '\n\n';

  if (rca.evidence && rca.evidence.length) {
    note += '📋 Evidence:\n';
    for (var i = 0; i < rca.evidence.length; i++) {
      note += '  • ' + rca.evidence[i] + '\n';
    }
    note += '\n';
  }

  if (rca.recommended_actions && rca.recommended_actions.length) {
    note += '✅ Recommended Actions:\n';
    for (var j = 0; j < rca.recommended_actions.length; j++) {
      note += '  ' + (j + 1) + '. ' + rca.recommended_actions[j] + '\n';
    }
    note += '\n';
  }

  if (rca.similar_cases && rca.similar_cases.length) {
    note += '🕰️  Similar Historical Cases:\n';
    for (var k = 0; k < rca.similar_cases.length; k++) {
      var sc = rca.similar_cases[k];
      note += '  • [' + sc.case_id + '] ' + sc.description.substring(0, 80) + '\n';
    }
    note += '\n';
  }

  note += 'Analysis mode: ' + (rca.analysis_mode || 'local') + '\n';
  note += 'Analyzed at: ' + (rca.analyzed_at || new Date().toISOString());

  // Write to work notes
  current.work_notes = note;

  // Optionally set state to In Progress
  if (current.state == '1') {  // New → In Progress
    current.state = '2';
  }

  // Optionally set assignment group from recommendation
  if (rca.recommended_team && !current.assignment_group.nil()) {
    // Only suggest — do not override existing assignment
    gs.addInfoMessage('RCA suggests routing to: ' + rca.recommended_team);
  }

  current.update();
  gs.addInfoMessage(
    '✅ RCA Analysis complete. Confidence: ' + (rca.confidence_label || '').toUpperCase() +
    ' (' + confidence + '). See Work Notes for details.'
  );

})(current, previous);

