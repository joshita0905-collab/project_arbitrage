const configuredApiBase = new URLSearchParams(window.location.search).get('apiBase')
  || window.PROJECT_ARBITRAGE_CONFIG?.apiBaseUrl
  || 'http://127.0.0.1:8000';
const API_BASE = `${configuredApiBase.replace(/\/+$/, '').replace(/\/api$/, '')}/api`;

const state = {
  health: null,
  dashboard: null,
  exposures: [],
  policies: [],
  memories: [],
  assessment: null,
  assessmentError: null,
  refreshing: false,
  audit: [],
  records: [],
  memoryOverview: null,
  memoryError: null,
  currentView: 'dashboard',
  currentRecord: null,
};

const els = {
  loginScreen: document.getElementById('login-screen'),
  dashboardShell: document.getElementById('dashboard-shell'),
  loginForm: document.getElementById('login-form'),
  loginId: document.getElementById('login-id'),
  loginPassword: document.getElementById('login-password'),
  loginError: document.getElementById('login-error'),
  signOut: document.getElementById('sign-out'),
  dashboardContent: document.querySelector('.dashboard'),
  historyView: document.getElementById('history-view'),
  memoryView: document.getElementById('memory-view'),
  historyRows: document.getElementById('history-rows'),
  historyEmpty: document.getElementById('history-empty'),
  historyTableWrap: document.getElementById('history-table-wrap'),
  historyCount: document.getElementById('history-count'),
  recordDetail: document.getElementById('record-detail'),
  dashboardRecordStats: document.getElementById('dashboard-record-stats'),
  recentRecords: document.getElementById('recent-records'),
  memoryStats: document.getElementById('memory-stats'),
  memoryTimeline: document.getElementById('memory-timeline'),
  memoryViewStatus: document.getElementById('memory-view-status'),
  refreshMemory: document.getElementById('refresh-memory'),
  simulateActionForm: document.getElementById('simulate-action-form'),
  simulatedActionDescription: document.getElementById('simulated-action-description'),
  simulatedActionResult: document.getElementById('simulated-action-result'),
  healthPill: document.getElementById('health-pill'),
  refreshButton: document.getElementById('refresh-assessment'),
  greeting: document.getElementById('greeting'),
  localDateTime: document.getElementById('local-date-time'),
  requestStatus: document.getElementById('request-status'),
  marketSourceStatus: document.getElementById('market-source-status'),
  hindsightSourceStatus: document.getElementById('hindsight-source-status'),
  aiSourceStatus: document.getElementById('ai-source-status'),
  lastUpdated: document.getElementById('last-updated'),
  shockScenario: document.getElementById('shock-scenario'),
  shockNote: document.getElementById('shock-note'),
  shockCurrency: document.getElementById('shock-currency'),
  shockMove: document.getElementById('shock-move'),
  shockRate: document.getElementById('shock-rate'),
  riskLevel: document.getElementById('risk-level'),
  riskRecommendation: document.getElementById('risk-recommendation'),
  riskScore: document.getElementById('risk-score'),
  riskScoreScale: document.getElementById('risk-score-scale'),
  policyStatus: document.getElementById('policy-status'),
  guardrailStatus: document.getElementById('guardrail-status'),
  approvalState: document.getElementById('approval-state'),
  approvalNote: document.getElementById('approval-note'),
  exposuresList: document.getElementById('exposures-list'),
  policiesList: document.getElementById('policies-list'),
  memoryList: document.getElementById('memory-list'),
  guardrailBox: document.getElementById('guardrail-box'),
  executiveSummary: document.getElementById('executive-summary'),
  proposedActions: document.getElementById('proposed-actions'),
  auditList: document.getElementById('audit-list'),
  exposureInputList: document.getElementById('exposure-input-list'),
  policyInputList: document.getElementById('policy-input-list'),
  exposureForm: document.getElementById('exposure-form'),
  policyForm: document.getElementById('policy-form'),
  decisionForm: document.getElementById('decision-form'),
  decisionSelect: document.getElementById('decision-select'),
  decisionRationale: document.getElementById('decision-rationale'),
  decisionNotes: document.getElementById('decision-notes'),
};

const DEMO_SESSION_KEY = 'project-arbitrage-demo-session';

function showDashboard() {
  state.currentView = 'dashboard';
  els.loginScreen.hidden = true;
  els.dashboardShell.hidden = false;
  window.location.hash = 'dashboard';
  refreshDashboard({ runAssessment: false });
}

function showLogin() {
  els.dashboardShell.hidden = true;
  els.loginScreen.hidden = false;
  window.location.hash = 'login';
}

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

async function api(path, options = {}) {
  const endpoint = `${API_BASE}${path}`;
  const headers = { Accept: 'application/json', ...options.headers };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';

  let response;
  try {
    response = await fetch(endpoint, { ...options, headers, mode: 'cors' });
  } catch (error) {
    throw new Error(`Could not reach ${endpoint}. Check that the API is running and allows this dashboard origin (${error.message}).`);
  }

  if (!response.ok) {
    const responseText = await response.text();
    let detail = responseText || response.statusText;
    try {
      const parsed = JSON.parse(responseText);
      detail = parsed.detail || parsed.message || detail;
    } catch {
      // Keep plain-text backend errors readable.
    }
    throw new Error(`${endpoint} returned HTTP ${response.status}: ${detail}`);
  }

  return response.headers.get('content-type')?.includes('application/json') ? response.json() : {};
}

