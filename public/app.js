/* ============================================================
   Zycus Contract Authoring Agent — app.js (P4 task 4.5)
   ============================================================
   Vanilla JS, no frameworks, no build step (D-62).
   The frontend holds NO business logic — it renders whatever
   the API returns and replaces its state on every response. */

'use strict';

// --- State -------------------------------------------------------------------
let currentEnvelope = null;  // last RunEnvelope from the API
let scenarios = [];

// --- DOM refs ----------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// --- Init --------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  await loadScenarios();
  wireEvents();
});

async function loadScenarios() {
  try {
    const res = await fetch('/api/scenarios');
    scenarios = await res.json();
    const select = $('#scenario-select');
    select.innerHTML = '<option value="">— custom —</option>';
    for (const s of scenarios) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.id} — ${s.title}`;
      select.appendChild(opt);
    }
  } catch (e) {
    console.error('Failed to load scenarios', e);
  }
}

function wireEvents() {
  $('#scenario-select').addEventListener('change', onScenarioChange);
  $('#btn-generate').addEventListener('click', onGenerate);
  $$('.tab-btn').forEach(btn => btn.addEventListener('click', onTabClick));
}

function onScenarioChange(e) {
  const id = e.target.value;
  if (!id) return;
  const s = scenarios.find(sc => sc.id === id);
  if (!s) return;
  const fields = [
    'disclosing_party', 'receiving_party', 'effective_date', 'term',
    'governing_law', 'survival_period', 'purpose', 'special_clause',
    'payment_terms', 'contract_value',
  ];
  for (const f of fields) {
    const el = $(`#input-${f.replace(/_/g, '-')}`);
    if (el) el.value = s.inputs[f] || '';
  }
  $('#sim-ai-failure').checked = s.simulate_ai_failure || false;
}

async function onGenerate() {
  const btn = $('#btn-generate');
  btn.disabled = true;
  btn.classList.add('loading');
  clearError();

  const inputs = {};
  const fields = [
    'disclosing_party', 'receiving_party', 'effective_date', 'term',
    'governing_law', 'survival_period', 'purpose', 'special_clause',
    'payment_terms', 'contract_value',
  ];
  for (const f of fields) {
    const el = $(`#input-${f.replace(/_/g, '-')}`);
    inputs[f] = el ? el.value : '';
  }
  inputs.contract_type = 'mutual_nda';

  const simulate_ai_failure = $('#sim-ai-failure').checked;

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inputs, simulate_ai_failure }),
    });
    if (res.status === 422) {
      const err = await res.json();
      showError('Validation error: ' + (err.detail?.[0]?.msg || JSON.stringify(err.detail)));
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.detail || `Server error (${res.status}) — please retry`);
      return;
    }
    currentEnvelope = await res.json();
    renderAll();
  } catch (e) {
    showError('Network error — check your connection and retry');
    console.error(e);
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
}

// --- Tab switching -----------------------------------------------------------
function onTabClick(e) {
  const tab = e.currentTarget.dataset.tab;
  $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
}

// --- Render everything -------------------------------------------------------
function renderAll() {
  if (!currentEnvelope) return;
  const rr = currentEnvelope.run_result;
  renderBanner(rr);
  renderReviewTab(rr);
  renderDraftTab();
  renderTraceTab(rr);
  renderFieldTable(rr);
  loadRulesTab();
  // Activate review tab by default
  $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === 'review'));
  $$('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'tab-review'));
}

