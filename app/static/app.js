/* ═══════════════════════════════════════════════════════════
   RCA Assistant – Dashboard JavaScript
   ═══════════════════════════════════════════════════════════ */
'use strict';

const API = '';  // Same origin
let _currentIncidentNumber = null;
let _currentRca = null;
let _schedulerPoll = null;

// ── Tab navigation ────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    if (tab.dataset.tab === 'dashboard') loadDashboard();
    if (tab.dataset.tab === 'history') loadHistoryTab();
    if (tab.dataset.tab === 'knowledge') loadKnowledge();
  });
});

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  startSchedulerPoll();
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const cfg = await apiFetch('/api/config');
    setText('m-incidents', cfg.incidents_analyzed);
    setText('m-kb', cfg.knowledge_cases);
    setText('m-avg-conf', cfg.average_confidence ? (cfg.average_confidence * 100).toFixed(1) + '%' : '—');
    setText('m-high', cfg.high_confidence_count);

    setBadge('s-mode', cfg.analysis_mode === 'ai' ? 'AI-Assisted' : 'Local', cfg.analysis_mode === 'ai' ? 'blue' : 'gray');
    setBadge('s-claude', cfg.claude_configured ? 'Configured' : 'Not Set', cfg.claude_configured ? 'green' : 'red');
    setBadge('s-firebase', cfg.firebase_configured ? 'Connected' : 'In-Memory', cfg.firebase_configured ? 'green' : 'orange');
    setBadge('s-writeback', cfg.servicenow_writeback_enabled ? 'Enabled' : 'Disabled', cfg.servicenow_writeback_enabled ? 'green' : 'gray');
  } catch(e) { console.error('Dashboard load error:', e); }

  await loadIncidentsList();
  await refreshSchedulerStatus();
}