function badgeLabel(value, kind = 'info') {
  return `<span class="badge ${kind}">${value}</span>`;
}

function normalizePolicyFlags(value) {
  if (Array.isArray(value)) {
    return value;
  }

  if (value && typeof value === 'object') {
    if (Array.isArray(value.thresholds_exceeded)) {
      return value.thresholds_exceeded;
    }

    if (Array.isArray(value.triggered_policies)) {
      return value.triggered_policies.map((entry) => entry?.id || entry?.name || '');
    }
  }

  if (typeof value === 'string') {
    return [value];
  }

  return [];
}

function recordDate(value) {
  return value ? new Date(value).toLocaleString() : 'Not recorded';
}

function recordDisplay(value) {
  if (value === null || value === undefined || value === '') return 'Not recorded';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function renderRecordStats() {
  const counts = state.dashboard?.record_counts || {};
  const memoryCount = state.memoryOverview?.total_units;
  const metrics = [
    ['Market assessments', counts.events ?? 0],
    ['Human decisions', counts.decisions ?? 0],
    ['Simulated outcomes', counts.outcomes ?? 0],
    ['Hindsight memory units', state.memoryError ? 'Unavailable' : memoryCount ?? 'Not queried'],
  ];
  const html = metrics.map(([label, value]) => `
    <div class="record-stat"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>
  `).join('');
  els.dashboardRecordStats.innerHTML = html;
}

function renderRecentRecords() {
  const records = state.dashboard?.recent_records || [];
  if (!records.length) {
    els.recentRecords.innerHTML = '<div class="empty-state"><strong>No treasury records yet</strong><p>Complete a market assessment and submit a decision to create the first organizational memory.</p></div>';
    return;
  }
  els.recentRecords.innerHTML = records.slice(0, 5).map((record) => `
    <div class="recent-record-row">
      <div><strong>${escapeHTML(record.event || 'Market assessment')}</strong><small class="muted-list">${escapeHTML(recordDate(record.timestamp))}</small></div>
      <span>${escapeHTML(record.currency || 'Not recorded')}</span>
      <span>${record.market_move_pct == null ? 'Not recorded' : `${Number(record.market_move_pct).toFixed(4)}%`}</span>
      <span>${escapeHTML(record.decision || record.risk_level || 'Assessment only')}</span>
      <button class="record-open" type="button" data-record-id="${escapeHTML(record.record_id)}">View</button>
    </div>
  `).join('');
}

function renderHistory() {
  const records = state.records;
  els.historyCount.textContent = `${records.length} ${records.length === 1 ? 'record' : 'records'} loaded`;
  els.historyEmpty.hidden = records.length > 0;
  els.historyTableWrap.hidden = records.length === 0;
  if (!records.length) {
    els.historyRows.innerHTML = '';
    return;
  }
  els.historyRows.innerHTML = records.map((record) => `
    <tr>
      <td>${escapeHTML(recordDate(record.timestamp))}</td>
      <td><button class="record-open" type="button" data-record-id="${escapeHTML(record.record_id)}">${escapeHTML(record.event || 'Market assessment')}</button></td>
      <td>${escapeHTML(record.currency || 'Not recorded')}</td>
      <td>${record.market_move_pct == null ? 'Not recorded' : `${Number(record.market_move_pct).toFixed(4)}%`}</td>
      <td>${escapeHTML(record.risk_level || 'Not recorded')}</td>
      <td>${escapeHTML(record.decision || record.agent_action || 'Not recorded')}</td>
      <td>${escapeHTML(record.outcome || 'Not recorded')}</td>
      <td>${escapeHTML(record.hindsight_retention_status || record.hindsight_recall_status || 'Not recorded')}</td>
    </tr>
  `).join('');
}

function renderMemoryOverview() {
  if (state.memoryError) {
    els.memoryViewStatus.textContent = 'Hindsight unavailable for memory listing.';
    els.memoryViewStatus.dataset.state = 'error';
    els.memoryStats.innerHTML = '<div class="record-stat"><span>Hindsight memory units</span><strong>Unavailable</strong></div><div class="record-stat"><span>Event / decision / outcome counts</span><strong>Unavailable</strong></div>';
    els.memoryTimeline.innerHTML = '<div class="empty-state"><strong>Hindsight unavailable</strong><p>Memory records could not be loaded from Vectorize Hindsight.</p></div>';
    return;
  }
  const overview = state.memoryOverview;
  if (!overview) {
    els.memoryViewStatus.textContent = 'Hindsight memory has not been queried.';
    els.memoryViewStatus.dataset.state = 'loading';
    return;
  }
  els.memoryViewStatus.textContent = overview.total_units
    ? `Queried Vectorize Hindsight · ${overview.total_units} actual memory units returned.`
    : 'Queried Vectorize Hindsight · no stored memory units found.';
  els.memoryViewStatus.dataset.state = 'success';
  els.memoryStats.innerHTML = `
    <div class="record-stat"><span>Hindsight memory units</span><strong>${Number(overview.total_units).toLocaleString()}</strong></div>
    <div class="record-stat"><span>Market event count</span><strong>Unavailable</strong><small>Hindsight does not expose this category count.</small></div>
    <div class="record-stat"><span>Decision count</span><strong>Unavailable</strong><small>Hindsight does not expose this category count.</small></div>
    <div class="record-stat"><span>Outcome count</span><strong>Unavailable</strong><small>Hindsight does not expose this category count.</small></div>
  `;
  if (!overview.records.length) {
    els.memoryTimeline.innerHTML = '<div class="empty-state"><strong>No Hindsight memories available</strong><p>Complete a market assessment and submit a decision to create the first organizational memory.</p></div>';
    return;
  }
  els.memoryTimeline.innerHTML = overview.records.map((memory) => `
    <article class="memory-timeline-item">
      <time>${escapeHTML(recordDate(memory.timestamp))} · ${escapeHTML(memory.fact_type || 'Unclassified memory unit')}</time>
      <strong>${escapeHTML(memory.context || 'Hindsight memory')}</strong>
      <p>${escapeHTML(memory.text)}</p>
    </article>
  `).join('');
}

function detailStep(title, value) {
  if (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)) return '';
  return `<article class="record-flow-step"><h4>${escapeHTML(title)}</h4><pre>${escapeHTML(recordDisplay(value))}</pre></article>`;
}