// --- Banner ------------------------------------------------------------------
function renderBanner(rr) {
  const banner = $('#banner');
  const readiness = rr.readiness;
  let cls, icon, label;
  if (readiness === 'BLOCKED') {
    cls = 'blocked'; icon = '🚫'; label = 'BLOCKED';
  } else if (readiness === 'NEEDS_REVIEW') {
    cls = 'needs-review'; icon = '⚠'; label = 'NEEDS REVIEW';
  } else {
    cls = 'ready'; icon = '✓'; label = 'READY FOR SIGNATURE REVIEW';
  }
  const reviewCount = rr.decisions.filter(d =>
    (d.status === 'NEEDS_REVIEW' || d.status === 'BLOCKED_MISSING') && !d.reviewer_action
  ).length;
  const reviewText = reviewCount > 0 ? ` — ${reviewCount} decision${reviewCount !== 1 ? 's' : ''} required` : '';

  // Run summary
  const trace = rr.trace || [];
  const agentSteps = trace.filter(s => s.kind === 'agent').length;
  const toolCalls = trace.reduce((n, s) => n + (s.tool_calls?.length || 0), 0);
  const totalTokens = trace.reduce((n, s) => n + (s.total_tokens || 0), 0);
  const wallMs = trace.reduce((n, s) => n + (s.duration_ms || 0), 0);

  const hasDocx = Boolean(currentEnvelope.docx_base64);
  const downloadDisabled = hasDocx ? '' : 'disabled';
  const downloadTitle = hasDocx ? 'Download draft as .docx' : (rr.qa?.passed === false ? 'QA check failed — download unavailable' : 'Download unavailable');

  banner.className = `banner ${cls}`;
  banner.style.display = 'flex';
  banner.innerHTML = `
    <span>${icon} ${label}${reviewText}</span>
    <div class="banner-actions">
      <span class="run-summary">${(wallMs/1000).toFixed(1)}s · ${agentSteps} LLM calls · ${toolCalls} tool calls · ${totalTokens.toLocaleString()} tokens</span>
      <button class="btn-download" id="btn-download" ${downloadDisabled} title="${downloadTitle}">
        ⬇ Download .docx
      </button>
    </div>
  `;
  $('#btn-download').addEventListener('click', downloadDocx);
}

