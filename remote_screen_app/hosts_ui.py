"""The hosts editor served into the Settings panel's ``iframe`` widget.

Why an iframe and not declarative widgets: aw-workspace-ui's declarative
renderer supports exactly ``markdown``, ``list``, ``button``, ``iframe``,
``app_iframe``, ``collapsible``, ``form`` and ``auth_status``. Its ``list``
takes STATIC items from the spec — there is no data-bound list/table widget,
and no ``table`` widget at all. So a spec made of widgets cannot render a live,
editable list of rows. ``iframe { src: "/api/*" }`` is the vocabulary's own
escape hatch for exactly this, and ``apiUrl()`` rewrites the src to the
workspace API origin — which is also the origin this page's own fetches go to,
so the apex ``aw_id_jwt`` cookie authorises them.

**Layout constraint:** the narrow case still rules the markup. In the Settings
sidebar the host renders this in a short `.appwin-iframe` box, where a
multi-column table wraps every cell into a vertical ribbon and pushes the row
actions off the right edge — one card per host, stacked, is what fits. As of
aw-workspace-ui's 2026-08-21 gutter/height pass the SAME page also fills a
full, resizable window (~1200px), so the stylesheet caps its measure and goes
two-up above 620px rather than stretching one column across the lot.

Deliberately dependency-free (no build step, no framework): this is a settings
pane, and a second npm bundle to maintain for one CRUD list is not worth it.
Colours come from the host's own `--color-*` variables with rgba fallbacks, so
it reads correctly in both its light and dark themes.
"""
from __future__ import annotations