function renderRecordDetail(record) {
  els.recordDetail.hidden = false;
  els.recordDetail.innerHTML = `
    <div class="panel-header">
      <div><p class="section-tag">Persistent treasury cycle</p><h3>${escapeHTML(record.record_id)}</h3><p class="muted">${escapeHTML(recordDate(record.timestamp))}</p></div>
      <button type="button" class="secondary" data-close-record>Close details</button>
    </div>
    <div class="record-flow">
      ${detailStep('Market event', record.market_event)}
      ${detailStep('Company exposure', record.exposures)}
      ${detailStep('Policy', record.policies)}
      ${detailStep('Risk + guardrails', { risk: record.risk_calculation, guardrail: record.guardrail })}
      ${detailStep('Hindsight recall', record.hindsight_memories?.length ? record.hindsight_memories : record.hindsight_recall_status === 'no_match' ? 'No relevant historical memory found.' : record.hindsight_recall_status)}
      ${detailStep('Agent analysis', record.agent_analysis)}
      ${detailStep('Human decision', record.human_decision)}
      ${detailStep('Simulated action', record.simulated_action)}
      ${detailStep('Outcome', record.simulated_action?.outcome)}
      ${detailStep('Hindsight retention', { status: record.simulated_action?.hindsight_retention_status || record.human_decision?.hindsight_retention_status || record.hindsight_retention_status, reference: record.simulated_action?.hindsight_reference || record.human_decision?.hindsight_reference || record.hindsight_reference })}
      ${detailStep('Audit information', record.audit)}
    </div>
  `;
}

async function loadRecordDetail(recordId) {
  els.recordDetail.hidden = false;
  els.recordDetail.textContent = 'Loading persisted record...';
  try {
    state.currentRecord = await api(`/records/${encodeURIComponent(recordId)}`);
    renderRecordDetail(state.currentRecord);
  } catch (error) {
    els.recordDetail.textContent = `Record details unavailable: ${error.message}`;
  }
}

async function refreshPersistentViews() {
  const [dashboardResult, recordsResult, auditResult, memoryResult] = await Promise.all([
    api('/dashboard').then((data) => ({ data })).catch((error) => ({ error })),
    api('/records?limit=500').then((data) => ({ data })).catch((error) => ({ error })),
    api('/audit').then((data) => ({ data })).catch((error) => ({ error })),
    api('/memory').then((data) => ({ data })).catch((error) => ({ error })),
  ]);
  if (dashboardResult.data) state.dashboard = dashboardResult.data;
  if (recordsResult.data) state.records = recordsResult.data;
  if (auditResult.data) state.audit = auditResult.data;
  state.memoryOverview = memoryResult.data || null;
  state.memoryError = memoryResult.error || null;
  renderRecordStats();
  renderRecentRecords();
  renderHistory();
  renderMemoryOverview();
  renderAudit();
  renderSourceStatus();
}

function setCurrentView(view) {
  state.currentView = view;
  const dashboardVisible = view === 'dashboard';
  els.dashboardContent.hidden = !dashboardVisible;
  els.historyView.hidden = view !== 'history';
  els.memoryView.hidden = view !== 'memory';
  document.querySelectorAll('.app-nav .nav-link[data-view]').forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  window.location.hash = view;
  if (view === 'history' || view === 'memory') {
    refreshPersistentViews().catch((error) => {
      els.requestStatus.textContent = error.message;
      els.requestStatus.dataset.state = 'error';
    });
  }
}

function renderHealth() {
  const marketConnected = Boolean(state.dashboard?.market);
  const hasProviderError = Boolean(state.assessmentError && !state.assessmentError.message.includes('No exposure data') && !state.assessmentError.message.includes('No policies are configured'));
  const label = marketConnected
    ? 'LIVE MARKET · CONNECTED'
    : hasProviderError
      ? 'LIVE DATA UNAVAILABLE'
      : 'Connecting to backend';
  const className = marketConnected ? 'ok' : hasProviderError ? 'fail' : 'warn';

  els.healthPill.textContent = label;
  els.healthPill.className = `status-pill ${className}`;
}

function updateLocalClock() {
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour >= 5 && hour < 12
    ? 'Good morning'
    : hour >= 12 && hour < 17
      ? 'Good afternoon'
      : hour >= 17 && hour < 21
        ? 'Good evening'
        : 'Good night';

  els.greeting.textContent = `${greeting}, Treasury Team`;
  els.localDateTime.textContent = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'full',
    timeStyle: 'short',
  }).format(now);
}