function downloadDocx() {
  if (!currentEnvelope?.docx_base64) return;
  const bytes = Uint8Array.from(atob(currentEnvelope.docx_base64), c => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${currentEnvelope.run_result.run_id}.docx`;
  a.click();
  URL.revokeObjectURL(url);
}

// --- Review Tab --------------------------------------------------------------
function renderReviewTab(rr) {
  const container = $('#review-content');
  const groups = {
    'Needs Review': rr.decisions.filter(d => d.status === 'NEEDS_REVIEW'),
    'Blocked': rr.decisions.filter(d => d.status === 'BLOCKED_MISSING'),
    'Assumptions': rr.decisions.filter(d => d.status === 'AUTO_FILLED_WITH_ASSUMPTION'),
    'Not Applicable': rr.decisions.filter(d => d.status === 'NOT_APPLICABLE'),
    'Auto-filled': rr.decisions.filter(d => d.status === 'AUTO_FILLED'),
  };

  let html = '';
  for (const [title, items] of Object.entries(groups)) {
    if (items.length === 0) continue;
    html += `<div class="review-section">
      <div class="review-section-title">${title} (${items.length})</div>`;
    for (const d of items) {
      html += renderReviewCard(d, rr);
    }
    html += '</div>';
  }

  // Document notes
  if (rr.document_notes?.length) {
    html += '<div class="review-section"><div class="review-section-title">Document Notes</div>';
    for (const note of rr.document_notes) {
      html += `<div class="review-card"><span style="color:var(--text-secondary);font-size:0.82rem">ℹ ${escHtml(note)}</span></div>`;
    }
    html += '</div>';
  }

  container.innerHTML = html;
  wireReviewActions(rr);
}

function renderReviewCard(d, rr) {
  const statusCls = {
    'NEEDS_REVIEW': 'needs-review',
    'BLOCKED_MISSING': 'blocked',
    'AUTO_FILLED': 'auto-filled',
    'AUTO_FILLED_WITH_ASSUMPTION': 'assumption',
    'NOT_APPLICABLE': 'not-applicable',
  }[d.status] || '';

  const statusLabel = d.status.replace(/_/g, ' ');
  let html = `<div class="review-card" data-field="${d.field}">
    <div class="review-card-header">
      <span class="status-badge ${statusCls}">${statusLabel}</span>
      <span class="field-name">${displayFieldName(d.field)}</span>
      <span class="gate-badge">${d.gate}</span>
    </div>
    <div class="reason">${escHtml(d.reason)}</div>`;

  // Special clause extra detail
  if (d.field === 'special_clause' && rr.clause) {
    const c = rr.clause;
    const v = rr.verification;
    const verified = v ? v.checks.filter(ch => ch.present).length : 0;
    const total = v ? v.checks.length : 0;

    html += '<dl class="clause-detail">';
    html += `<dt>Request</dt><dd>${escHtml(c.request_summary)}</dd>`;
    if (c.risks?.length) html += `<dt>Risks</dt><dd>${c.risks.map(escHtml).join('; ')}</dd>`;
    if (c.conflicting_sections?.length) html += `<dt>Conflicts with §</dt><dd>${c.conflicting_sections.join(', ')}</dd>`;
    if (c.proposed_text) {
      html += `<dt>Proposed text</dt><dd>${escHtml(c.proposed_text)}</dd>`;
      html += `<dt>Source</dt><dd>`;
      const srcCls = { library: 'library', ai_drafted: 'ai-drafted', none: 'none' }[c.proposed_text_source] || 'none';
      html += `<span class="source-badge ${srcCls}">${c.proposed_text_source === 'library' ? '✓ Approved library' : c.proposed_text_source}</span>`;
      if (v) {
        const vCls = verified === total ? 'verified' : 'unverified';
        html += ` <span class="verification-badge ${vCls}">${verified}/${total} safeguards</span>`;
      }
      html += '</dd>';
    }
    if (d.reviewer_action === 'edit' && d.edited_text) {
      html += `<dt>Custom edited text</dt><dd class="edited-text-display">${escHtml(d.edited_text)}</dd>`;
    }
    html += '</dl>';

    // Safeguard warning banner (architecture §5.4: human decision stands)
    const safeguardWarning = (d.info_notes || []).find(n => n.includes('Warning: edited text lacks'));
    if (safeguardWarning) {
      html += `<div class="warning-banner">${escHtml(safeguardWarning)}</div>`;
    }

    // Actions
    const activeAction = d.reviewer_action;
    html += '<div class="clause-actions">';
    for (const [action, label] of [
      ['accept_proposed', 'Accept proposed'],
      ['use_as_requested', 'Use as requested'],
      ['remove', 'Remove clause'],
      ['edit', 'Edit text'],
    ]) {
      const activeCls = activeAction === action ? 'active-action' : '';
      html += `<button class="hitl-action ${activeCls}" data-field="${d.field}" data-action="${action}">${label}</button>`;
    }
    html += '</div>';

    // Inline edit panel
    const defaultEditText = d.edited_text || c.proposed_text || rr.inputs.special_clause || '';
    html += `
      <div class="edit-clause-panel" id="edit-panel-${d.field}" style="display:${activeAction === 'edit' ? 'block' : 'none'}">
        <label for="edit-textarea-${d.field}">Edit clause text (max 2,000 characters):</label>
        <textarea id="edit-textarea-${d.field}" class="edit-clause-textarea" rows="4">${escHtml(defaultEditText)}</textarea>
        <div class="edit-clause-buttons">
          <button class="btn-save-edit" data-field="${d.field}">Apply edited text</button>
          <button class="btn-cancel-edit" data-field="${d.field}">Cancel</button>
        </div>
      </div>
    `;
  }

  // Info notes (excluding safeguard warning already shown in banner)
  if (d.info_notes?.length) {
    for (const note of d.info_notes) {
      if (!note.includes('Warning: edited text lacks')) {
        html += `<div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.35rem">ℹ ${escHtml(note)}</div>`;
      }
    }
  }

  html += '</div>';
  return html;
}

