const O = "remote-screen.main";
function j(e) {
  const { useState: K, useEffect: N, useCallback: $, useRef: W, useSyncExternalStore: P } = e.React, S = e.app;
  async function R(r, o, c) {
    const l = { method: r }, i = await S.fetch(o, l);
    if (!i.ok) {
      let p = "";
      try {
        p = (await i.json()).detail || "";
      } catch {
        p = await i.text();
      }
      throw new Error(`${i.status}: ${p}`);
    }
    return i.json();
  }
  const t = window.__awRemoteScreenStore || (window.__awRemoteScreenStore = {
    state: {
      hosts: [],
      settings: null,
      selectedId: "",
      src: "",
      srcKey: 0,
      error: null
    },
    creds: null,
    iframe: null,
    androidWs: null,
    listeners: /* @__PURE__ */ new Set(),
    loading: null,
    subscribe(r) {
      return t.listeners.add(r), () => t.listeners.delete(r);
    },
    get() {
      return t.state;
    },
    set(r) {
      t.state = { ...t.state, ...r }, t.listeners.forEach((o) => o());
    },
    async load() {
      return t.loading || (t.loading = (async () => {
        try {
          const [{ hosts: r }, o] = await Promise.all([
            R("GET", "/hosts"),
            R("GET", "/settings")
          ]);
          t.set({ hosts: r || [], settings: o, error: null }), !t.state.selectedId && (r != null && r.length) && t.select(r[0].id);
        } catch (r) {
          t.set({ error: r.message });
        } finally {
          t.loading = null;
        }
      })()), t.loading;
    },
    select(r) {
      t.set({ selectedId: r }), t.connect(r);
    },
    // Android's three system buttons. They are not part of the mirrored
    // framebuffer — screencap captures the app surface, while Back/Home/
    // Recents are the OS navigation bar, so without these the device is
    // effectively view-only past the first screen. `adb shell input keyevent`
    // is the same channel taps already use.
    sendKey(r) {
      const o = t.androidWs;
      (o == null ? void 0 : o.readyState) === WebSocket.OPEN && o.send(JSON.stringify({ type: "key", code: r }));
    },
    async connect(r) {
      const o = t.state.hosts.find((c) => c.id === r);
      if (o) {
        if (!o.supported) {
          t.set({ src: "", error: `${o.name} is saved as ${o.protocol.toUpperCase()}, which has no browser client yet.` });
          return;
        }
        try {
          if (o.protocol === "android") {
            t.creds = null, t.set({ src: "android", srcKey: t.state.srcKey + 1, error: null });
            return;
          }
          const c = await R("GET", `/hosts/${r}/credentials`);
          t.creds = c, t.set({
            src: U(r, c.password, t.state.settings),
            srcKey: t.state.srcKey + 1,
            error: null
          });
        } catch (c) {
          t.set({ error: c.message });
        }
      }
    }
  });
  function I() {
    return P(t.subscribe, t.get);
  }
  function U(r, o, c) {
    const l = new URL(S.wsUrl(`/ws/bridge/${r}`)), i = new URLSearchParams({
      host: l.hostname,
      port: l.port || (l.protocol === "wss:" ? "443" : "80"),
      path: l.pathname.replace(/^\//, "") + l.search,
      // noVNC wants no leading slash
      encrypt: l.protocol === "wss:" ? "1" : "0",
      autoconnect: "true",
      reconnect: "true",
      resize: (c == null ? void 0 : c.default_scaling) || "scale",
      view_only: c != null && c.view_only ? "1" : "0"
    });
    return o && i.set("password", o), `/novnc/vnc.html?${i.toString()}`;
  }
  const A = () => {
    var r;
    return (r = window.__awOpenAppWindow) == null ? void 0 : r.call(window, "remote-screen.hosts");
  }, M = "p-2 rounded-lg hover:bg-white/10 active:bg-white/20 transition-colors", _ = "w-8 h-8 text-[var(--color-text-primary)]";
  function D() {
    const { hosts: r, selectedId: o } = I(), [c, l] = K(!1), [i, p] = K(null), g = W(null), b = r.find((s) => s.id === o);
    N(() => {
      t.load();
    }, []);
    const v = $(() => {
      l((s) => {
        var m;
        if (s) return !1;
        const f = (m = g.current) == null ? void 0 : m.getBoundingClientRect();
        return f && p({ top: f.bottom + 6, left: f.left }), !0;
      });
    }, []);
    N(() => {
      if (!c) return;
      const s = (f) => f.key === "Escape" && l(!1);
      return window.addEventListener("keydown", s), () => window.removeEventListener("keydown", s);
    }, [c]);
    const C = "p-1.5 rounded hover:bg-white/10 transition-colors", k = "w-4 h-4 text-[var(--color-text-muted)]";
    return /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h(
      "button",
      {
        ref: g,
        onClick: v,
        className: "flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors",
        title: "Switch host"
      },
      /* @__PURE__ */ e.h("span", { className: "truncate" }, b ? b.name : "No hosts"),
      /* @__PURE__ */ e.h(
        "svg",
        {
          className: `w-3 h-3 shrink-0 text-[var(--color-text-muted)] transition-transform ${c ? "rotate-180" : ""}`,
          viewBox: "0 0 24 24",
          fill: "none",
          stroke: "currentColor",
          strokeWidth: "2"
        },
        /* @__PURE__ */ e.h("path", { d: "M6 9l6 6 6-6" })
      )
    ), c && e.ReactDOM.createPortal(
      /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h("div", { className: "fixed inset-0 z-[9998]", onClick: () => l(!1) }), /* @__PURE__ */ e.h(
        "div",
        {
          className: "fixed w-72 max-h-80 overflow-y-auto bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-2xl shadow-black/60 z-[9999]",
          style: { top: (i == null ? void 0 : i.top) ?? 0, left: (i == null ? void 0 : i.left) ?? 0 }
        },
        r.map((s) => /* @__PURE__ */ e.h(
          "button",
          {
            key: s.id,
            onClick: () => {
              t.select(s.id), l(!1);
            },
            className: `w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${s.id === o ? "bg-[var(--color-accent)]/10" : ""}`
          },
          /* @__PURE__ */ e.h("div", { className: "text-xs font-medium text-[var(--color-text-primary)] truncate" }, s.name),
          /* @__PURE__ */ e.h("div", { className: "text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono" }, s.protocol === "android" ? `android · ${s.device_serial || "default device"}` : `${s.host}:${s.port}`, s.supported ? "" : " · not connectable")
        )),
        /* @__PURE__ */ e.h(
          "button",
          {
            onClick: () => {
              l(!1), A();
            },
            className: "w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5"
          },
          /* @__PURE__ */ e.h("svg", { className: "w-3 h-3 shrink-0", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M12 5v14M5 12h14" })),
          "Manage hosts"
        )
      )),
      document.body
    ), /* @__PURE__ */ e.h("button", { onClick: () => o && t.connect(o), className: C, title: "Reconnect" }, /* @__PURE__ */ e.h("svg", { className: k, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M21 12a9 9 0 1 1-3-6.7" }), /* @__PURE__ */ e.h("path", { d: "M21 3v6h-6" }))), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var s, f, m, E;
          return (E = (m = (f = (s = t.iframe) == null ? void 0 : s.contentWindow) == null ? void 0 : f.UI) == null ? void 0 : m.toggleVirtualKeyboard) == null ? void 0 : E.call(m);
        },
        className: C,
        title: "Toggle keyboard"
      },
      /* @__PURE__ */ e.h("svg", { className: k, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "2", y: "6", width: "20", height: "12", rx: "2" }), /* @__PURE__ */ e.h("path", { d: "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" }))
    ), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          if (!o) return;
          const { src: s } = t.get(), f = s === "android" ? S.absoluteApiUrl(`/panel/viewer/${o}`) : s;
          f && window.open(f, `remote-screen-${o}`, "popup=1,width=1280,height=800");
        },
        disabled: !o,
        className: `${C} disabled:opacity-30`,
        title: "Pop out"
      },
      /* @__PURE__ */ e.h("svg", { className: k, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" }), /* @__PURE__ */ e.h("polyline", { points: "15 3 21 3 21 9" }), /* @__PURE__ */ e.h("line", { x1: "10", y1: "14", x2: "21", y2: "3" }))
    ));
  }
  function L() {
    const { hosts: r, selectedId: o, src: c, srcKey: l, error: i } = I(), p = W(null), g = W(null), b = r.find((d) => d.id === o), v = (b == null ? void 0 : b.protocol) === "android";
    N(() => {
      t.load();
    }, []), N(() => {
      t.iframe = p.current;
    }, [l]);
    const C = $(() => {
      var x;
      const d = (x = p.current) == null ? void 0 : x.contentWindow, n = t.creds;
      if (t.iframe = p.current, !d || !n || !n.password && !n.username) return;
      let a = 0;
      const h = () => {
        var w;
        const u = (w = d.UI) == null ? void 0 : w.rfb;
        if (!u) {
          ++a < 40 && setTimeout(h, 100);
          return;
        }
        u.addEventListener("credentialsrequired", () => {
          u.sendCredentials({ username: n.username || "", password: n.password || "" });
        });
      };
      h();
    }, []);
    N(() => {
      if (!v || !o) return;
      let d = !0, n = null, a = null, h = 0;
      const x = () => {
        d && (n = new WebSocket(S.wsUrl(`/ws/android/${o}`)), n.binaryType = "blob", t.androidWs = n, n.onopen = () => {
          h = 0, t.set({ error: null });
        }, n.onmessage = async (u) => {
          if (!d || !(u.data instanceof Blob)) return;
          const w = await createImageBitmap(u.data), y = g.current;
          if (!y) {
            w.close();
            return;
          }
          y.width = w.width, y.height = w.height, y.getContext("2d").drawImage(w, 0, 0), w.close();
        }, n.onclose = (u) => {
          if (d) {
            if (t.androidWs = null, u.code === 4401 || u.code === 4403 || u.code === 4426) {
              t.set({ error: "Session expired — log in again." });
              try {
                window.dispatchEvent(new Event("aw-auth-failed"));
              } catch {
              }
              return;
            }
            if (h += 1, h > 6) {
              t.set({ error: "Android stream lost — press Reconnect." });
              return;
            }
            a = setTimeout(x, Math.min(1e3 * h, 5e3));
          }
        });
      };
      return x(), () => {
        d = !1, clearTimeout(a), t.androidWs = null;
        try {
          n && n.close();
        } catch {
        }
      };
    }, [v, o, l]);
    const k = (d) => {
      const n = g.current;
      if (!n || !n.width || !n.height) return null;
      const a = n.getBoundingClientRect(), h = n.width / n.height, x = a.width / a.height, u = h > x ? a.width : a.height * h, w = h > x ? a.width / h : a.height, y = (d.clientX - (a.left + (a.width - u) / 2)) / u, B = (d.clientY - (a.top + (a.height - w) / 2)) / w;
      return y < 0 || y > 1 || B < 0 || B > 1 ? null : { nx: y, ny: B };
    }, s = (d) => {
      const n = t.androidWs;
      (n == null ? void 0 : n.readyState) === WebSocket.OPEN && n.send(JSON.stringify(d));
    }, f = 0.02, m = W(null), E = (d) => {
      const n = k(d);
      m.current = n ? { ...n, t: Date.now() } : null;
    }, T = (d) => {
      const n = m.current;
      m.current = null;
      const a = k(d);
      if (!n || !a) return;
      Math.hypot(a.nx - n.nx, a.ny - n.ny) < f ? s({ type: "tap", nx: a.nx, ny: a.ny }) : s({
        type: "swipe",
        nx1: n.nx,
        ny1: n.ny,
        nx2: a.nx,
        ny2: a.ny,
        // Match the real gesture duration: a flick and a slow drag scroll
        // very differently on Android.
        duration_ms: Math.min(Math.max(Date.now() - n.t, 50), 2e3)
      });
    };
    return /* @__PURE__ */ e.h("div", { className: "flex flex-col h-full bg-black" }, /* @__PURE__ */ e.h("div", { className: "flex-1 relative" }, i ? /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300" }, i) : r.length ? v ? /* @__PURE__ */ e.h(
      "canvas",
      {
        ref: g,
        onPointerDown: E,
        onPointerUp: T,
        onPointerLeave: () => {
          m.current = null;
        },
        className: "absolute inset-0 w-full h-full object-contain touch-none"
      }
    ) : /* @__PURE__ */ e.h(
      "iframe",
      {
        ref: p,
        key: l,
        src: c,
        onLoad: C,
        className: "absolute inset-0 w-full h-full border-0",
        title: "Remote Screen"
      }
    ) : /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]" }, /* @__PURE__ */ e.h("span", null, "No hosts yet."), /* @__PURE__ */ e.h("button", { onClick: A, className: "text-[var(--color-accent)] hover:underline" }, "Add one in Settings"))), v && r.length > 0 && /* @__PURE__ */ e.h("div", { className: `shrink-0 flex items-center justify-center gap-10 py-2.5
                          bg-[var(--color-bg-header)] border-t border-[var(--color-border)]` }, /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_BACK"), className: M, title: "Back" }, /* @__PURE__ */ e.h(
      "svg",
      {
        className: _,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "2",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      },
      /* @__PURE__ */ e.h("polyline", { points: "15 18 9 12 15 6" })
    )), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_HOME"), className: M, title: "Home" }, /* @__PURE__ */ e.h("svg", { className: _, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("circle", { cx: "12", cy: "12", r: "8" }))), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_APP_SWITCH"), className: M, title: "Recents" }, /* @__PURE__ */ e.h("svg", { className: _, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "5", y: "5", width: "14", height: "14", rx: "1.5" })))));
  }
  e.registerWindow(O, L), e.registerWindowActions(O, D);
}
export {
  j as register
};