function renderShock() {
  const shock = state.assessment?.shock || state.dashboard?.market;
  if (!shock) {
    els.shockScenario.textContent = state.refreshing
      ? 'Connecting to live market data...'
      : 'LIVE MARKET DATA UNAVAILABLE';
    els.shockNote.textContent = state.assessmentError?.message || '';
    els.shockCurrency.textContent = '--';
    els.shockMove.textContent = '--';
    els.shockRate.textContent = '--';
    return;
  }

  els.shockScenario.textContent = shock.scenario || `Live ${shock.currency_pair} reference rate`;
  els.shockNote.textContent = `${shock.source} · published ${shock.latest_date || shock.market_date} · retrieved ${new Date(shock.retrieved_at).toLocaleString()}`;
  els.shockCurrency.textContent = shock.currency_pair || '--';
  els.shockMove.textContent = `${Number(shock.market_move_pct).toFixed(4)}%`;
  els.shockRate.textContent = Number(shock.spot_rate).toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function renderExposureSummary() {
  if (!state.exposures.length) {
    els.exposuresList.innerHTML = '<div class="muted-list">No exposure data available.</div>';
    return;
  }

  els.exposuresList.innerHTML = state.exposures.map((item) => `
    <div class="exposure-row">
      <div class="exposure-head">
        <strong>${escapeHTML(item.entity)}</strong>
        ${badgeLabel(escapeHTML(item.source || 'unknown source'), item.source === 'user_entered' ? 'good' : 'warn')}
      </div>
      <div class="muted-list">
        ${escapeHTML(item.currency)} · ${Number(item.amount).toLocaleString()} · Maturity ${item.maturity_days}d
      </div>
      <div class="muted-list">Hedge cover: ${Number(item.hedged_pct).toFixed(0)}%</div>
    </div>
  `).join('');
}

function renderPolicies() {
  if (!state.policies.length) {
    els.policiesList.innerHTML = '<div class="muted-list">No policy thresholds entered yet. Add your actual policy limits to assess breaches.</div>';
    return;
  }

  const breached = normalizePolicyFlags(state.assessment?.policy_flags);
  const breachedSet = new Set(breached.map((item) => String(item)));

  els.policiesList.innerHTML = state.policies.map((policy) => {
    const policyId = String(policy.id || policy.name || '');
    const active = breachedSet.has(policy.id) || breachedSet.has(policy.name) || breached.some((item) => String(item).includes(policyId));
    const status = state.assessment ? (active ? 'BREACHED' : 'WITHIN BAND') : 'NOT ASSESSED';
    return `
      <div class="policy-item ${active ? 'active' : ''}">
        <div class="policy-head">
          <strong>${escapeHTML(policy.name)}</strong>
          ${badgeLabel(status, state.assessment ? (active ? 'danger' : 'good') : 'warn')}
        </div>
        <div class="muted-list">${escapeHTML(policy.category)} · threshold ${Number(policy.threshold).toLocaleString()}</div>
        <div class="muted-list">${escapeHTML(policy.description || '')}</div>
      </div>
    `;
  }).join('');
}

function renderInputSummaries() {
  els.exposureInputList.innerHTML = state.exposures.length
    ? state.exposures.map((exposure) => `<div class="muted-list">${escapeHTML(exposure.entity)} · ${escapeHTML(exposure.currency)} ${Number(exposure.amount).toLocaleString()} · source: ${escapeHTML(exposure.source)}</div>`).join('')
    : '<div class="muted-list">No exposure records saved. Risk assessment is disabled until actual exposure input is provided.</div>';
  els.policyInputList.innerHTML = state.policies.length
    ? state.policies.map((policy) => `<div class="muted-list">${escapeHTML(policy.name)} · ${escapeHTML(policy.category)} ≥ ${Number(policy.threshold).toLocaleString()} · source: ${escapeHTML(policy.source)}</div>`).join('')
    : '<div class="muted-list">No policy records saved. Risk assessment is disabled until actual policy thresholds are provided.</div>';
}

function renderSourceStatus() {
  const market = state.dashboard?.market;
  const assessmentError = state.assessmentError?.message || '';
  els.marketSourceStatus.textContent = market
    ? `Market: LIVE · ${market.source} · ${market.latest_date}`
    : 'Market: LIVE DATA UNAVAILABLE';
  els.marketSourceStatus.dataset.state = market ? 'success' : 'error';
  const hindsightRecallFailed = assessmentError.includes('Official Hindsight recall failed');
  const hindsightRetentionFailed = assessmentError.includes('Official Hindsight retention failed');
  const groqFailed = assessmentError.includes('Groq live assessment failed');
  const hindsightCompleted = Boolean(state.assessment) || groqFailed || hindsightRetentionFailed || Boolean(state.memoryOverview);
  const groqCompleted = Boolean(state.assessment) || hindsightRetentionFailed;
  els.hindsightSourceStatus.textContent = state.assessment
    ? state.assessment.hindsight_recall_status === 'matched'
      ? `Hindsight: MATCH FOUND · ${state.memories.length} recalled · ${state.assessment.hindsight_retention_status || 'retention unknown'}`
      : `Hindsight: QUERIED · no relevant match · ${state.assessment.hindsight_retention_status || 'retention unknown'}`
    : hindsightRecallFailed
      ? 'Hindsight: RECALL UNAVAILABLE'
      : hindsightRetentionFailed
        ? 'Hindsight: RECALL COMPLETE · RETENTION FAILED'
        : groqFailed
          ? 'Hindsight: LIVE · recall complete'
          : state.memoryError
            ? 'Hindsight: UNAVAILABLE'
            : state.memoryOverview
              ? `Hindsight: QUERIED · ${state.memoryOverview.total_units} stored units`
              : 'Hindsight: NOT USED YET';
  els.hindsightSourceStatus.dataset.state = state.assessment || hindsightCompleted ? 'success' : hindsightRecallFailed || hindsightRetentionFailed ? 'error' : 'loading';
  els.aiSourceStatus.textContent = state.assessment
    ? 'AI reasoning: COMPLETE'
    : groqFailed
      ? 'AI reasoning: UNAVAILABLE'
      : hindsightRetentionFailed
        ? 'AI reasoning: COMPLETE'
        : 'AI reasoning: NOT RUN YET';
  els.aiSourceStatus.dataset.state = groqCompleted ? 'success' : groqFailed ? 'error' : 'loading';
  if (state.dashboard?.market?.retrieved_at) {
    els.lastUpdated.textContent = `Last updated: ${new Date(state.dashboard.market.retrieved_at).toLocaleString()}`;
  }
}

function renderMemoryList() {
  const memories = state.memories;

  if (!memories.length) {
    const message = state.assessmentError
      ? 'Official Hindsight recall is unavailable without a successful live assessment. No substitute memory is shown.'
      : state.assessment?.hindsight_recall_status === 'no_match'
        ? 'No relevant historical memory found.'
        : state.assessmentError
          ? 'Hindsight unavailable for this assessment. No substitute memory is shown.'
          : 'Hindsight recall runs when a complete live assessment is available.';
    els.memoryList.innerHTML = `<div class="muted-list">${message}</div>`;
    return;
  }

  els.memoryList.innerHTML = `
    ${memories.slice(0, 5).map((item) => `
      <div class="memory-item">
        <div class="memory-head">
          <strong>${item.type || 'historical precedent'}</strong>
          ${badgeLabel('Hindsight', 'good')}
        </div>
        <p>${escapeHTML(item.text || item.content || '')}</p>
      </div>
    `).join('')}
  `;
}

function renderGuardrail() {
  if (!state.assessment) {
    els.guardrailBox.textContent = 'Guardrail evaluation is unavailable until the live assessment succeeds.';
    return;
  }

  const guardrail = state.assessment?.guardrail || {};
  const guardStatus = guardrail.guardrail_status || state.assessment?.guardrail_status || 'PRECEDENT_INTACT';
  const manualOverride = guardrail.manual_override_required ?? false;
  const variance = guardrail.precedent_variance_index ?? state.assessment?.precedent_variance_index ?? 0;

  els.guardrailBox.innerHTML = `
    <p><strong>Guardrail status:</strong> ${guardStatus}</p>
    <p><strong>Manual override required:</strong> ${manualOverride ? 'Yes' : 'No'}</p>
    <p><strong>Precedent variance index:</strong> ${variance === null ? 'Unavailable' : Number(variance).toFixed(4)}</p>
    <p><strong>Safety:</strong> ${escapeHTML(guardrail.safety_message || 'No guardrail status provided.')}</p>
  `;
}

function renderAssessment() {
  const assessment = state.assessment;
  const submitButton = els.decisionForm.querySelector('button[type="submit"]');
  submitButton.disabled = !assessment || Boolean(assessment.human_decision);
  els.simulateActionForm.hidden = !assessment
    || assessment.human_decision?.decision !== 'APPROVE'
    || Boolean(assessment.simulated_action);
  if (!assessment?.simulated_action) {
    els.simulatedActionResult.hidden = true;
  } else {
    const action = assessment.simulated_action;
    els.simulatedActionResult.hidden = false;
    els.simulatedActionResult.innerHTML = `
      <p><strong>SIMULATION ONLY · NO REAL FUNDS MOVED</strong></p>
      <p>Action: ${escapeHTML(action.action)}</p>
      <p>Action ID: ${escapeHTML(action.action_id)}</p>
      <p>Status: ${escapeHTML(action.status)}</p>
      <p>Outcome: ${escapeHTML(action.outcome)}</p>
      <p>Hindsight retention: ${escapeHTML(action.hindsight_retention_status || 'pending')}</p>
    `;
  }

  if (!assessment) {
    const missingInputs = [];
    if (!state.exposures.length) missingInputs.push('an exposure');
    if (!state.policies.length) missingInputs.push('a policy threshold');
    const inputRequired = !state.assessmentError && missingInputs.length > 0;
    const message = state.assessmentError
      ? `LIVE DATA UNAVAILABLE: ${state.assessmentError.message}. No synthetic assessment is shown.`
      : state.refreshing
        ? 'Connecting to Project Arbitrage...'
      : inputRequired
        ? `Add ${missingInputs.join(' and ')} to generate an assessment.`
        : 'Waiting for the live backend assessment.';
    els.riskLevel.textContent = '--';
    els.riskRecommendation.textContent = state.assessmentError
      ? 'LIVE DATA UNAVAILABLE'
      : state.refreshing
        ? 'CONNECTING'
        : inputRequired
          ? 'INPUT REQUIRED'
          : 'ASSESSMENT UNAVAILABLE';
    els.riskScore.textContent = '--';
    els.policyStatus.textContent = 'NOT ASSESSED';
    els.guardrailStatus.textContent = 'NOT EVALUATED';
    els.approvalState.textContent = 'HUMAN REVIEW REQUIRED';
    els.approvalNote.textContent = 'Decision submission is disabled until a live assessment is available.';
    els.executiveSummary.textContent = message;
    const calculation = state.assessmentError
      ? 'Live assessment is unavailable. Check the service status and try again.'
      : inputRequired
        ? `Add ${missingInputs.join(' and ')} before calculating risk.`
      : 'Assessment is not available.';
    document.getElementById('risk-calculation').textContent = calculation;
    els.proposedActions.innerHTML = '<li>No actions proposed because the live assessment is unavailable.</li>';
    return;
  }

  const policyFlags = normalizePolicyFlags(assessment.policy_flags);

  els.riskLevel.textContent = assessment.risk_level || '--';
  els.riskRecommendation.textContent = assessment.recommendation || 'HUMAN_REVIEW_REQUIRED';
  els.riskScore.textContent = Number(assessment.risk_score || 0).toFixed(2);
  els.policyStatus.textContent = policyFlags.length ? 'BREACHED' : 'CLEAR';
  els.guardrailStatus.textContent = assessment.guardrail_status || 'PRECEDENT_INTACT';
  els.approvalState.textContent = assessment.requires_human_approval ? 'HUMAN APPROVAL REQUIRED' : 'AUTO-APPROVAL DISABLED';
  els.approvalNote.textContent = assessment.requires_human_approval ? 'No autonomous trading or payment execution.' : 'Approval not required.';
  if (assessment.human_decision) {
    els.approvalState.textContent = assessment.human_decision.decision;
    els.approvalNote.textContent = 'Human decision already persisted for this assessment.';
    els.decisionSelect.value = assessment.human_decision.decision;
    els.decisionRationale.value = assessment.human_decision.rationale || '';
    els.decisionNotes.value = assessment.human_decision.notes || '';
  }
  els.executiveSummary.textContent = assessment.executive_summary || 'No executive summary provided.';
  document.getElementById('risk-calculation').textContent = `${assessment.risk_calculation.risk_calculation.formula}. Inputs: ${JSON.stringify(assessment.risk_calculation.risk_calculation.inputs)}. Components: ${JSON.stringify(assessment.risk_calculation.risk_calculation.components)}.`;

  els.proposedActions.innerHTML = (assessment.proposed_actions || []).map((item) => `<li>${escapeHTML(item)}</li>`).join('') || '<li>No protective actions returned.</li>';
}

function renderAudit() {
  if (!state.audit.length) {
    els.auditList.innerHTML = '<div class="muted-list">No audit events recorded yet.</div>';
    return;
  }

  els.auditList.innerHTML = state.audit.slice(-5).reverse().map((entry) => `
    <div class="audit-item">
      <div class="policy-head">
        <strong>${escapeHTML(entry.event || 'Audit event')}</strong>
        ${badgeLabel(new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), 'warn')}
      </div>
      <p>${escapeHTML(JSON.stringify(entry.payload || entry).slice(0, 140))}${JSON.stringify(entry.payload || entry).length > 140 ? '…' : ''}</p>
    </div>
  `).join('');
}

async function refreshDashboard({ runAssessment = true } = {}) {
  state.refreshing = true;
  els.refreshButton.disabled = true;
  els.requestStatus.textContent = 'Connecting to Project Arbitrage...';
  els.requestStatus.dataset.state = 'loading';
  state.assessment = null;
  state.assessmentError = null;
  state.memories = [];
  state.dashboard = null;
  state.exposures = [];
  state.policies = [];
  state.audit = [];
  state.records = [];
  state.memoryOverview = null;
  state.memoryError = null;
  els.lastUpdated.textContent = 'Last updated: --';
  els.decisionForm.querySelector('button[type="submit"]').disabled = true;
  renderExposureSummary();
  renderPolicies();
  renderInputSummaries();
  renderMemoryList();
  renderAudit();
  renderShock();
  renderGuardrail();
  renderAssessment();
  els.marketSourceStatus.textContent = 'Market: retrieving current provider data';
  els.hindsightSourceStatus.textContent = 'Hindsight: waiting for an eligible assessment';
  els.aiSourceStatus.textContent = 'AI reasoning: waiting for an eligible assessment';

  try {
    const [health, dashboardResult, exposures, policies, audit, recordsResult, memoryResult] = await Promise.all([
      api('/health'),
      api('/dashboard').then((data) => ({ data })).catch((error) => ({ error })),
      api('/exposures'),
      api('/policies'),
      api('/audit'),
      api('/records?limit=500').then((data) => ({ data })).catch((error) => ({ error })),
      api('/memory').then((data) => ({ data })).catch((error) => ({ error })),
    ]);

    state.health = health;
    state.dashboard = dashboardResult.data || null;
    state.exposures = exposures;
    state.policies = policies;
    state.audit = audit;
    state.records = recordsResult.data || [];
    state.memoryOverview = memoryResult.data || null;
    state.memoryError = memoryResult.error || null;
    state.refreshing = false;
    const marketBaseCurrency = health.market_pair?.split('/')[0];
    if (marketBaseCurrency) document.getElementById('exposure-currency').value = marketBaseCurrency;
    renderHealth();
    renderShock();
    renderExposureSummary();
    renderPolicies();
    renderInputSummaries();
    renderAudit();
    renderRecordStats();
    renderRecentRecords();
    renderHistory();
    renderMemoryOverview();
    renderSourceStatus();

    if (dashboardResult.error) throw dashboardResult.error;
    const dashboard = dashboardResult.data;

    if (health.mock_mode) {
      throw new Error(`${API_BASE}/health reports mock_mode=true. Live assessment is blocked; no mock response will be displayed.`);
    }

    if (!dashboard.market) throw new Error(`${API_BASE}/dashboard did not return live market data.`);
    if (!runAssessment) {
      const latestRecord = dashboard.recent_records?.[0];
      if (latestRecord) {
        const savedAssessment = await api(`/records/${encodeURIComponent(latestRecord.record_id)}`);
        state.assessment = savedAssessment;
        state.memories = Array.isArray(savedAssessment.hindsight_memories)
          ? savedAssessment.hindsight_memories
          : [];
        els.requestStatus.textContent = `Loaded persisted treasury record ${latestRecord.record_id}. Use Refresh assessment to run a new live cycle.`;
        els.requestStatus.dataset.state = 'success';
      } else if (!state.exposures.length || !state.policies.length) {
        const needs = [!state.exposures.length ? 'actual exposure data' : '', !state.policies.length ? 'actual policy thresholds' : ''].filter(Boolean).join(' and ');
        els.requestStatus.textContent = `Live market data is connected. Add ${needs} below to enable risk assessment.`;
        els.requestStatus.dataset.state = 'success';
      } else {
        els.requestStatus.textContent = 'Live market, exposure, and policy data loaded. Click Refresh assessment to calculate risk.';
        els.requestStatus.dataset.state = 'success';
      }
      renderMemoryList();
      renderGuardrail();
      renderAssessment();
      renderSourceStatus();
      renderRecordStats();
      renderRecentRecords();
      return;
    }
    if (!state.exposures.length || !state.policies.length) {
      const needs = [!state.exposures.length ? 'actual exposure data' : '', !state.policies.length ? 'actual policy thresholds' : ''].filter(Boolean).join(' and ');
      els.requestStatus.textContent = `Live market data is connected. Add ${needs} below to enable risk assessment.`;
      els.requestStatus.dataset.state = 'success';
      els.riskRecommendation.textContent = 'INPUT REQUIRED';
      els.executiveSummary.textContent = 'Live market data is available. Enter real exposures and policy thresholds to calculate risk; no defaults are installed.';
      renderAssessment();
      return;
    }

    els.requestStatus.textContent = 'Running live Hindsight recall and AI assessment...';
    els.requestStatus.dataset.state = 'loading';
    const assessmentId = globalThis.crypto?.randomUUID?.() || `assessment-${Date.now()}`;

    try {
      state.refreshing = true;
      state.assessment = await api('/assess', {
        method: 'POST',
        body: JSON.stringify({ assessment_id: assessmentId }),
      });
      state.assessmentError = null;
      state.memories = Array.isArray(state.assessment.hindsight_memories)
        ? state.assessment.hindsight_memories
        : [];
      els.requestStatus.textContent = 'Live assessment complete. Official Hindsight recall and AI reasoning are displayed.';
      els.requestStatus.dataset.state = 'success';
      els.lastUpdated.textContent = `Last updated: ${new Date(state.assessment.market.retrieved_at).toLocaleString()}`;
      await refreshPersistentViews();
    } catch (error) {
      state.refreshing = false;
      state.assessment = null;
      state.assessmentError = error;
      state.memories = [];
      els.requestStatus.textContent = error.message;
      els.requestStatus.dataset.state = 'error';
    }

    renderHealth();
    renderShock();
    renderPolicies();
    renderMemoryList();
    renderRecordStats();
    renderRecentRecords();
    renderHistory();
    renderMemoryOverview();
    renderGuardrail();
    renderAssessment();
    renderSourceStatus();
  } catch (error) {
    state.refreshing = false;
    state.assessmentError = error;
    state.dashboard = null;
    els.requestStatus.textContent = error.message;
    els.requestStatus.dataset.state = 'error';
    els.marketSourceStatus.textContent = 'Market: LIVE DATA UNAVAILABLE';
    els.marketSourceStatus.dataset.state = 'error';
    if (error.message.includes('/api/memories') || error.message.includes('Hindsight')) {
      els.hindsightSourceStatus.textContent = 'Hindsight: UNAVAILABLE';
      els.hindsightSourceStatus.dataset.state = 'error';
    }
    console.error(error);
    renderHealth();
    renderShock();
    renderPolicies();
    renderMemoryList();
    renderGuardrail();
    renderAssessment();
    renderSourceStatus();
  } finally {
    state.refreshing = false;
    els.refreshButton.disabled = false;
  }
}

els.decisionForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!state.assessment || !state.assessment.assessment_id) return;

  const submitButton = els.decisionForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = 'Submitting...';
  els.requestStatus.textContent = 'Submitting the human decision to the backend...';
  els.requestStatus.dataset.state = 'loading';

  const payload = {
    decision: els.decisionSelect.value,
    rationale: els.decisionRationale.value,
    notes: els.decisionNotes.value,
    assessment_id: state.assessment.assessment_id,
  };

  let decisionSaved = false;
  try {
    const result = await api('/decision', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    decisionSaved = true;
    const record = await api(`/records/${encodeURIComponent(state.assessment.assessment_id)}`);
    state.assessment.human_decision = record.human_decision;
    state.assessment.simulated_action = record.simulated_action;
    await refreshPersistentViews();
    renderAssessment();
    els.approvalState.textContent = result.decision || 'DECISION RECORDED';
    els.approvalNote.textContent = result.hindsight_status === 'retained'
      ? 'Decision persisted and retained in Hindsight.'
      : 'Decision persisted locally; Hindsight retention is unavailable.';
    els.requestStatus.textContent = `Human decision ${result.decision} persisted. Record history refreshed.`;
    els.requestStatus.dataset.state = 'success';
  } catch (error) {
    els.requestStatus.textContent = decisionSaved
      ? `Decision was recorded, but refreshing ${API_BASE}/audit failed: ${error.message}`
      : error.message;
    els.requestStatus.dataset.state = 'error';
  } finally {
    submitButton.textContent = 'Submit decision';
    submitButton.disabled = !state.assessment;
  }
});

