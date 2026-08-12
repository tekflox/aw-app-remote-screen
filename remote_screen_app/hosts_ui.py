"""The hosts editor served into the Settings panel's ``iframe`` widget.

Why an iframe and not declarative widgets: aw-workspace-ui's declarative
renderer (``src/components/AppWindow.jsx``) supports exactly ``markdown``,
``list``, ``button``, ``iframe``, ``app_iframe``, ``collapsible``, ``form``
and ``auth_status``. Its ``list`` takes STATIC items from the spec — there is
no data-bound list/table widget, and no ``table`` widget at all (despite what
some apps' manifests assume). So a spec made of widgets cannot render a live,
editable list of rows. ``iframe { src: "/api/*" }`` is the vocabulary's own
escape hatch for exactly this, and ``apiUrl()`` rewrites the src to the
workspace API origin — which is also the origin this page's own fetches go
to, so the apex ``aw_id_jwt`` cookie authorises them.

Deliberately dependency-free (no build step, no framework): this is a settings
pane, and a second npm bundle to maintain for one CRUD table is not worth it.
"""
from __future__ import annotations

HOSTS_UI_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Remote Desktop hosts</title>
<style>
  :root { color-scheme: dark light; }
  body { margin: 0; padding: 0; font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
         background: transparent; color: inherit; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid rgba(128,128,128,.25);
           font-size: 12px; }
  th { font-weight: 600; opacity: .7; font-size: 11px; text-transform: uppercase;
       letter-spacing: .04em; }
  td.addr { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .actions { text-align: right; white-space: nowrap; }
  button { font: inherit; font-size: 11px; padding: 3px 9px; border-radius: 5px;
           border: 1px solid rgba(128,128,128,.35); background: rgba(128,128,128,.12);
           color: inherit; cursor: pointer; }
  button:hover { background: rgba(128,128,128,.22); }
  button.danger { border-color: rgba(220,80,80,.4); color: #e88; }
  button.primary { border-color: rgba(90,150,240,.5); color: #8ab4f8; }
  form { display: grid; grid-template-columns: 130px 1fr; gap: 8px 10px; align-items: center;
         margin-top: 6px; }
  form label { font-size: 12px; opacity: .8; }
  input, select { font: inherit; font-size: 12px; padding: 5px 7px; border-radius: 5px;
                  border: 1px solid rgba(128,128,128,.35); background: rgba(128,128,128,.1);
                  color: inherit; width: 100%; box-sizing: border-box; }
  .row-span { grid-column: 1 / -1; display: flex; gap: 8px; justify-content: flex-end; }
  .hint { grid-column: 1 / -1; font-size: 11px; opacity: .6; margin: -2px 0 4px; }
  .msg { padding: 6px 8px; border-radius: 5px; font-size: 12px; margin-bottom: 10px; }
  .msg.err { background: rgba(220,80,80,.15); color: #f2a0a0; }
  .msg.ok  { background: rgba(80,190,120,.15); color: #9edeb0; }
  .empty { opacity: .6; font-size: 12px; padding: 10px 0; }
  h4 { margin: 16px 0 4px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
       opacity: .7; }
</style>
</head>
<body>
<div id="msg"></div>
<div id="list"></div>
<h4 id="form-title">Add a host</h4>
<form id="form" autocomplete="off">
  <input type="hidden" id="id">
  <label for="name">Name</label>
  <input id="name" placeholder="office-mac" required>
  <label for="protocol">Protocol</label>
  <select id="protocol">
    <option value="vnc">VNC</option>
    <option value="android">Android (screen mirror over the agent exec channel)</option>
    <option value="rdp">RDP (stored only &mdash; no browser client yet)</option>
  </select>
  <label for="host" id="host-label">Host</label>
  <input id="host" placeholder="127.0.0.1" required>
  <div class="hint" id="host-hint">Resolved from inside this workspace, not from your laptop
    &mdash; a machine on your own LAN needs a reachable address or a tunnel.</div>
  <label for="port" id="port-label">Port</label>
  <input id="port" type="number" min="1" max="65535" placeholder="5900">
  <label for="device_serial" id="serial-label">Device serial</label>
  <input id="device_serial" placeholder="emulator-5554 (blank = only attached device)">
  <label for="adb_bin" id="adb-label">adb path</label>
  <input id="adb_bin" placeholder="~/Android/platform-tools/adb">
  <label for="agent_base_url" id="agent-label">Agent URL</label>
  <input id="agent_base_url" placeholder="http://127.0.0.1:10005">
  <label for="username">Username</label>
  <input id="username" placeholder="(optional)">
  <label for="password">Password</label>
  <input id="password" type="password" placeholder="(optional)">
  <div class="hint" id="pw-hint"></div>
  <div class="row-span">
    <button type="button" id="cancel" hidden>Cancel</button>
    <button type="submit" class="primary" id="save">Add host</button>
  </div>
</form>

<script>
const BASE = '/api/apps/remote-screen';
const $ = (id) => document.getElementById(id);

async function call(method, path, body) {
  const init = { method, credentials: 'include' };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, init);
  let payload = {};
  try { payload = await res.json(); } catch (_e) { /* empty body */ }
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

let hosts = [];

function render() {
  if (!hosts.length) {
    $('list').innerHTML = '<div class="empty">No hosts yet.</div>';
    return;
  }
  $('list').innerHTML =
    '<table><thead><tr><th>Name</th><th>Address</th><th>Protocol</th><th>Password</th>' +
    '<th></th></tr></thead><tbody>' +
    hosts.map((h) =>
      '<tr><td>' + esc(h.name) + '</td>' +
      '<td class="addr">' + esc(h.host) + (h.port ? ':' + h.port : '') +
        (h.device_serial ? ' / ' + esc(h.device_serial) : '') + '</td>' +
      '<td>' + esc(h.protocol.toUpperCase()) + (h.supported ? '' : ' \\u26a0') + '</td>' +
      '<td>' + (h.has_password ? 'saved' : '\\u2014') + '</td>' +
      '<td class="actions">' +
      '<button data-edit="' + esc(h.id) + '">Edit</button> ' +
      '<button class="danger" data-del="' + esc(h.id) + '">Delete</button></td></tr>'
    ).join('') + '</tbody></table>';
}

async function refresh() {
  hosts = (await call('GET', '/hosts')).hosts || [];
  render();
}

const ANDROID_ONLY = ['device_serial', 'adb_bin', 'agent_base_url'];
const TCP_ONLY = ['port'];

function rowOf(id) { return [$(id), document.querySelector('label[for="' + id + '"]')]; }

// A form that shows "Port" for an Android device and "adb path" for a VNC box
// teaches the wrong model of what each protocol needs, so swap the halves
// rather than showing everything greyed out.
function applyProtocol() {
  const android = $('protocol').value === 'android';
  for (const id of ANDROID_ONLY) rowOf(id).forEach((el) => { if (el) el.hidden = !android; });
  for (const id of TCP_ONLY) rowOf(id).forEach((el) => { if (el) el.hidden = android; });
  $('host-label').textContent = android ? 'Agent profile' : 'Host';
  $('host-hint').innerHTML = android
    ? 'The remote-agent profile id of the machine the device is attached to (e.g. <code>macbook-fred</code>) &mdash; not a hostname; there is no TCP endpoint.'
    : 'Resolved from inside this workspace, not from your laptop &mdash; a machine on your own LAN needs a reachable address or a tunnel.';
  $('port').required = !android;
}

$('protocol').addEventListener('change', applyProtocol);

function resetForm() {
  $('id').value = '';
  $('form').reset();
  $('protocol').value = 'vnc';
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
  $('port').value = h.port;
  $('username').value = h.username || '';
  $('password').value = '';
  for (const id of ANDROID_ONLY) $(id).value = h[id] || '';
  applyProtocol();
  $('form-title').textContent = 'Edit ' + h.name;
  $('save').textContent = 'Save changes';
  $('cancel').hidden = false;
  // The single most confusing thing about editing a saved credential is not
  // knowing whether leaving the field blank wipes it. Say so explicitly.
  $('pw-hint').textContent = h.has_password
    ? 'A password is saved. Leave blank to keep it; type a new one to replace it.'
    : 'No password saved for this host.';
  $('name').focus();
}

$('list').addEventListener('click', async (e) => {
  const del = e.target.getAttribute('data-del');
  const edit = e.target.getAttribute('data-edit');
  if (edit) return loadForEdit(edit);
  if (!del) return;
  const h = hosts.find((x) => x.id === del);
  if (!confirm('Delete "' + (h ? h.name : del) + '"? Its saved password is deleted too.')) return;
  try {
    await call('DELETE', '/hosts/' + encodeURIComponent(del));
    if ($('id').value === del) resetForm();
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
    port: Number($('port').value),
    username: $('username').value.trim(),
  };
  if (body.protocol === 'android') {
    for (const id of ANDROID_ONLY) body[id] = $(id).value.trim();
  }
  if ($('password').value) body.password = $('password').value;
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
