// Integrated-mode entrypoint — dynamic-imported by aw-workspace-ui's
// loadComponentPlugin() once this app is installed with "ui:code" +
// "ui:slots:core.nav.workspace" granted. Built by `npm run build` ->
// ui/dist/rdp-vnc.js, referenced from aw-app.json's contributes.frontend.bundle.
//
// Ported from the monolith's src/app/src/components/RemoteDesktopWindow.jsx,
// with three deliberate changes:
//
// 1. The Android-emulator entry is GONE. In the monolith it was a second,
//    unrelated transport (screen-mirror over the remote-agent exec channel)
//    wedged into the same connection picker; it belongs to whatever app owns
//    the emulator, not to a VNC client.
// 2. The "Manage connections" modal now only OPENS Settings — host CRUD lives
//    in the declarative settings panel (windows/hosts.json) so there is one
//    editor, not two that can disagree.
// 3. The noVNC iframe gets an ABSOLUTE host/port instead of a relative `path`.
//    In a BYOD workspace the SPA and the workspace API are different origins,
//    and aw-workspace-ui's WebSocket shim (apiBase.js) only rewrites upgrades
//    made from the SPA's own window — it cannot reach inside the noVNC iframe,
//    which builds its own socket. Deriving host/port from host.app.wsUrl() is
//    what makes the bridge connect on a tunneled workspace at all.

const WIN_ID = 'rdp-vnc.main';