els.simulateActionForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!state.assessment?.assessment_id) return;
  const button = els.simulateActionForm.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Simulating...';
  els.requestStatus.textContent = 'Recording the approved simulation and outcome...';
  els.requestStatus.dataset.state = 'loading';
  try {
    const result = await api('/actions/simulate', {
      method: 'POST',
      body: JSON.stringify({
        assessment_id: state.assessment.assessment_id,
        action: els.simulatedActionDescription.value,
      }),
    });
    state.assessment.simulated_action = result;
    const record = await api(`/records/${encodeURIComponent(state.assessment.assessment_id)}`);
    state.assessment.human_decision = record.human_decision;
    state.assessment.simulated_action = record.simulated_action;
    await refreshPersistentViews();
    renderAssessment();
    els.requestStatus.textContent = 'Simulated action and outcome persisted. No real funds moved.';
    els.requestStatus.dataset.state = 'success';
  } catch (error) {
    els.requestStatus.textContent = error.message;
    els.requestStatus.dataset.state = 'error';
  } finally {
    button.disabled = false;
    button.textContent = 'Simulate approved action';
  }
});

els.exposureForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = els.exposureForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = 'Saving...';
  els.requestStatus.textContent = `Saving user-entered exposure to ${API_BASE}/exposures...`;
  els.requestStatus.dataset.state = 'loading';
  try {
    await api('/exposures', {
      method: 'POST',
      body: JSON.stringify({
        entity: document.getElementById('exposure-entity').value,
        currency: document.getElementById('exposure-currency').value,
        amount: document.getElementById('exposure-amount').value,
        maturity_days: Number(document.getElementById('exposure-maturity').value),
        hedged_pct: document.getElementById('exposure-hedged').value,
      }),
    });
    els.exposureForm.reset();
    document.getElementById('exposure-currency').value = state.health?.market_pair?.split('/')[0] || '';
    els.requestStatus.textContent = 'Exposure saved to backend storage. Refreshing live assessment...';
    els.requestStatus.dataset.state = 'success';
    await refreshDashboard();
  } catch (error) {
    els.requestStatus.textContent = error.message;
    els.requestStatus.dataset.state = 'error';
  } finally {
    submit.disabled = false;
    submit.textContent = 'Save exposure';
  }
});

