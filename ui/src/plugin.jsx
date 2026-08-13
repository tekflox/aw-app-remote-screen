// Integrated-mode entrypoint — dynamic-imported by aw-workspace-ui's
// loadComponentPlugin() once this app is installed with "ui:code" +
// "ui:slots:core.nav.workspace" granted. Built by `npm run build` ->
// ui/dist/remote-screen.js, referenced from aw-app.json's
// contributes.frontend.bundle.
//
// Ported from the monolith's src/app/src/components/RemoteDesktopWindow.jsx.
// Four deliberate differences:
//
// 1. The Android-emulator entry is no longer a hard-wired extra row in the
//    picker — it is a protocol like any other, driven off the host's own
//    `protocol` column, so N android devices work the same as N VNC boxes.
// 2. Host CRUD lives in the declarative settings panel (windows/hosts.json),
//    so there is one editor rather than two that can disagree.
// 3. The noVNC iframe gets an ABSOLUTE host/port. In a BYOD workspace the SPA
//    and the workspace API are different origins, and aw-workspace-ui's
//    WebSocket shim (apiBase.js) only rewrites upgrades made from the SPA's
//    own window — it cannot reach inside the noVNC iframe, which builds its
//    own socket.
// 4. The toolbar lives in the HOST's title bar via registerWindowActions, not
//    in a second bar of our own. The monolith drew its own full-width header
//    (with its own maximize/close duplicating the host's), which stacked two
//    title bars on every window.

const WIN_ID = 'remote-screen.main';