export function register(host) {
  const { useState, useEffect, useCallback, useRef } = host.React;
  const api = host.app || host.sdk?.api || {};

  async function call(method, path, body) {
    const init = { method };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    const res = await api.fetch(`/api/apps/rdp-vnc${path}`, init);
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch (_e) { detail = await res.text(); }
      throw new Error(`${res.status}: ${detail}`);
    }
    return res.json();
  }

  // noVNC's vnc.html is vendored in aw-workspace-ui/public/novnc and served
  // from the SPA origin. It takes host/port/path separately, so point it at
  // the workspace API origin explicitly (see header note 3).
  function novncUrl(hostId, password, settings) {
    const wsHref = api.wsUrl(`/api/apps/rdp-vnc/ws/bridge/${hostId}`);
    const u = new URL(wsHref);
    const params = new URLSearchParams({
      host: u.hostname,
      port: u.port || (u.protocol === 'wss:' ? '443' : '80'),
      // noVNC wants the path WITHOUT a leading slash.
      path: u.pathname.replace(/^\//, '') + u.search,
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
        <rect x="2" y="4" width="20" height="13" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </svg>
    );
  }

  // ── 1. Workspace nav row ────────────────────────────────────────────────
  function RemoteDesktopNavRow() {
    return (
      <button
        onClick={() => window.__awOpenAppWindow?.(WIN_ID)}
        className="w-full text-left px-3 py-2 hover:bg-white/5 transition-colors flex items-center gap-2"
      >
        <MonitorIcon />
        <span className="text-xs text-[var(--color-text-primary)]">Remote Desktop</span>
      </button>
    );
  }

  // ── 2. Window body ──────────────────────────────────────────────────────
  function RemoteDesktopWindowBody() {
    const [hosts, setHosts] = useState([]);
    const [settings, setSettings] = useState(null);
    const [selectedId, setSelectedId] = useState('');
    const [iframeSrc, setIframeSrc] = useState('');
    const [iframeKey, setIframeKey] = useState(0);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [error, setError] = useState(null);
    const iframeRef = useRef(null);

    const selected = hosts.find((h) => h.id === selectedId);

    const refresh = useCallback(async () => {
      const [{ hosts: rows }, cfg] = await Promise.all([
        call('GET', '/hosts'),
        call('GET', '/settings'),
      ]);
      setHosts(rows || []);
      setSettings(cfg);
      return rows || [];
    }, []);

    useEffect(() => {
      refresh()
        .then((rows) => { if (!selectedId && rows.length) setSelectedId(rows[0].id); })
        .catch((e) => setError(e.message));
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const connect = useCallback(async (id) => {
      if (!id) { setIframeSrc(''); return; }
      setError(null);
      const row = hosts.find((h) => h.id === id);
      if (row && !row.supported) {
        // Fail loudly here rather than opening a bridge the browser can't
        // speak — the WS would just close 4415 with no visible explanation.
        setIframeSrc('');
        setError(`${row.name} is saved as ${row.protocol.toUpperCase()}, which has no browser client yet — only VNC can be opened from here.`);
        return;
      }
      try {
        const { password } = await call('GET', `/hosts/${id}/credentials`);
        setIframeSrc(novncUrl(id, password, settings));
        setIframeKey((k) => k + 1);
      } catch (e) {
        setError(e.message);
      }
    }, [hosts, settings]);

    useEffect(() => {
      if (selectedId && settings) connect(selectedId);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedId, settings]);

    // Opens this app's own declarative hosts window (the same spec the
    // Settings gear renders, via contributes.settings_panels) — there is no
    // global "open app settings" helper in the SPA, only __awOpenAppWindow.
    const openSettings = () => {
      setPickerOpen(false);
      window.__awOpenAppWindow?.('rdp-vnc.hosts');
    };

    return (
      <div className="flex flex-col h-full bg-black">
        {/* Toolbar */}
        <div className="flex items-center gap-1.5 px-2 py-1.5 bg-[var(--color-bg-header)] border-b border-[var(--color-border)] shrink-0">
          <div className="relative">
            <button
              onClick={() => setPickerOpen((v) => !v)}
              className="flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors"
              title="Switch host"
            >
              <span className="truncate">{selected ? selected.name : 'No hosts'}</span>
              <svg className={`w-3 h-3 shrink-0 text-[var(--color-text-muted)] transition-transform ${pickerOpen ? 'rotate-180' : ''}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
            </button>
            {pickerOpen && (
              <div className="absolute left-0 top-full mt-1 w-72 max-h-80 overflow-y-auto bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-2xl shadow-black/60 z-50">
                {hosts.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => { setSelectedId(h.id); setPickerOpen(false); }}
                    className={`w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${h.id === selectedId ? 'bg-[var(--color-accent)]/10' : ''}`}
                  >
                    <div className="text-xs font-medium text-[var(--color-text-primary)] truncate">{h.name}</div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono">
                      {h.host}:{h.port}{h.supported ? '' : ` · ${h.protocol.toUpperCase()} (not connectable)`}
                    </div>
                  </button>
                ))}
                <button onClick={openSettings}
                  className="w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5">
                  <svg className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
                  Manage hosts
                </button>
              </div>
            )}
          </div>

          <button onClick={() => selectedId && connect(selectedId)}
            className="p-1.5 rounded hover:bg-white/10 transition-colors" title="Reconnect">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-3-6.7" /><path d="M21 3v6h-6" />
            </svg>
          </button>

          {/* Focuses noVNC's own hidden keyboard-capture input inside the
              iframe (window.UI.toggleVirtualKeyboard — same mechanism as
              noVNC's touch control-bar button), so mobile users don't have to
              find its collapsed handle inside the small embedded view. */}
          <button onClick={() => iframeRef.current?.contentWindow?.UI?.toggleVirtualKeyboard?.()}
            className="p-1.5 rounded hover:bg-white/10 transition-colors" title="Toggle keyboard">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="6" width="20" height="12" rx="2" />
              <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" />
            </svg>
          </button>

          <button
            onClick={async () => {
              if (!selectedId) return;
              const { password } = await call('GET', `/hosts/${selectedId}/credentials`);
              window.open(novncUrl(selectedId, password, settings),
                `rdp-vnc-${selectedId}`, 'popup=1,width=1280,height=800');
            }}
            disabled={!selectedId}
            className="p-1.5 rounded hover:bg-white/10 transition-colors disabled:opacity-30"
            title="Pop out to new window">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
              <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </button>
        </div>

        {/* Viewport */}
        <div className="flex-1 relative">
          {error ? (
            <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300">{error}</div>
          ) : !hosts.length ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]">
              <span>No hosts yet.</span>
              <button onClick={openSettings} className="text-[var(--color-accent)] hover:underline">Add one in Settings</button>
            </div>
          ) : (
            <iframe ref={iframeRef} key={iframeKey} src={iframeSrc}
              className="absolute inset-0 w-full h-full border-0" title="Remote Desktop" />
          )}
        </div>

        {pickerOpen && <div className="fixed inset-0 z-40" onClick={() => setPickerOpen(false)} />}
      </div>
    );
  }

  host.registerSlot('core.nav.workspace', RemoteDesktopNavRow);
  host.registerWindow(WIN_ID, RemoteDesktopWindowBody);
}