els.policyForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = els.policyForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = 'Saving...';
  els.requestStatus.textContent = `Saving user-entered policy to ${API_BASE}/policies...`;
  els.requestStatus.dataset.state = 'loading';
  try {
    await api('/policies', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('policy-name').value,
        category: document.getElementById('policy-category').value,
        threshold: document.getElementById('policy-threshold').value,
        severity: document.getElementById('policy-severity').value,
        require_human_escalation: document.getElementById('policy-escalation').checked,
        description: document.getElementById('policy-description').value || null,
      }),
    });
    els.policyForm.reset();
    els.requestStatus.textContent = 'Policy saved to backend storage. Refreshing live assessment...';
    els.requestStatus.dataset.state = 'success';
    await refreshDashboard();
  } catch (error) {
    els.requestStatus.textContent = error.message;
    els.requestStatus.dataset.state = 'error';
  } finally {
    submit.disabled = false;
    submit.textContent = 'Save policy';
  }
});

window.addEventListener('DOMContentLoaded', () => {
  updateLocalClock();
  window.setInterval(updateLocalClock, 30_000);
  els.refreshButton.addEventListener('click', () => refreshDashboard({ runAssessment: true }));
  els.refreshMemory.addEventListener('click', refreshPersistentViews);
  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const viewButton = target.closest('[data-view]');
    if (viewButton) {
      setCurrentView(viewButton.dataset.view);
      return;
    }
    const scrollButton = target.closest('[data-scroll]');
    if (scrollButton) {
      setCurrentView('dashboard');
      requestAnimationFrame(() => document.querySelector(`.${scrollButton.dataset.scroll}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return;
    }
    const recordButton = target.closest('[data-record-id]');
    if (recordButton) {
      const recordId = recordButton.dataset.recordId;
      setCurrentView('history');
      loadRecordDetail(recordId);
      return;
    }
    if (target.closest('[data-close-record]')) {
      els.recordDetail.hidden = true;
      state.currentRecord = null;
    }
  });
  els.loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const validCredentials = els.loginId.value.trim().toLowerCase() === 'demo@arbitrage.com'
      && els.loginPassword.value === 'demo123';
    if (!validCredentials) {
      els.loginError.hidden = false;
      els.loginPassword.value = '';
      els.loginPassword.focus();
      return;
    }

    sessionStorage.setItem(DEMO_SESSION_KEY, 'signed-in');
    els.loginError.hidden = true;
    els.loginPassword.value = '';
    showDashboard();
  });
  els.signOut.addEventListener('click', () => {
    sessionStorage.removeItem(DEMO_SESSION_KEY);
    els.loginForm.reset();
    showLogin();
  });

  if (sessionStorage.getItem(DEMO_SESSION_KEY) === 'signed-in') {
    showDashboard();
  } else {
    showLogin();
  }
});