HOSTS_UI_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Remote Screen hosts</title>
<style>
  :root {
    color-scheme: dark light;
    --accent: var(--color-accent, #f5a623);
    --line: var(--color-border, rgba(128,128,128,.28));
    --muted: var(--color-text-muted, #64748b);
    --panel: rgba(128,128,128,.06);
  }
  * { box-sizing: border-box; }
  /* The gutter has to live HERE. The host renders this page in a
     cross-origin iframe, so no stylesheet of its can reach inside; padding on
     the <iframe> itself only shifts the origin and clips the right-hand side
     (tried, reverted). Without this the form sits flush against the frame. */
  body { margin: 0; padding: 12px; font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
         background: transparent; color: inherit; }

  /* This page is sized by whatever box embeds it, and that box is no longer
     always the narrow Settings sidebar — since the host lets a window's iframe
     take the full window height/width, a maximised Remote Screen — Hosts is
     ~1200px across. Left alone, every input stretched the whole way: a 1200px
     field for "5900" is a worse target than a 400px one, not a better one.
     Cap the measure, left-aligned so it stays flush with the window heading
     rendered ABOVE this frame by the host's markdown widget — centring it
     instead left the two visibly out of step. The sidebar is narrower than the
     cap, so nothing changes there. */
  #msg, #list, #form-title, #form { max-width: 760px; }

  /* Above the cap there is room for two fields per line. Grid (not the
     existing .row2 flex) because the form's fields are shown and hidden per
     protocol — ANDROID_ONLY toggles four of them — and grid reflows around a
     display:none item on its own instead of leaving a hole. Rows that are
     already a pair, plus the hint and the buttons, span the full width. */
  @media (min-width: 620px) {
    #form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0 14px; align-items: start; }
    #form > .row2, #form > .hint, #form > .form-actions { grid-column: 1 / -1; }
  }

  .card { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
          margin-bottom: 8px; background: var(--panel); }
  .card-top { display: flex; align-items: center; gap: 8px; }
  .name { font-weight: 600; font-size: 13px; flex: 1; min-width: 0;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .addr { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px;
          color: var(--muted); margin-top: 4px;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tag { font-size: 10px; font-weight: 600; letter-spacing: .04em; padding: 2px 6px;
         border-radius: 4px; background: rgba(128,128,128,.16); color: var(--muted);
         flex: none; }
  .tag.warn { background: rgba(248,113,113,.15); color: #f87171; }
  .note { font-size: 11px; color: var(--muted); margin-top: 5px; }

  .actions { display: flex; gap: 5px; flex: none; }
  button { font: inherit; font-size: 11px; font-weight: 500; padding: 4px 10px;
           border-radius: 6px; border: 1px solid var(--line);
           background: transparent; color: inherit; cursor: pointer;
           transition: background .12s, border-color .12s, color .12s; }
  button:hover { background: rgba(128,128,128,.16); border-color: rgba(128,128,128,.45); }
  button.primary { background: var(--accent); border-color: var(--accent);
                   color: #1a1205; font-weight: 600; }
  button.primary:hover { filter: brightness(1.08); }
  button.ghost { border-color: transparent; color: var(--muted); padding: 4px 7px; }
  button.ghost:hover { color: inherit; }
  button.danger:hover { background: rgba(248,113,113,.14);
                        border-color: rgba(248,113,113,.45); color: #f87171; }
  /* The armed half of the two-click delete — filled, so "one more click and
     it's gone" doesn't depend on reading the label. The :hover variant repeats
     the whole declaration because `button.danger:hover` above is more specific
     than a bare `.danger.armed`, and the armed button is ALWAYS hovered: it
     renders exactly under the cursor that just clicked Delete. */
  button.danger.armed, button.danger.armed:hover {
    background: #f87171; border-color: #f87171; color: #2a0808; font-weight: 600; }

  h4 { margin: 18px 0 8px; font-size: 11px; text-transform: uppercase;
       letter-spacing: .05em; color: var(--muted); font-weight: 600; }
  .field { margin-bottom: 10px; }
  .field > label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 4px; }
  input, select { font: inherit; font-size: 12px; padding: 6px 8px; border-radius: 6px;
                  border: 1px solid var(--line); background: rgba(128,128,128,.08);
                  color: inherit; width: 100%; }
  input:focus, select:focus { outline: none; border-color: var(--accent); }
  .hint { font-size: 11px; color: var(--muted); margin-top: 4px; line-height: 1.45; }
  .row2 { display: flex; gap: 8px; }
  .row2 > .field { flex: 1; margin-bottom: 0; }
  .form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }

  .msg { padding: 7px 10px; border-radius: 7px; font-size: 12px; margin-bottom: 10px;
         line-height: 1.45; }
  .msg.err { background: rgba(248,113,113,.13); color: #fca5a5; }
  .msg.ok  { background: rgba(74,222,128,.13); color: #86efac; }
  .empty { color: var(--muted); font-size: 12px; padding: 14px 0; text-align: center; }
</style>
</head>
<body>
<div id="msg"></div>
<div id="list"></div>

<h4 id="form-title">Add a host</h4>
<form id="form" autocomplete="off">
  <input type="hidden" id="id">

  <div class="field">
    <label for="name">Name</label>
    <input id="name" placeholder="office-mac" required>
  </div>

  <div class="field">
    <label for="protocol">Protocol</label>
    <select id="protocol">
      <option value="vnc">VNC</option>
      <option value="android">Android (screen mirror)</option>
      <option value="rdp">RDP (stored only &mdash; no browser client yet)</option>
    </select>
  </div>

  <div class="field">
    <label for="agent_kind" id="kind-label">Exec channel</label>
    <select id="agent_kind">
      <option value="aw_remote_host">Linked remote host (this workspace)</option>
      <option value="remote_agent">Legacy remote-agent backend</option>
    </select>
    <div class="hint" id="kind-hint"></div>
  </div>

  <div class="field">
    <label for="host" id="host-label">Host</label>
    <input id="host" placeholder="127.0.0.1" required>
    <div class="hint" id="host-hint"></div>
  </div>

  <div class="field" id="port-field">
    <label for="port">Port</label>
    <input id="port" type="number" min="1" max="65535" placeholder="5900">
  </div>

  <div class="field" id="serial-field">
    <label for="device_serial">Device serial</label>
    <input id="device_serial" placeholder="emulator-5554 (blank = only attached device)">
  </div>

  <div class="field" id="adb-field">
    <label for="adb_bin">adb path</label>
    <input id="adb_bin" placeholder="~/Android/platform-tools/adb">
  </div>

  <div class="field" id="agent-field">
    <label for="agent_base_url">Agent URL</label>
    <input id="agent_base_url" placeholder="http://127.0.0.1:10005">
  </div>

  <div class="row2" id="creds-row">
    <div class="field">
      <label for="username">Username</label>
      <input id="username" placeholder="(optional)">
    </div>
    <div class="field">
      <label for="password">Password</label>
      <input id="password" type="password" placeholder="(optional)">
    </div>
  </div>
  <div class="hint" id="pw-hint"></div>

  <div class="form-actions">
    <button type="button" id="cancel" hidden>Cancel</button>
    <button type="submit" class="primary" id="save">Add host</button>
  </div>
</form>

<script>
const BASE = '/api/apps/remote-screen';
const $ = (id) => document.getElementById(id);
const ANDROID_ONLY = ['device_serial', 'adb_bin', 'agent_base_url', 'agent_kind'];
let hosts = [];
// Id of the host whose Delete is armed. This panel CANNOT use confirm(): the
// host renders it in a sandbox without allow-modals (aw-workspace-ui
// AppWindow.jsx — "allow-scripts allow-forms allow-same-origin"), so the
// browser ignores the call and returns false. `if (!confirm(...)) return;`
// was therefore an unconditional return and Delete silently did nothing.
let armed = null;

async function call(method, path, body) {
  const init = { method, credentials: 'include' };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, init);
  let payload = {};
  try { payload = await res.json(); } catch (_e) {}
  if (!res.ok) throw new Error(payload.detail || ('HTTP ' + res.status));
  return payload;
}

function say(text, kind) {
  $('msg').innerHTML = text ? '<div class="msg ' + kind + '">' + text + '</div>' : '';
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function addrOf(h) {
  if (h.protocol === 'android') {
    return h.host + (h.device_serial ? ' \\u00b7 ' + h.device_serial : ' \\u00b7 default device');
  }
  return h.host + ':' + h.port;
}

function render() {
  if (!hosts.length) {
    $('list').innerHTML = '<div class="empty">No hosts yet.</div>';
    return;
  }
  $('list').innerHTML = hosts.map((h) =>
    '<div class="card">'
    + '<div class="card-top">'
    +   '<span class="name" title="' + esc(h.name) + '">' + esc(h.name) + '</span>'
    +   '<span class="tag' + (h.supported ? '' : ' warn') + '">'
    +     esc(h.protocol.toUpperCase()) + '</span>'
    +   '<span class="actions">'
    +     '<button class="ghost" data-edit="' + esc(h.id) + '">Edit</button>'
    +     (armed === h.id
              ? '<button class="ghost danger armed" data-confirm-del="' + esc(h.id) + '">Confirm</button>'
                + '<button class="ghost" data-cancel-del="1">Cancel</button>'
              : '<button class="ghost danger" data-del="' + esc(h.id) + '">Delete</button>')
    +   '</span>'
    + '</div>'
    + '<div class="addr" title="' + esc(addrOf(h)) + '">' + esc(addrOf(h)) + '</div>'
    + (h.supported
        ? (h.has_password ? '<div class="note">Password saved</div>' : '')
        : '<div class="note">No browser client for this protocol yet &mdash; '
          + 'stored, not connectable.</div>')
    + '</div>').join('');
}

async function refresh() {
  hosts = (await call('GET', '/hosts')).hosts || [];
  render();
}

// A form that shows "Port" for an Android device and "adb path" for a VNC box
// teaches the wrong model of what each protocol needs, so swap the halves
// rather than showing everything greyed out.
function applyProtocol() {
  const android = $('protocol').value === 'android';
  for (const id of ANDROID_ONLY) {
    const f = $(id).closest('.field');
    if (f) f.hidden = !android;
  }
  $('port-field').hidden = android;
  $('creds-row').hidden = android;
  $('pw-hint').hidden = android;
  $('port').required = !android;
  $('host-label').textContent = android ? 'Agent profile' : 'Host';
  applyAgentKind();
  if (!android) {
    $('host-hint').innerHTML = 'Resolved from inside this workspace, not from your laptop '
      + '&mdash; a machine on your own LAN needs a reachable address or a tunnel.';
  }
}
$('protocol').addEventListener('change', applyProtocol);

// The two channels want DIFFERENT things in `host`, and getting that wrong is
// the likeliest way to end up with a host that just times out: one wants a
// linked-host id, the other a remote-agent profile name.
function applyAgentKind() {
  const android = $('protocol').value === 'android';
  if (!android) return;
  const legacy = $('agent_kind').value === 'remote_agent';
  $('agent_base_url').closest('.field').hidden = !legacy;
  $('kind-hint').innerHTML = legacy
    ? 'Monolith path &mdash; reachable only from inside that deployment.'
    : 'Goes through aw-backend over the /link tunnel the host already holds open.';
  $('host-hint').innerHTML = legacy
    ? 'The remote-agent <b>profile name</b> (e.g. <code>macbook-fred</code>).'
    : 'The <b>linked host id</b> (see Remote Hosts) &mdash; not a hostname.';
}
$('agent_kind').addEventListener('change', applyAgentKind);

function resetForm() {
  $('id').value = '';
  $('form').reset();
  $('protocol').value = 'vnc';
  $('agent_kind').value = 'aw_remote_host';
  $('form-title').textContent = 'Add a host';
  $('save').textContent = 'Add host';
  $('cancel').hidden = true;
  $('pw-hint').textContent = '';
  applyProtocol();
}

function loadForEdit(id) {
  const h = hosts.find((x) => x.id === id);
  if (!h) return;
  $('id').value = h.id;
  $('name').value = h.name;
  $('protocol').value = h.protocol;
  $('host').value = h.host;
  $('port').value = h.port || '';
  $('username').value = h.username || '';
  $('password').value = '';
  for (const k of ANDROID_ONLY) $(k).value = h[k] || '';
  if (!h.agent_kind) $('agent_kind').value = 'aw_remote_host';
  $('form-title').textContent = 'Edit ' + h.name;
  $('save').textContent = 'Save changes';
  $('cancel').hidden = false;
  // The single most confusing thing about editing a saved credential is not
  // knowing whether leaving the field blank wipes it. Say so explicitly.
  $('pw-hint').textContent = h.has_password
    ? 'A password is saved. Leave blank to keep it; type a new one to replace it.'
    : 'No password saved for this host.';
  applyProtocol();
  $('name').focus();
  $('form-title').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

$('list').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  const del = b.getAttribute('data-del');
  const edit = b.getAttribute('data-edit');
  const confirmDel = b.getAttribute('data-confirm-del');
  if (edit) return loadForEdit(edit);
  if (b.hasAttribute('data-cancel-del')) { armed = null; return render(); }
  if (del) {
    const h = hosts.find((x) => x.id === del);
    armed = del;
    render();
    say('Deleting "' + esc(h ? h.name : del) + '" also deletes its saved password. Click Confirm.', 'err');
    return;
  }
  if (!confirmDel) return;
  armed = null;
  try {
    await call('DELETE', '/hosts/' + encodeURIComponent(confirmDel));
    if ($('id').value === confirmDel) resetForm();
    await refresh();
    say('Deleted.', 'ok');
  } catch (err) { say(esc(err.message), 'err'); }
});

$('cancel').addEventListener('click', () => { resetForm(); say('', 'ok'); });

$('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = $('id').value;
  const body = {
    name: $('name').value.trim(),
    protocol: $('protocol').value,
    host: $('host').value.trim(),
    port: Number($('port').value) || 0,
    username: $('username').value.trim(),
  };
  if ($('password').value) body.password = $('password').value;
  if (body.protocol === 'android') for (const k of ANDROID_ONLY) body[k] = $(k).value.trim();
  try {
    if (id) await call('PUT', '/hosts/' + encodeURIComponent(id), body);
    else await call('POST', '/hosts', body);
    resetForm();
    await refresh();
    say(id ? 'Saved.' : 'Host added.', 'ok');
  } catch (err) { say(esc(err.message), 'err'); }
});

applyProtocol();
refresh().catch((err) => say('Could not load hosts: ' + esc(err.message), 'err'));
</script>
</body>
</html>
"""
