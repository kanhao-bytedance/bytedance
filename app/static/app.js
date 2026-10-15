const $ = (id) => document.getElementById(id);
const pageSize = 20;
let offset = 0;
let total = 0;
let generation = 0;
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safeURL(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}
async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail; else if (Array.isArray(body.detail)) message = body.detail.map(x => `${x.loc.at(-1)}: ${x.msg}`).join('; '); } catch {}
    throw new Error(message);
  }
  return response.json();
}
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
  $('notice').hidden = !message;
}
function params() {
  const result = new URLSearchParams();
  for (const [key, value] of new FormData($('filter-form'))) if (value.trim()) result.set(key, value.trim());
  return result;
}
function showAdd() {
  $('add-form').reset();
  $('add-form').elements.external_id.value = `manual-${crypto.randomUUID()}`;
  $('add-form').querySelector('.form-status').textContent = '';
  $('add-dialog').showModal();
}
$('add-button').onclick = showAdd;
$('empty-add').onclick = showAdd;
$('collect-button').onclick = () => $('collect-dialog').showModal();
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => button.closest('dialog').close());
$('filter-form').onsubmit = event => {event.preventDefault(); offset = 0; load();};
$('previous').onclick = () => {offset = Math.max(0, offset - pageSize); load();};
$('next').onclick = () => {offset += pageSize; load();};
async function load() {
  const current = ++generation;
  const query = params();
  $('previous').disabled = $('next').disabled = true;
  try {
    const [summary, rows, themes] = await Promise.all([
      api(`/summary?${query}`), api(`/feedback?${query}&limit=${pageSize}&offset=${offset}`), api(`/trends?${query}`)
    ]);
    if (current !== generation) return;
    total = summary.total;
    $('total').textContent = total.toLocaleString();
    $('high').textContent = summary.high_severity.toLocaleString();
    $('requests').textContent = summary.feature_requests.toLocaleString();
    $('unclassified').textContent = summary.unclassified.toLocaleString();
    $('inbox-count').textContent = total.toLocaleString();
    $('themes').innerHTML = themes.length ? themes.slice(0, 4).map(t => `<div class="theme-row"><div class="theme-info"><span>${escapeHTML(t.product_area)} <small>${escapeHTML(t.feedback_type)}</small></span><span>${t.count}</span></div><div class="track"><div style="width:${Math.round(t.count / Math.max(total, 1) * 100)}%"></div></div></div>`).join('') : '<p class="empty-small">Your top themes will appear as feedback comes in.</p>';
    $('platforms').innerHTML = summary.platforms.length ? summary.platforms.sort((a,b) => b.count-a.count).map(p => `<div class="platform-row"><span><span class="platform-icon">${escapeHTML(p.name.charAt(0))}</span>${escapeHTML(p.name)}</span><strong>${p.count}</strong></div>`).join('') : '<p class="empty-small">No platform data yet. Add feedback to start listening.</p>';
    $('feedback-rows').innerHTML = rows.map(row => `<tr><td><button data-id="${row.id}">${escapeHTML(row.summary || row.title || row.text.slice(0, 160))}</button><small>${escapeHTML(row.product_area || 'Other')} · ${escapeHTML(new Date(row.created_at.endsWith('Z') ? row.created_at : row.created_at + 'Z').toLocaleDateString(undefined, {month:'short', day:'numeric'}))}${row.classification_status === 'unclassified' ? ' · Unclassified' : ''}</small></td><td>${escapeHTML(row.platform || 'Other')}</td><td><span class="badge ${row.classification_status === 'unclassified' ? 'unclassified' : ''}">${escapeHTML(row.classification_status === 'unclassified' ? 'Unclassified' : row.feedback_type)}</span></td><td>${row.classification_status === 'unclassified' ? '—' : `<span class="badge ${escapeHTML(row.severity.toLowerCase())}">${escapeHTML(row.severity)}</span>`}</td><td>${escapeHTML(row.source)}</td><td><button data-id="${row.id}" aria-label="View feedback">↗</button></td></tr>`).join('');
    $('feedback-rows').querySelectorAll('[data-id]').forEach(button => button.onclick = () => showDetail(button.dataset.id));
    $('empty-state').hidden = rows.length > 0;
    const filtered = query.size > 0;
    $('empty-title').textContent = filtered ? 'No conversations match yet.' : 'Your listening starts here.';
    $('empty-copy').textContent = filtered ? 'Try a broader search or change the filters.' : 'Add your first piece of feedback or connect Reddit to bring customer conversations into focus.';
    $('empty-add').hidden = filtered;
    $('pagination-label').textContent = total ? `${Math.min(offset + 1, total)}–${Math.min(offset + rows.length, total)} of ${total} conversations` : '0 conversations';
    $('previous').disabled = offset === 0;
    $('next').disabled = offset + pageSize >= total;
  } catch (error) {
    if (current !== generation) return;
    notice(error.message, true);
    $('pagination-label').textContent = 'Could not load feedback. Search to retry.';
  }
}
async function showDetail(id) {
  $('detail-content').textContent = 'Loading conversation…';
  $('detail-dialog').showModal();
  try {
    const row = await api(`/feedback/${id}`);
    const fields = {Platform: row.platform, 'Product area': row.product_area, 'Feedback type': row.feedback_type, 'Classification': row.classification_status, 'User type': row.user_type, 'Sentiment': row.sentiment, 'Severity': row.classification_status === 'unclassified' ? 'Not evaluated' : row.severity, 'Relevance': row.classification_status === 'unclassified' ? 'Not evaluated' : `${Math.round(row.relevance*100)}%`, 'Source':row.source, 'Source reference':row.external_id, 'Author':row.author || 'Not provided', 'Requested change':row.requested_change || '—'};
    const url = safeURL(row.url);
    $('detail-content').innerHTML = `<h2 class="detail-title">${escapeHTML(row.title || row.summary)}</h2>${row.classification_status === 'unclassified' ? '<p class="muted">Saved without AI classification. Categories have not been evaluated.</p>' : `<p>${escapeHTML(row.summary)}</p>`}<div class="evidence">${escapeHTML(row.text)}</div><dl class="detail-grid">${Object.entries(fields).map(([key,value]) => `<div><dt>${escapeHTML(key)}</dt><dd>${escapeHTML(value)}</dd></div>`).join('')}</dl>${url ? `<a class="source-link" target="_blank" rel="noopener noreferrer" href="${escapeHTML(url)}">View original source ↗</a>` : '<p class="muted">No source link provided.</p>'}`;
  } catch (error) { $('detail-content').textContent = error.message; }
}
async function submitForm(event, action) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector('[type="submit"]');
  const status = form.querySelector('.form-status');
  button.disabled = true;
  status.textContent = 'Working…';
  try {
    const message = await action(new FormData(form));
    form.closest('dialog').close();
    status.textContent = '';
    offset = 0;
    notice(message);
    await load();
  } catch (error) { status.textContent = error.message; }
  finally { button.disabled = false; }
}
$('add-form').onsubmit = event => submitForm(event, async data => {
  const body = Object.fromEntries(data);
  body.content_type = 'comment';
  if (!body.url) body.url = null;
  const result = await api('/ingest', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return result.created ? (result.classification_status === 'unclassified' ? 'Feedback saved. AI classification is not configured; this conversation is marked unclassified.' : 'Feedback saved and classified.') : 'This source reference is already in your inbox. No duplicate was created.';
});
$('collect-form').onsubmit = event => submitForm(event, async data => {
  const query = new URLSearchParams();
  for (const [key,value] of data) if (value.trim()) query.set(key,value.trim());
  const result = await api(`/collect/reddit?${query}`, {method:'POST'});
  return `Fetched ${result.fetched} Reddit posts; added ${result.created} new conversations.`;
});
api('/health').then(health => {
  $('integration-status').textContent = `AI classification ${health.ai_enabled ? 'configured' : 'not configured'} · Reddit ${health.reddit_enabled ? 'configured' : 'not configured'}`;
}).catch(() => { $('integration-status').textContent = 'Integration status unavailable'; });
load();
