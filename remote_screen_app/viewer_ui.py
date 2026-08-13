"""Standalone Android viewer — what "Pop out" opens for an android host.

A VNC host pops out to the vendored noVNC page, which is a real standalone
document and needs nothing from us. Android had no equivalent: the mirror only
existed as a React component inside the workspace window, so Pop out had
nothing to open and silently did nothing (the handler literally skipped
`src === 'android'`).

This is that missing document: the same WebSocket, the same canvas painting,
the same tap mapping and the same three navigation keys, in one dependency-
free page. Deliberately NOT a second copy of the viewer's logic in another
framework — it is small enough that duplicating ~60 lines of socket handling
is cheaper than shipping a build step for a pop-out window.

Served from the app's own origin, so the WebSocket is same-origin here and the
apex ``aw_id_jwt`` cookie authorises it exactly as it does in the SPA.
"""
from __future__ import annotations

import json

_VIEWER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; background: #000; color: #e5e7eb; display: flex;
         flex-direction: column;
         font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
  #screen { flex: 1; min-height: 0; position: relative; }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%;
           object-fit: contain; }
  #msg { position: absolute; inset: 0; display: flex; align-items: center;
         justify-content: center; font-size: 13px; color: #9ca3af;
         text-align: center; padding: 0 24px; }
  nav { flex: none; display: flex; align-items: center; justify-content: center;
        gap: 44px; padding: 10px 0; background: #0b0b10;
        border-top: 1px solid #23232f; }
  nav button { background: transparent; border: 0; color: #e5e7eb; cursor: pointer;
               padding: 8px; border-radius: 10px; line-height: 0;
               transition: background .12s; }
  nav button:hover { background: rgba(255,255,255,.08); }
  nav button:active { background: rgba(255,255,255,.16); }
  svg { width: 32px; height: 32px; }
</style>
</head>
<body>
<div id="screen">
  <canvas id="c"></canvas>
  <div id="msg">Connecting\\u2026</div>
</div>
<nav>
  <button id="back" title="Back" aria-label="Back">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
  </button>
  <button id="home" title="Home" aria-label="Home">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="8"/></svg>
  </button>
  <button id="recents" title="Recents" aria-label="Recents">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="5" y="5" width="14" height="14" rx="1.5"/></svg>
  </button>
</nav>

<script>
const HOST_ID = __HOST_ID__;
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const msg = document.getElementById('msg');
let ws = null, attempt = 0, timer = null;

function say(text) { msg.textContent = text || ''; msg.style.display = text ? 'flex' : 'none'; }

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/api/apps/remote-screen/ws/android/${encodeURIComponent(HOST_ID)}`;
}

function connect() {
  ws = new WebSocket(wsUrl());
  ws.binaryType = 'blob';
  ws.onopen = () => { attempt = 0; say('Connecting\\u2026'); };
  ws.onmessage = async (ev) => {
    if (!(ev.data instanceof Blob)) return;
    try {
      const bmp = await createImageBitmap(ev.data);
      canvas.width = bmp.width; canvas.height = bmp.height;
      ctx.drawImage(bmp, 0, 0);
      bmp.close();
      say('');
    } catch (_e) {
      // A frame the browser refuses to decode means it arrived truncated —
      // the server drops those now, so this is belt-and-braces. Never paint a
      // partial image: a stale picture that looks live is the worst outcome.
    }
  };
  ws.onclose = () => {
    ws = null;
    attempt += 1;
    if (attempt > 6) { say('Stream lost. Close this window and pop out again.'); return; }
    say('Reconnecting\\u2026');
    timer = setTimeout(connect, Math.min(1000 * attempt, 5000));
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

canvas.addEventListener('click', (e) => {
  if (!canvas.width) return;
  const r = canvas.getBoundingClientRect();
  // object-fit: contain letterboxes the canvas, so the drawn image is smaller
  // than the element. Mapping against the ELEMENT box would put every tap off
  // by the letterbox offset; scale by the fitted rect instead.
  const scale = Math.min(r.width / canvas.width, r.height / canvas.height);
  const drawnW = canvas.width * scale, drawnH = canvas.height * scale;
  const offX = r.left + (r.width - drawnW) / 2;
  const offY = r.top + (r.height - drawnH) / 2;
  const x = Math.round((e.clientX - offX) / scale);
  const y = Math.round((e.clientY - offY) / scale);
  if (x < 0 || y < 0 || x > canvas.width || y > canvas.height) return;
  send({ type: 'tap', x, y });
});

document.getElementById('back').onclick = () => send({ type: 'key', code: 'KEYCODE_BACK' });
document.getElementById('home').onclick = () => send({ type: 'key', code: 'KEYCODE_HOME' });
document.getElementById('recents').onclick = () => send({ type: 'key', code: 'KEYCODE_APP_SWITCH' });

window.addEventListener('beforeunload', () => { clearTimeout(timer); if (ws) ws.close(); });
connect();
</script>
</body>
</html>
"""


def viewer_html(host_id: str, name: str) -> str:
    """The standalone page for one android host.

    ``host_id``/``name`` are JSON-encoded rather than interpolated raw — they
    come from the database, and a name with a quote in it would otherwise
    break out of the title or the JS string.
    """
    return (_VIEWER_TEMPLATE
            .replace("__HOST_ID__", json.dumps(host_id))
            .replace("__NAME__", (name or "Remote Screen")
                     .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")))