function wireReviewActions(rr) {
  $$('.hitl-action').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const field = e.target.dataset.field;
      const action = e.target.dataset.action;
      if (action === 'edit') {
        const panel = $(`#edit-panel-${field}`);
        if (panel) {
          const isHidden = panel.style.display === 'none' || !panel.style.display;
          panel.style.display = isHidden ? 'block' : 'none';
          const textarea = $(`#edit-textarea-${field}`);
          if (isHidden && textarea) {
            textarea.focus();
          }
        }
      } else {
        await sendRenderAction(field, action);
      }
    });
  });

  $$('.btn-save-edit').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const field = e.target.dataset.field;
      const textarea = $(`#edit-textarea-${field}`);
      const text = textarea ? textarea.value.trim() : '';
      if (!text) {
        showError('Please enter clause text or choose "Remove clause"');
        return;
      }
      if (text.length > 2000) {
        showError('Edited text exceeds 2,000 characters limit');
        return;
      }
      await sendRenderAction(field, 'edit', text);
    });
  });

  $$('.btn-cancel-edit').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const field = e.target.dataset.field;
      const panel = $(`#edit-panel-${field}`);
      if (panel) panel.style.display = 'none';
    });
  });
}

async function sendRenderAction(field, action, edited_text = null) {
  if (!currentEnvelope) return;
  clearError();
  const reviewerAction = { field, action };
  if (edited_text !== null) {
    reviewerAction.edited_text = edited_text;
  }
  try {
    const res = await fetch('/api/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_result: currentEnvelope.run_result,
        signature: currentEnvelope.signature,
        reviewer_actions: [reviewerAction],
      }),
    });
    if (res.status === 400) {
      showError('Signature invalid — please regenerate the draft');
      return;
    }
    if (res.status === 422) {
      const err = await res.json().catch(() => ({}));
      showError('Validation error: ' + (err.detail || 'field too long (max 2,000 characters)'));
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.detail || `Server error (${res.status}) — please retry`);
      return;
    }
    currentEnvelope = await res.json();
    renderAll();
  } catch (e) {
    showError('Network error — check your connection and retry');
  }
}

// --- Draft Tab ---------------------------------------------------------------
function renderDraftTab() {
  const container = $('#draft-content');
  if (!currentEnvelope?.preview_html) {
    container.innerHTML = '<div class="empty-state"><div class="icon">📄</div><p>Generate a draft to preview</p></div>';
    return;
  }
  container.innerHTML = `<div class="draft-preview">${currentEnvelope.preview_html}</div>`;
}