async function loadIncidentsList() {
  try {
    const list = await apiFetch('/api/incidents');
    const tbody = document.getElementById('incidents-tbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">No incidents analyzed yet.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(r => `
      <tr>
        <td><code>${r.incident_number}</code></td>
        <td>${truncate(r.probable_root_cause, 70)}</td>
        <td><span class="badge badge-${r.confidence_label}">${r.confidence_label} ${(r.confidence_score*100).toFixed(0)}%</span></td>
        <td>${r.recommended_team}</td>
        <td><span class="badge badge-${r.analysis_mode === 'ai' ? 'blue' : 'gray'}">${r.analysis_mode}</span></td>
        <td>${formatDate(r.analyzed_at)}</td>
        <td><button class="btn btn-sm btn-ghost" onclick="viewRca('${r.incident_number}')">View</button></td>
      </tr>
    `).join('');
  } catch(e) { console.error('Incidents list error:', e); }
}

async function viewRca(num) {
  try {
    const rca = await apiFetch(`/api/incidents/${num}`);
    showTab('analyze');
    renderRcaResult(rca);
  } catch(e) { toast('Failed to load RCA: ' + e.message, 'error'); }
}

// ── Scheduler ─────────────────────────────────────────────────────────────────
async function refreshSchedulerStatus() {
  try {
    const s = await apiFetch('/api/scheduler/status');
    const dot = document.getElementById('sch-dot');
    const runEl = document.getElementById('sch-running');
    const meta = document.getElementById('sch-meta');

    if (s.running) {
      dot.className = 'dot dot-green';
      runEl.textContent = 'Running — generating an incident every 2 minutes';
      meta.style.display = 'flex';
      setText('sch-last', s.last_incident || '—');
      setText('sch-wb', s.last_writeback_status || '—');
      setText('sch-next', s.next_run ? new Date(s.next_run).toLocaleTimeString() : '—');
      const errRow = document.getElementById('sch-error-row');
      if (s.error) {
        errRow.style.display = 'flex';
        setText('sch-error', s.error);
      } else {
        errRow.style.display = 'none';
      }
    } else {
      dot.className = 'dot dot-gray';
      runEl.textContent = 'Not running';
      meta.style.display = 'none';
    }
  } catch(e) { /* ignore */ }
}

function startSchedulerPoll() {
  _schedulerPoll = setInterval(refreshSchedulerStatus, 10000);
}

async function startScheduler() {
  try {
    await apiFetch('/api/scheduler/start', { method: 'POST' });
    toast('Scheduler started', 'success');
    setTimeout(refreshSchedulerStatus, 500);
  } catch(e) { toast('Failed to start scheduler: ' + e.message, 'error'); }
}

async function stopScheduler() {
  try {
    await apiFetch('/api/scheduler/stop', { method: 'POST' });
    toast('Scheduler stopped', 'info');
    setTimeout(refreshSchedulerStatus, 500);
  } catch(e) { toast('Failed to stop scheduler: ' + e.message, 'error'); }
}

// ── Analyze tab ───────────────────────────────────────────────────────────────
const TEST_PRESETS = {
  vpn_timeout: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'network',
    priority: '2 - High',
    app: 'Corporate VPN Service',
    short_desc: 'Users unable to connect to corporate VPN due to network connectivity issues',
    desc: 'Multiple users reported inability to establish VPN connections to the corporate network. Intermittent connectivity between VPN gateway servers and internet service providers. Remote users unable to access internal applications.',
    logs: 'VPN connection timeout\nGateway unreachable\nNetwork packet loss detected: 85%\nFailed to establish secure tunnel\nError Code: VPN-504 Gateway Timeout',
    changes: 'Upstream ISP fiber maintenance reported in local region.'
  },
  disk_full: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'storage',
    priority: '2 - High',
    app: 'app-server-03',
    short_desc: '/var filesystem full due to uncontrolled application log growth',
    desc: 'Monitoring reports critical disk utilization (>95%) on /var partition. Application write failures reported across services.',
    logs: 'No space left on device (ENOSPC)\nwrite failed: /var/log/app/payment.log\ndf -h: /dev/sda1 100% /var\nOSError: [Errno 28] No space left on device',
    changes: 'Log rotation policy was modified in /etc/logrotate.d/ during yesterday maintenance.'
  },
  db_pool: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'database',
    priority: '1 - Critical',
    app: 'order-service',
    short_desc: 'HTTP 503 errors on order-service – database connection pool exhausted',
    desc: 'Users experiencing 503 Service Unavailable when placing orders. HikariCP pool at maximum capacity. Queries timing out after 30s.',
    logs: 'HikariPool-1 - Connection is not available, request timed out after 30000ms\nPool stats (total=50, active=50, idle=0, waiting=23)\nHTTP 503 Service Unavailable\norg.postgresql.util.PSQLException: FATAL: remaining connection slots reserved',
    changes: 'Database maintenance window last night; max_connections parameter not restored.'
  },
  oom_killed: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'memory',
    priority: '1 - Critical',
    app: 'payment-api',
    short_desc: 'Production service OOMKilled – payment-api pods restarting (Exit 137)',
    desc: 'Payment API deployment in prod experiencing repeated pod evictions. Kubernetes reports OOMKilled with exit code 137.',
    logs: 'java.lang.OutOfMemoryError: Java heap space\n\tat java.util.Arrays.copyOf(Arrays.java:3210)\nOOMKilled exit code 137\nkubernetes: pod payment-api-7d9f6b5c4-xkp2q restarted 8 times',
    changes: 'Pod heap size reduced from -Xmx4g to -Xmx2g in last release.'
  },
  ssl_expired: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'authentication',
    priority: '1 - Critical',
    app: 'api-gateway',
    short_desc: 'SSL certificate expired – API gateway returning 401 / TLS handshake failure',
    desc: 'API Gateway is rejecting all incoming HTTPS traffic with SSL handshake failure. Certificate expiry was reached.',
    logs: 'SSL_ERROR_RX_RECORD_TOO_LONG\nERR_CERT_DATE_INVALID\nTLS handshake failed: certificate has expired\ncert-manager: ClusterIssuer letsencrypt-prod is not ready: ACME account error',
    changes: 'ClusterIssuer updated 2 weeks ago to change ACME email address.'
  },
  sssd_auth: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'authentication',
    priority: '2 - High',
    app: 'ad-auth-service',
    short_desc: 'SSSD authentication failures due to expired AD trust credentials',
    desc: 'Linux server domain authentication failing for enterprise users. SSSD service unable to authenticate against Active Directory.',
    logs: 'sssd[be[domain]]: [krb5_child[12345]] Keytab ticket expired or domain trust credentials rejected\nFailed to authenticate user via PAM: Authentication token expired\nsystemd: pam_sss(sshd:auth): authentication failure; logname= uid=0 euid=0',
    changes: 'Active Directory domain controller trust certificates rotated last weekend.'
  },
  dns_failure: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'network',
    priority: '2 - High',
    app: 'core-dns-service',
    short_desc: 'DNS resolution failures caused by unreachable configured nameservers',
    desc: 'Internal services failing to resolve domain names. resolve.conf pointing to decommissioned IP address.',
    logs: 'Name or service not known (EAI_NONAME)\nnslookup: connection timed out; no servers could be reached\nresolver: query failed to 10.0.0.2:53 (SERVFAIL)',
    changes: 'Subnet DNS IP migration completed overnight without updating DHCP options.'
  },
  iis_disk: {
    number: 'INC00' + Math.floor(10000 + Math.random() * 90000),
    category: 'storage',
    priority: '2 - High',
    app: 'iis-web-cluster',
    short_desc: 'Windows Server system drive exhausted by IIS log and dump growth',
    desc: 'C: system drive has 0 MB free disk space. IIS worker processes crashing and refusing incoming requests.',
    logs: 'Event ID 1500: The server cannot allocate more space on drive C:\nHTTP 500.19 - Internal Server Error - Cannot read configuration file\nDisk free space: 0 MB of 120 GB',
    changes: 'High traffic event caused W3C log files to accumulate in C:\\inetpub\\logs\\LogFiles.'
  }
};

function loadTestPreset(type) {
  const p = TEST_PRESETS[type];
  if (!p) return;
  setVal('f-number', p.number);
  setVal('f-category', p.category);
  setVal('f-priority', p.priority);
  setVal('f-app', p.app);
  setVal('f-short-desc', p.short_desc);
  setVal('f-description', p.desc);
  setVal('f-logs', p.logs);
  setVal('f-changes', p.changes);
  toast(`Loaded scenario: ${p.short_desc.substring(0, 35)}...`, 'info');
}

function fillRandomDemoData() {
  const keys = Object.keys(TEST_PRESETS);
  const randomKey = keys[Math.floor(Math.random() * keys.length)];
  loadTestPreset(randomKey);
}

async function submitAnalysis(event) {
  event.preventDefault();
  const btn = document.getElementById('analyze-btn');
  const loading = document.getElementById('analyze-loading');

  btn.disabled = true;
  loading.style.display = 'flex';
  document.getElementById('result-panel').style.display = 'none';

  const autoNum = 'INC00' + Math.floor(10000 + Math.random() * 90000);
  const incNum = val('f-number') || autoNum;
  setVal('f-number', incNum);

  const payload = {
    incident_number: incNum,
    short_description: val('f-short-desc'),
    description: val('f-description'),
    category: val('f-category'),
    priority: val('f-priority'),
    logs: val('f-logs'),
    recent_changes: val('f-changes'),
    application: val('f-app'),
    environment: 'production',
  };

  try {
    const rca = await apiFetch('/api/incidents/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderRcaResult(rca);
    toast('RCA complete!', 'success');
  } catch(e) {
    toast('Analysis failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    loading.style.display = 'none';
  }
}

async function createInServiceNow(event) {
  if (event) event.preventDefault();
  const shortDesc = val('f-short-desc');
  if (!shortDesc) {
    toast('Please enter at least a Short Description before posting to ServiceNow', 'warning');
    document.getElementById('f-short-desc').focus();
    return;
  }

  const btn = document.getElementById('post-snow-btn');
  btn.disabled = true;
  btn.innerHTML = '⏳ Posting…';

  const payload = {
    incident_number: val('f-number') || 'NEW',
    short_description: shortDesc,
    description: val('f-description') || shortDesc,
    category: val('f-category'),
    priority: val('f-priority'),
    logs: val('f-logs'),
    recent_changes: val('f-changes'),
    application: val('f-app'),
    environment: 'production',
  };

  try {
    const res = await apiFetch('/api/servicenow/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (res.success && res.number) {
      setVal('f-number', res.number);
      toast(`Created incident ${res.number} in ServiceNow!`, 'success');

      const banner = document.getElementById('sn-ticket-banner');
      const link = document.getElementById('sn-ticket-link');
      if (banner && link) {
        link.textContent = `${res.number} ↗`;
        link.href = res.link || `https://dev411616.service-now.com/nav_to.do?uri=incident.do?sys_id=${res.sys_id}`;
        banner.style.display = 'block';
        banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    } else {
      toast('Failed to create ticket: ' + (res.error || 'Unknown error'), 'error');
    }
  } catch(e) {
    toast('ServiceNow post error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🚀 Post to ServiceNow';
  }
}

async function generateAndAnalyze() {
  const loading = document.getElementById('analyze-loading');
  loading.style.display = 'flex';
  document.getElementById('result-panel').style.display = 'none';
  try {
    const rca = await apiFetch('/api/incidents/generate', { method: 'POST' });
    // Populate form for context
    setVal('f-number', rca.incident_number);
    renderRcaResult(rca);
    toast('Demo incident generated & analyzed!', 'success');
  } catch(e) {
    toast('Generate failed: ' + e.message, 'error');
  } finally {
    loading.style.display = 'none';
  }
}

function renderRcaResult(rca) {
  _currentRca = rca;
  _currentIncidentNumber = rca.incident_number;

  // Header
  setText('r-incident-number', rca.incident_number);

  // Confidence banner
  const banner = document.getElementById('r-conf-banner');
  banner.className = `confidence-banner ${rca.confidence_label}`;
  setText('r-conf-score', Math.round(rca.confidence_score * 100) + '%');
  setText('r-conf-label', rca.confidence_label.toUpperCase() + ' Confidence');
  setText('r-conf-mode', 'Analysis mode: ' + rca.analysis_mode);

  // Root cause
  setText('r-root-cause', rca.probable_root_cause);

  // Team
  setText('r-team', rca.recommended_team);

  // Evidence
  const evEl = document.getElementById('r-evidence');
  evEl.innerHTML = rca.evidence.length
    ? rca.evidence.map(e => `<li>${e}</li>`).join('')
    : '<li class="empty">No specific error patterns detected.</li>';

  // Actions
  const actEl = document.getElementById('r-actions');
  actEl.innerHTML = rca.recommended_actions.length
    ? rca.recommended_actions.map(a => `<li>${a}</li>`).join('')
    : '<li class="empty">No specific actions recommended.</li>';

  // Commands
  const cmdSec = document.getElementById('r-cmd-section');
  const cmdEl = document.getElementById('r-commands');
  if (rca.diagnostic_commands && rca.diagnostic_commands.length) {
    cmdSec.style.display = 'block';
    cmdEl.innerHTML = rca.diagnostic_commands.map(cmd => `
      <div class="cmd-card ${cmd.requires_approval ? 'needs-approval' : ''}">
        <div class="cmd-line">$ ${escHtml(cmd.command)}</div>
        <div class="cmd-desc">${escHtml(cmd.description)}</div>
        ${cmd.requires_approval ? '<div class="cmd-warning">⚠️ REQUIRES ENGINEER APPROVAL before execution</div>' : ''}
      </div>
    `).join('');
  } else {
    cmdSec.style.display = 'none';
  }

  // Similar cases
  const simSec = document.getElementById('r-sim-section');
  const simEl = document.getElementById('r-similar');
  if (rca.similar_cases && rca.similar_cases.length) {
    simSec.style.display = 'block';
    simEl.innerHTML = rca.similar_cases.map(sc => `
      <div class="sim-card">
        <div class="sim-header">
          <span class="sim-id">${escHtml(sc.case_id)}</span>
          <span class="sim-score">Similarity: ${(sc.similarity_score * 100).toFixed(0)}%</span>
        </div>
        <div class="sim-desc">${escHtml(sc.description)}</div>
        <div class="sim-rc"><strong>Root Cause:</strong> ${escHtml(sc.root_cause)}</div>
        <div class="sim-res"><strong>Resolution:</strong> ${escHtml(sc.resolution)}</div>
      </div>
    `).join('');
  } else {
    simSec.style.display = 'none';
  }

  // Write-back button visibility
  const wbBtn = document.getElementById('r-wb-btn');
  wbBtn.style.display = 'inline-flex';

  // Render decision status (accepted / rejected / pending)
  renderDecisionStatus(rca.decision || 'pending', rca.decision_notes || '');

  // Show panel
  document.getElementById('result-panel').style.display = 'block';
  document.getElementById('result-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function clearForm() {
  document.getElementById('analyze-form').reset();
  document.getElementById('result-panel').style.display = 'none';
  _currentIncidentNumber = null;
}

function copyResult() {
  if (!_currentRca) return;
  const text = JSON.stringify(_currentRca, null, 2);
  navigator.clipboard.writeText(text).then(() => toast('Copied to clipboard', 'success'));
}

async function writebackCurrent() {
  if (!_currentIncidentNumber) return;
  try {
    const result = await apiFetch(`/api/servicenow/${_currentIncidentNumber}/writeback`, { method: 'POST' });
    if (result.success) toast('Written to ServiceNow!', 'success');
    else toast('Write-back failed: ' + (result.error || 'unknown'), 'error');
  } catch(e) { toast('Write-back error: ' + e.message, 'error'); }
}

async function submitFeedback() {
  if (!_currentIncidentNumber) { toast('No incident loaded', 'error'); return; }
  const payload = {
    incident_number: _currentIncidentNumber,
    verified_root_cause: val('fb-root-cause'),
    resolution_notes: val('fb-resolution'),
    final_assignment_group: val('fb-team'),
  };
  if (!payload.verified_root_cause || !payload.resolution_notes) {
    toast('Please fill in root cause and resolution notes', 'error'); return;
  }
  try {
    const res = await apiFetch('/api/incidents/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    toast('Feedback saved! Case ID: ' + res.case_id, 'success');
  } catch(e) { toast('Feedback error: ' + e.message, 'error'); }
}

// ── ServiceNow tab ────────────────────────────────────────────────────────────
async function testSnowConnection() {
  const el = document.getElementById('snow-conn-status');
  el.style.display = 'block';
  el.className = 'alert alert-info';
  el.textContent = 'Testing connection…';
  try {
    const r = await apiFetch('/api/servicenow/test');
    if (r.success) {
      el.className = 'alert alert-success';
      el.textContent = '✅ ServiceNow connection successful!';
    } else {
      el.className = 'alert alert-error';
      el.textContent = '❌ Connection failed: ' + r.error;
    }
  } catch(e) {
    el.className = 'alert alert-error';
    el.textContent = '❌ Error: ' + e.message;
  }
}

async function fetchAndAnalyze() {
  const num = val('snow-incident-num');
  if (!num) { toast('Enter an incident number', 'error'); return; }
  showSnowResult('Fetching and analyzing ' + num + '…');
  try {
    const rca = await apiFetch(`/api/servicenow/${num}`);
    showSnowResult(JSON.stringify(rca, null, 2));
    toast('Analysis complete for ' + num, 'success');
  } catch(e) {
    showSnowResult('Error: ' + e.message);
    toast('Failed: ' + e.message, 'error');
  }
}

async function manualWriteback() {
  const num = val('snow-wb-num');
  if (!num) { toast('Enter an incident number', 'error'); return; }
  try {
    const r = await apiFetch(`/api/servicenow/${num}/writeback`, { method: 'POST' });
    showSnowResult(JSON.stringify(r, null, 2));
    toast(r.success ? 'Written to ServiceNow!' : 'Write-back failed: ' + r.error, r.success ? 'success' : 'error');
  } catch(e) {
    showSnowResult('Error: ' + e.message);
    toast(e.message, 'error');
  }
}

function showSnowResult(text) {
  const panel = document.getElementById('snow-result');
  panel.style.display = 'block';
  document.getElementById('snow-result-pre').textContent = text;
}

// ── Knowledge Base tab ────────────────────────────────────────────────────────
async function loadKnowledge() {
  const tbody = document.getElementById('kb-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">Loading…</td></tr>';
  try {
    const [cases, stats] = await Promise.all([
      apiFetch('/api/knowledge'),
      apiFetch('/api/knowledge/stats'),
    ]);

    // Stats bar
    const statsEl = document.getElementById('kb-stats');
    const catBadges = Object.entries(stats.categories || {})
      .map(([k,v]) => `<span class="badge badge-blue">${k}: ${v}</span>`).join(' ');
    statsEl.innerHTML = `
      <div class="status-card"><div class="status-label">Total Cases</div><span class="badge badge-green">${stats.total_cases}</span></div>
      <div class="status-card"><div class="status-label">Firebase</div><span class="badge badge-${stats.firebase_connected ? 'green' : 'orange'}">${stats.firebase_connected ? 'Connected' : 'In-Memory'}</span></div>
      <div class="status-card"><div class="status-label">Categories</div>${catBadges}</div>
    `;

    // Table
    if (!cases.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">No cases in knowledge base.</td></tr>';
      return;
    }
    tbody.innerHTML = cases.map(c => `
      <tr>
        <td><code>${c.case_id || '—'}</code></td>
        <td><span class="badge badge-gray">${c.category || '—'}</span></td>
        <td>${truncate(c.description || '', 80)}</td>
        <td>${truncate(c.root_cause || '', 80)}</td>
        <td>${c.assignment_group || '—'}</td>
        <td>${c.verified ? '✅' : '—'}</td>
      </tr>
    `).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-cell text-danger">Error: ${e.message}</td></tr>`;
  }
}

// ── Copilot tab ───────────────────────────────────────────────────────────────
async function askCopilot() {
  const num = val('cop-incident');
  const question = val('cop-question');
  if (!num || !question) { toast('Enter both incident number and a question', 'error'); return; }

  const chatWindow = document.getElementById('chat-window');

  // Clear welcome if first message
  const welcome = chatWindow.querySelector('.chat-welcome');
  if (welcome) chatWindow.innerHTML = '';

  // Add user message
  chatWindow.innerHTML += `<div class="chat-message user">${escHtml(question)}</div>`;
  chatWindow.innerHTML += `<div class="chat-message assistant" id="cop-typing">Thinking…</div>`;
  chatWindow.scrollTop = chatWindow.scrollHeight;

  document.getElementById('cop-question').value = '';

  try {
    const res = await apiFetch('/api/copilot/ask', {
      method: 'POST',
      body: JSON.stringify({ incident_number: num, question }),
    });
    document.getElementById('cop-typing').textContent = res.answer;
    chatWindow.scrollTop = chatWindow.scrollHeight;
  } catch(e) {
    document.getElementById('cop-typing').textContent = 'Error: ' + e.message;
  }
}

// ── Settings tab ──────────────────────────────────────────────────────────────
async function saveSnowConfig() {
  const payload = {
    servicenow_instance_url: val('cfg-sn-url'),
    servicenow_username: val('cfg-sn-user'),
    servicenow_password: val('cfg-sn-pass'),
    servicenow_writeback_enabled: document.getElementById('cfg-writeback').checked,
  };
  await saveConfig(payload, 'cfg-sn-status');
}

async function saveClaudeConfig() {
  const payload = {
    claude_api_key: val('cfg-claude-key'),
    claude_model: val('cfg-claude-model'),
    analysis_mode: val('cfg-mode'),
  };
  await saveConfig(payload, 'cfg-claude-status');
}

async function saveFirebaseConfig() {
  const payload = {
    firebase_service_account_path: val('cfg-fb-path'),
    firebase_project_id: val('cfg-fb-project'),
  };
  await saveConfig(payload, 'cfg-fb-status');
}

async function saveConfig(payload, statusId) {
  const statusEl = document.getElementById(statusId);
  try {
    await apiFetch('/api/config', { method: 'POST', body: JSON.stringify(payload) });
    statusEl.textContent = '✅ Saved';
    statusEl.style.color = 'var(--green)';
    toast('Configuration updated', 'success');
    setTimeout(() => { statusEl.textContent = ''; }, 3000);
  } catch(e) {
    statusEl.textContent = '❌ ' + e.message;
    statusEl.style.color = 'var(--red)';
    toast('Save failed: ' + e.message, 'error');
  }
}

async function testSnowAndReport() {
  const statusEl = document.getElementById('cfg-sn-status');
  statusEl.textContent = 'Testing…';
  statusEl.style.color = 'var(--text-muted)';
  try {
    const r = await apiFetch('/api/servicenow/test');
    if (r.success) {
      statusEl.textContent = '✅ Connected';
      statusEl.style.color = 'var(--green)';
    } else {
      statusEl.textContent = '❌ ' + r.error;
      statusEl.style.color = 'var(--red)';
    }
  } catch(e) {
    statusEl.textContent = '❌ ' + e.message;
    statusEl.style.color = 'var(--red)';
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const defaults = { headers: { 'Content-Type': 'application/json' } };
  const merged = { ...defaults, ...options };
  if (merged.headers && options.headers) merged.headers = { ...defaults.headers, ...options.headers };
  const resp = await fetch(API + url, merged);
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const d = await resp.json(); msg = d.detail || msg; } catch(_) {}
    throw new Error(msg);
  }
  return resp.json();
}

function val(id) { return (document.getElementById(id)?.value || '').trim(); }
function setVal(id, v) { const el = document.getElementById(id); if (el) el.value = v; }
function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }
function truncate(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }
function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function formatDate(iso) {
  try { return new Date(iso).toLocaleString(); } catch(_) { return iso; }
}

function setBadge(id, text, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = `badge badge-${type}`;
}

function showTab(name) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-section').forEach(s => s.classList.toggle('active', s.id === 'tab-' + name));
}

function toast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Decision Support (Accepted / Rejected) ──────────────────────────────────
function renderDecisionBadge(decision) {
  const d = (decision || 'pending').toLowerCase().trim();
  if (d === 'accepted') {
    return '<span class="badge" style="background:rgba(16,185,129,0.18); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-weight:600;">✅ Accepted</span>';
  } else if (d === 'rejected') {
    return '<span class="badge" style="background:rgba(239,68,68,0.18); color:#ef4444; border:1px solid rgba(239,68,68,0.3); font-weight:600;">❌ Rejected</span>';
  } else {
    return '<span class="badge" style="background:rgba(245,158,11,0.18); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); font-weight:600;">⏳ Pending</span>';
  }
}

function renderDecisionStatus(decision, notes) {
  const banner = document.getElementById('r-decision-banner');
  const acceptBtn = document.getElementById('r-accept-btn');
  const rejectBtn = document.getElementById('r-reject-btn');
  if (!banner) return;

  const d = (decision || 'pending').toLowerCase().trim();
  banner.style.display = 'block';

  if (d === 'accepted') {
    banner.style.background = 'rgba(16, 185, 129, 0.12)';
    banner.style.border = '1px solid rgba(16, 185, 129, 0.35)';
    banner.style.color = '#10b981';
    banner.innerHTML = `<strong>✅ Engineer Review: ACCEPTED</strong> — Root cause verified and confirmed by engineer. ${notes ? `<div style="font-size:0.8rem; margin-top:3px; color:var(--text-secondary);">Feedback: ${escHtml(notes)}</div>` : ''}`;
    if (acceptBtn) { acceptBtn.disabled = true; acceptBtn.style.opacity = '0.6'; acceptBtn.style.display = 'inline-flex'; }
    if (rejectBtn) { rejectBtn.disabled = false; rejectBtn.style.opacity = '1'; rejectBtn.style.display = 'inline-flex'; }
  } else if (d === 'rejected') {
    banner.style.background = 'rgba(239, 68, 68, 0.12)';
    banner.style.border = '1px solid rgba(239, 68, 68, 0.35)';
    banner.style.color = '#ef4444';
    banner.innerHTML = `<strong>❌ Engineer Review: REJECTED</strong> — AI diagnosis rejected by engineer. ${notes ? `<div style="font-size:0.8rem; margin-top:3px; color:var(--text-secondary);">Reason: ${escHtml(notes)}</div>` : ''}`;
    if (acceptBtn) { acceptBtn.disabled = false; acceptBtn.style.opacity = '1'; acceptBtn.style.display = 'inline-flex'; }
    if (rejectBtn) { rejectBtn.disabled = true; rejectBtn.style.opacity = '0.6'; rejectBtn.style.display = 'inline-flex'; }
  } else {
    banner.style.background = 'rgba(245, 158, 11, 0.10)';
    banner.style.border = '1px solid rgba(245, 158, 11, 0.30)';
    banner.style.color = '#f59e0b';
    banner.innerHTML = `<strong>⏳ Engineer Review: PENDING</strong> — Awaiting engineer evaluation. Click Accept or Reject above.`;
    if (acceptBtn) { acceptBtn.disabled = false; acceptBtn.style.opacity = '1'; acceptBtn.style.display = 'inline-flex'; }
    if (rejectBtn) { rejectBtn.disabled = false; rejectBtn.style.opacity = '1'; rejectBtn.style.display = 'inline-flex'; }
  }
}

async function decideCurrent(decision) {
  if (!_currentIncidentNumber) return;
  const promptText = decision === 'accepted'
    ? 'Optional engineer feedback / validation notes:'
    : 'Reason for rejecting this AI diagnosis:';
  const notes = prompt(promptText, decision === 'accepted' ? 'Confirmed root cause by engineer.' : 'Diagnosis does not match system logs.');
  if (notes === null) return; // User cancelled prompt

  try {
    const res = await apiFetch(`/api/incidents/${_currentIncidentNumber}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        incident_number: _currentIncidentNumber,
        decision: decision,
        engineer_notes: notes || `Recorded ${decision.toUpperCase()} on dashboard.`
      })
    });
    if (_currentRca) {
      _currentRca.decision = decision;
      _currentRca.decision_notes = notes || `Recorded ${decision.toUpperCase()} on dashboard.`;
    }
    renderDecisionStatus(decision, notes || `Recorded ${decision.toUpperCase()} on dashboard.`);
    toast(`Incident ${_currentIncidentNumber} marked as ${decision.toUpperCase()}!`, 'success');
  } catch(e) {
    toast(`Failed to record decision: ${e.message}`, 'error');
  }
}

// ── RCA Evaluation History (Accepted & Rejected, Exempting Pending) ──────────
let _allHistory = [];
let _historyFilter = 'all';

async function loadHistoryTab() {
  const tbody = document.getElementById('history-tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Loading evaluated history…</td></tr>';
  }
  try {
    _allHistory = await apiFetch('/api/incidents/history/decisions');
    renderHistoryTable();
  } catch(e) {
    console.error('Failed to load history:', e);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-cell text-danger">Failed to load history: ${escHtml(e.message)}</td></tr>`;
    }
  }
}

function filterHistory(filter) {
  _historyFilter = filter;
  ['all', 'accepted', 'rejected'].forEach(f => {
    const el = document.getElementById('hf-' + f);
    if (el) el.classList.toggle('active', f === filter);
  });
  renderHistoryTable();
}

function renderHistoryTable() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  let items = _allHistory || [];
  if (_historyFilter === 'accepted') {
    items = items.filter(r => (r.decision || '').toLowerCase() === 'accepted');
  } else if (_historyFilter === 'rejected') {
    items = items.filter(r => (r.decision || '').toLowerCase() === 'rejected');
  }

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-cell">No evaluated incidents matching "<strong>${_historyFilter}</strong>". (Pending incidents are exempted).</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(r => `
    <tr>
      <td><code>${escHtml(r.incident_number)}</code></td>
      <td>${renderDecisionBadge(r.decision)}</td>
      <td title="${escHtml(r.probable_root_cause)}">${escHtml(truncate(r.probable_root_cause, 60))}</td>
      <td><span class="badge badge-${r.confidence_label}">${r.confidence_label} ${(r.confidence_score*100).toFixed(0)}%</span></td>
      <td><span class="badge badge-blue">${escHtml(r.recommended_team || '—')}</span></td>
      <td style="max-width:200px; font-size:0.8rem; color:var(--text-secondary);" title="${escHtml(r.decision_notes || '')}">
        ${escHtml(truncate(r.decision_notes || '—', 50))}
      </td>
      <td style="font-size:0.75rem; color:var(--text-muted);">${formatDate(r.decided_at || r.analyzed_at)}</td>
      <td>
        <button class="btn btn-sm btn-ghost" onclick="viewHistoryIncident('${escHtml(r.incident_number)}')">🔍 View RCA</button>
      </td>
    </tr>
  `).join('');
}

async function viewHistoryIncident(incNum) {
  showTab('analyze');
  viewRca(incNum);
}