export function register(host) {
  const { useState, useEffect, useCallback, useRef, useSyncExternalStore } = host.React;

  // host.app.* ALREADY prefixes /api/apps/<slug> (pluginHost.js). Passing a
  // full path here double-prefixes it into
  // /api/apps/remote-screen/api/apps/remote-screen/... and every call 404s,
  // which surfaces as an empty "No hosts" picker over a 404 body.
  const api = host.app;

  async function call(method, path, body) {
    const init = { method };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    const res = await api.fetch(path, init);
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch (_e) { detail = await res.text(); }
      throw new Error(`${res.status}: ${detail}`);
    }
    return res.json();
  }

  // ── shared viewer state ──────────────────────────────────────────────────
  // The picker lives in the title bar and the viewport lives in the body, and
  // they are registered as two INDEPENDENT slot components — so they cannot
  // share React state through a common parent. A module-scoped store with
  // useSyncExternalStore is the smallest thing that keeps them in step.
  const store = {
    state: {
      hosts: [], settings: null, selectedId: '', src: '', srcKey: 0, error: null,
    },
    creds: null,
    iframe: null,
    androidWs: null,
    listeners: new Set(),
    loading: null,

    subscribe(fn) {
      store.listeners.add(fn);
      return () => store.listeners.delete(fn);
    },
    get() { return store.state; },
    set(patch) {
      store.state = { ...store.state, ...patch };
      store.listeners.forEach((fn) => fn());
    },

    async load() {
      // Both components mount at once; only fetch once.
      if (store.loading) return store.loading;
      store.loading = (async () => {
        try {
          const [{ hosts }, settings] = await Promise.all([
            call('GET', '/hosts'), call('GET', '/settings'),
          ]);
          store.set({ hosts: hosts || [], settings, error: null });
          if (!store.state.selectedId && hosts?.length) store.select(hosts[0].id);
        } catch (e) {
          store.set({ error: e.message });
        } finally {
          store.loading = null;
        }
      })();
      return store.loading;
    },

    select(id) {
      store.set({ selectedId: id });
      store.connect(id);
    },

    // Android's three system buttons. They are not part of the mirrored
    // framebuffer — screencap captures the app surface, while Back/Home/
    // Recents are the OS navigation bar, so without these the device is
    // effectively view-only past the first screen. `adb shell input keyevent`
    // is the same channel taps already use.
    sendKey(code) {
      const ws = store.androidWs;
      if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'key', code }));
    },

    async connect(id) {
      const row = store.state.hosts.find((h) => h.id === id);
      if (!row) return;
      if (!row.supported) {
        // Fail loudly rather than opening a transport the browser can't speak
        // — the socket would just close with a code nobody sees.
        store.set({ src: '', error: `${row.name} is saved as ${row.protocol.toUpperCase()}, `
          + `which has no browser client yet.` });
        return;
      }
      try {
        if (row.protocol === 'android') {
          store.creds = null;
          store.set({ src: 'android', srcKey: store.state.srcKey + 1, error: null });
          return;
        }
        const creds = await call('GET', `/hosts/${id}/credentials`);
        store.creds = creds;
        store.set({
          src: novncUrl(id, creds.password, store.state.settings),
          srcKey: store.state.srcKey + 1,
          error: null,
        });
      } catch (e) {
        store.set({ error: e.message });
      }
    },
  };

  function useViewer() {
    return useSyncExternalStore(store.subscribe, store.get);
  }

  // noVNC's vnc.html is vendored in aw-workspace-ui/public/novnc and served
  // from the SPA origin. It takes host/port/path separately, so point it at
  // the workspace API origin explicitly (see header note 3).
  function novncUrl(hostId, password, settings) {
    const u = new URL(api.wsUrl(`/ws/bridge/${hostId}`));
    const params = new URLSearchParams({
      host: u.hostname,
      port: u.port || (u.protocol === 'wss:' ? '443' : '80'),
      path: u.pathname.replace(/^\//, '') + u.search,   // noVNC wants no leading slash
      encrypt: u.protocol === 'wss:' ? '1' : '0',
      autoconnect: 'true',
      reconnect: 'true',
      resize: settings?.default_scaling || 'scale',
      view_only: settings?.view_only ? '1' : '0',
    });
    if (password) params.set('password', password);
    return `/novnc/vnc.html?${params.toString()}`;
  }

  function MonitorIcon({ className }) {
    return (
      <svg className={className || 'w-3.5 h-3.5 shrink-0 text-[var(--color-text-muted)]'}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="4" width="20" height="13" rx="2" /><path d="M8 21h8M12 17v4" />
      </svg>
    );
  }

  const openSettings = () => window.__awOpenAppWindow?.('remote-screen.hosts');

  // ── 1. Workspace nav row ────────────────────────────────────────────────
  function RemoteScreenNavRow() {
    return (
      <button
        onClick={() => window.__awOpenAppWindow?.(WIN_ID)}
        className="w-full text-left px-3 py-2 hover:bg-white/5 transition-colors flex items-center gap-2"
      >
        <MonitorIcon />
        <span className="text-xs text-[var(--color-text-primary)]">Remote Screen</span>
      </button>
    );
  }

  // ── 2. Title-bar actions ────────────────────────────────────────────────
  function RemoteScreenWindowActions() {
    const { hosts, selectedId } = useViewer();
    const [open, setOpen] = useState(false);
    const [anchor, setAnchor] = useState(null);
    const btnRef = useRef(null);
    const selected = hosts.find((h) => h.id === selectedId);
    const isAndroid = selected?.protocol === 'android';

    useEffect(() => { store.load(); }, []);

    // BasicWindow's root is overflow-hidden (rounded corners), so an absolute
    // popover in the header is clipped — portal to document.body with fixed
    // coords taken from the button instead.
    const toggle = useCallback(() => {
      setOpen((v) => {
        if (v) return false;
        const r = btnRef.current?.getBoundingClientRect();
        if (r) setAnchor({ top: r.bottom + 6, left: r.left });
        return true;
      });
    }, []);

    useEffect(() => {
      if (!open) return;
      const onKey = (e) => e.key === 'Escape' && setOpen(false);
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [open]);

    const btn = 'p-1.5 rounded hover:bg-white/10 transition-colors';
    const icon = 'w-4 h-4 text-[var(--color-text-muted)]';

    return (
      <>
        <button ref={btnRef} onClick={toggle}
          className="flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors"
          title="Switch host">
          <span className="truncate">{selected ? selected.name : 'No hosts'}</span>
          <svg className={`w-3 h-3 shrink-0 text-[var(--color-text-muted)] transition-transform ${open ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
        </button>

        {open && host.ReactDOM.createPortal(
          <>
            <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
            <div className="fixed w-72 max-h-80 overflow-y-auto bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-2xl shadow-black/60 z-[9999]"
              style={{ top: anchor?.top ?? 0, left: anchor?.left ?? 0 }}>
              {hosts.map((h) => (
                <button key={h.id}
                  onClick={() => { store.select(h.id); setOpen(false); }}
                  className={`w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${h.id === selectedId ? 'bg-[var(--color-accent)]/10' : ''}`}>
                  <div className="text-xs font-medium text-[var(--color-text-primary)] truncate">{h.name}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono">
                    {h.protocol === 'android'
                      ? `android · ${h.device_serial || 'default device'}`
                      : `${h.host}:${h.port}`}
                    {h.supported ? '' : ' · not connectable'}
                  </div>
                </button>
              ))}
              <button onClick={() => { setOpen(false); openSettings(); }}
                className="w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5">
                <svg className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
                Manage hosts
              </button>
            </div>
          </>, document.body)}

        <button onClick={() => selectedId && store.connect(selectedId)} className={btn} title="Reconnect">
          <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12a9 9 0 1 1-3-6.7" /><path d="M21 3v6h-6" />
          </svg>
        </button>

        {/* Focuses noVNC's own hidden keyboard-capture input inside the iframe
            (same mechanism as its touch control-bar button), so mobile users
            don't have to find its collapsed handle in the embedded view. */}
        <button onClick={() => store.iframe?.contentWindow?.UI?.toggleVirtualKeyboard?.()}
          className={btn} title="Toggle keyboard">
          <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="6" width="20" height="12" rx="2" />
            <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" />
          </svg>
        </button>

        {isAndroid && (
          <>
            <span className="w-px h-4 bg-[var(--color-border)] mx-0.5" />
            <button onClick={() => store.sendKey('KEYCODE_BACK')} className={btn} title="Back">
              <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <button onClick={() => store.sendKey('KEYCODE_HOME')} className={btn} title="Home">
              <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="8" />
              </svg>
            </button>
            <button onClick={() => store.sendKey('KEYCODE_APP_SWITCH')} className={btn} title="Recents">
              <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="5" y="5" width="14" height="14" rx="1.5" />
              </svg>
            </button>
            <span className="w-px h-4 bg-[var(--color-border)] mx-0.5" />
          </>
        )}

        <button
          onClick={() => {
            const { src } = store.get();
            if (src && src !== 'android') window.open(src, `remote-screen-${selectedId}`, 'popup=1,width=1280,height=800');
          }}
          disabled={!selectedId} className={`${btn} disabled:opacity-30`} title="Pop out">
          <svg className={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
            <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </button>
      </>
    );
  }

  // ── 3. Window body ──────────────────────────────────────────────────────
  function RemoteScreenWindowBody() {
    const { hosts, selectedId, src, srcKey, error } = useViewer();
    const iframeRef = useRef(null);
    const canvasRef = useRef(null);
    const selected = hosts.find((h) => h.id === selectedId);
    const isAndroid = selected?.protocol === 'android';

    useEffect(() => { store.load(); }, []);
    useEffect(() => { store.iframe = iframeRef.current; }, [srcKey]);

    // noVNC's vnc.html only reads ?password= from the URL and builds its RFB
    // with `credentials: { password }` — there is no username URL param. That
    // is enough for standard VNC auth (type 2) but NOT for the Apple Remote
    // Desktop scheme (type 30) macOS Screen Sharing offers, which demands
    // username AND password: noVNC fires `credentialsrequired` and puts up its
    // own prompt. Answering it from the same-origin iframe is what makes a
    // saved macOS host log in without the user re-typing anything.
    const injectCredentials = useCallback(() => {
      const win = iframeRef.current?.contentWindow;
      const creds = store.creds;
      store.iframe = iframeRef.current;
      if (!win || !creds) return;
      let tries = 0;
      const attach = () => {
        const rfb = win.UI?.rfb;
        if (!rfb) { if (++tries < 40) setTimeout(attach, 100); return; }
        rfb.addEventListener('credentialsrequired', () => {
          rfb.sendCredentials({ username: creds.username || '', password: creds.password || '' });
        });
      };
      attach();
    }, []);

    // Android has no VNC server: frames arrive as binary PNGs on the app's own
    // WebSocket and taps go back as JSON. Painting into a canvas (rather than
    // an <img> per frame) avoids churning a blob URL 2x a second.
    // The monolith's AndroidViewerPanel reconnected on close; dropping that in
    // the port meant a single dead socket froze the picture on its last frame
    // — the mirror still LOOKED live while the device had moved on. A stale
    // mirror is worse than a visibly broken one, so reconnect, and surface it
    // when we cannot.
    useEffect(() => {
      if (!isAndroid || !selectedId) return undefined;
      let alive = true;
      let ws = null;
      let timer = null;
      let attempt = 0;

      const connect = () => {
        if (!alive) return;
        ws = new WebSocket(api.wsUrl(`/ws/android/${selectedId}`));
        ws.binaryType = 'blob';
        store.androidWs = ws;   // the tap/key handlers send back on this socket
        ws.onopen = () => { attempt = 0; store.set({ error: null }); };
        ws.onmessage = async (ev) => {
          if (!alive || !(ev.data instanceof Blob)) return;
          const bmp = await createImageBitmap(ev.data);
          const c = canvasRef.current;
          if (!c) { bmp.close(); return; }
          c.width = bmp.width; c.height = bmp.height;
          c.getContext('2d').drawImage(bmp, 0, 0);
          bmp.close();
        };
        ws.onclose = () => {
          if (!alive) return;
          store.androidWs = null;
          attempt += 1;
          if (attempt > 6) { store.set({ error: 'Android stream lost — press Reconnect.' }); return; }
          timer = setTimeout(connect, Math.min(1000 * attempt, 5000));
        };
      };
      connect();

      return () => {
        alive = false;
        clearTimeout(timer);
        store.androidWs = null;
        try { ws && ws.close(); } catch (_e) { /* already gone */ }
      };
    }, [isAndroid, selectedId, srcKey]);

    const tap = (e) => {
      const c = canvasRef.current;
      if (!c) return;
      const r = c.getBoundingClientRect();
      // Map CSS-rendered coords to the device's natural pixels, so a tap lands
      // correctly no matter how the canvas is scaled.
      const x = Math.round((e.clientX - r.left) * (c.width / r.width));
      const y = Math.round((e.clientY - r.top) * (c.height / r.height));
      if (store.androidWs?.readyState === WebSocket.OPEN) {
        store.androidWs.send(JSON.stringify({ type: 'tap', x, y }));
      }
    };

    return (
      <div className="flex flex-col h-full bg-black">
        <div className="flex-1 relative">
          {error ? (
            <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300">{error}</div>
          ) : !hosts.length ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]">
              <span>No hosts yet.</span>
              <button onClick={openSettings} className="text-[var(--color-accent)] hover:underline">Add one in Settings</button>
            </div>
          ) : isAndroid ? (
            <canvas ref={canvasRef} onClick={tap}
              className="absolute inset-0 w-full h-full object-contain" />
          ) : (
            <iframe ref={iframeRef} key={srcKey} src={src} onLoad={injectCredentials}
              className="absolute inset-0 w-full h-full border-0" title="Remote Screen" />
          )}
        </div>
      </div>
    );
  }

  host.registerSlot('core.nav.workspace', RemoteScreenNavRow);
  host.registerWindow(WIN_ID, RemoteScreenWindowBody);
  host.registerWindowActions(WIN_ID, RemoteScreenWindowActions);
}