// --- Agent Trace Tab ---------------------------------------------------------
function renderTraceTab(rr) {
  const container = $('#trace-content');
  const trace = rr.trace || [];

  let html = '<button class="btn-trace-download" id="btn-trace-json">Download trace JSON</button>';
  html += `<table class="trace-table">
    <thead><tr><th>Step</th><th>Kind</th><th>Status</th><th>Time</th><th>Model</th><th>Tokens</th><th>Details</th></tr></thead>
    <tbody>`;

  for (const step of trace) {
    const kindCls = step.kind || 'tool';
    let toolCallsHtml = '';
    if (step.tool_calls?.length) {
      toolCallsHtml = `<details class="trace-tools-details"><summary>${step.tool_calls.length} tool call${step.tool_calls.length > 1 ? 's' : ''}: ${step.tool_calls.map(tc => escHtml(tc.name)).join(', ')}</summary><div class="trace-tools-expanded">`;
      for (const tc of step.tool_calls) {
        toolCallsHtml += `<div class="tc-item">
          <div class="tc-name"><strong>${escHtml(tc.name)}</strong>${tc.is_error ? ' <span class="tc-err">(error)</span>' : ''}</div>
          ${tc.arguments_summary ? `<div class="tc-args"><code>args: ${escHtml(tc.arguments_summary)}</code></div>` : ''}
          ${tc.output_summary ? `<div class="tc-out"><code>out: ${escHtml(tc.output_summary)}</code></div>` : ''}
        </div>`;
      }
      toolCallsHtml += `</div></details>`;
    }

    html += `<tr>
      <td>${escHtml(step.name)}</td>
      <td><span class="kind-badge ${kindCls}">${step.kind}</span></td>
      <td>${step.status === 'ok' ? '<span style="color:var(--accent-green)">✓</span>' : '<span style="color:var(--accent-red)">✗</span>'}</td>
      <td>${step.duration_ms ? step.duration_ms.toFixed(1) + 'ms' : '—'}</td>
      <td style="font-size:0.72rem">${step.model || '—'}</td>
      <td>${step.total_tokens || '—'}${step.remaining_rate_limit_tokens ? `<br><span style="font-size:0.65rem;color:var(--text-muted)">rem: ${step.remaining_rate_limit_tokens}</span>` : ''}</td>
      <td>
        <div class="trace-detail">${escHtml(step.output_summary || '')}</div>
        ${toolCallsHtml}
        ${step.error ? `<div style="color:var(--accent-red);font-size:0.72rem;margin-top:0.25rem">${escHtml(step.error)}</div>` : ''}
      </td>
    </tr>`;
  }
  html += '</tbody></table>';

  // Tokens per model summary
  const tokensByModel = {};
  for (const s of trace) {
    if (s.model && s.total_tokens) {
      tokensByModel[s.model] = (tokensByModel[s.model] || 0) + s.total_tokens;
    }
  }
  if (Object.keys(tokensByModel).length) {
    html += '<div style="margin-top:1rem;font-size:0.78rem;color:var(--text-secondary)"><strong>Tokens per model:</strong>';
    for (const [model, total] of Object.entries(tokensByModel)) {
      html += ` ${model}: ${total.toLocaleString()} ·`;
    }
    html = html.slice(0, -1) + '</div>';
  }

  container.innerHTML = html;
  $('#btn-trace-json')?.addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(trace, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trace-${rr.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

// --- Field Table Tab ---------------------------------------------------------
function renderFieldTable(rr) {
  const container = $('#field-table-content');
  let html = `<table class="field-table">
    <thead><tr><th>Field</th><th>Raw Value</th><th>Value for Document</th><th>Status</th><th>Gate</th><th>Reason</th></tr></thead>
    <tbody>`;
  for (const d of rr.decisions) {
    html += `<tr>
      <td style="font-weight:500">${displayFieldName(d.field)}</td>
      <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escAttr(d.raw_value || '')}">${escHtml((d.raw_value || '').substring(0, 60))}</td>
      <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escAttr(d.value_for_document || '')}">${escHtml((d.value_for_document || '—').substring(0, 60))}</td>
      <td><span class="status-badge ${statusClass(d.status)}">${d.status.replace(/_/g, ' ')}</span></td>
      <td><span class="gate-badge">${d.gate}</span></td>
      <td style="font-size:0.75rem;color:var(--text-secondary)">${escHtml(d.reason)}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

// --- Rules Tab ---------------------------------------------------------------
async function loadRulesTab() {
  const container = $('#rules-content');
  try {
    const res = await fetch('/api/rulebook');
    const data = await res.json();
    container.innerHTML = `<pre class="rules-content">${escHtml(data.text)}</pre>`;
  } catch (e) {
    container.innerHTML = '<div class="empty-state"><p>Failed to load rulebook</p></div>';
  }
}

// --- Helpers -----------------------------------------------------------------
function displayFieldName(f) {
  return f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function statusClass(status) {
  return {
    'NEEDS_REVIEW': 'needs-review',
    'BLOCKED_MISSING': 'blocked',
    'AUTO_FILLED': 'auto-filled',
    'AUTO_FILLED_WITH_ASSUMPTION': 'assumption',
    'NOT_APPLICABLE': 'not-applicable',
  }[status] || '';
}

function escHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function escAttr(s) {
  return (s || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function showError(msg) {
  clearError();
  const toast = document.createElement('div');
  toast.className = 'error-toast';
  toast.id = 'error-toast';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(clearError, 6000);
}
function clearError() {
  const existing = $('#error-toast');
  if (existing) existing.remove();
}
