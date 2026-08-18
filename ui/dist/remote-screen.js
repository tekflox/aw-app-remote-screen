const O = "remote-screen.main";
function j(e) {
  const { useState: $, useEffect: N, useCallback: _, useRef: W, useSyncExternalStore: P } = e.React, E = e.app;
  async function S(r, o, a) {
    const l = { method: r }, i = await E.fetch(o, l);
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
  const t = {
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
            S("GET", "/hosts"),
            S("GET", "/settings")
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
      const o = t.state.hosts.find((a) => a.id === r);
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
          const a = await S("GET", `/hosts/${r}/credentials`);
          t.creds = a, t.set({
            src: U(r, a.password, t.state.settings),
            srcKey: t.state.srcKey + 1,
            error: null
          });
        } catch (a) {
          t.set({ error: a.message });
        }
      }
    }
  };
  function I() {
    return P(t.subscribe, t.get);
  }
  function U(r, o, a) {
    const l = new URL(E.wsUrl(`/ws/bridge/${r}`)), i = new URLSearchParams({
      host: l.hostname,
      port: l.port || (l.protocol === "wss:" ? "443" : "80"),
      path: l.pathname.replace(/^\//, "") + l.search,
      // noVNC wants no leading slash
      encrypt: l.protocol === "wss:" ? "1" : "0",
      autoconnect: "true",
      reconnect: "true",
      resize: (a == null ? void 0 : a.default_scaling) || "scale",
      view_only: a != null && a.view_only ? "1" : "0"
    });
    return o && i.set("password", o), `/novnc/vnc.html?${i.toString()}`;
  }
  const A = () => {
    var r;
    return (r = window.__awOpenAppWindow) == null ? void 0 : r.call(window, "remote-screen.hosts");
  }, M = "p-2 rounded-lg hover:bg-white/10 active:bg-white/20 transition-colors", B = "w-8 h-8 text-[var(--color-text-primary)]";
  function D() {
    const { hosts: r, selectedId: o } = I(), [a, l] = $(!1), [i, p] = $(null), b = W(null), g = r.find((s) => s.id === o);
    N(() => {
      t.load();
    }, []);
    const v = _(() => {
      l((s) => {
        var h;
        if (s) return !1;
        const u = (h = b.current) == null ? void 0 : h.getBoundingClientRect();
        return u && p({ top: u.bottom + 6, left: u.left }), !0;
      });
    }, []);
    N(() => {
      if (!a) return;
      const s = (u) => u.key === "Escape" && l(!1);
      return window.addEventListener("keydown", s), () => window.removeEventListener("keydown", s);
    }, [a]);
    const C = "p-1.5 rounded hover:bg-white/10 transition-colors", k = "w-4 h-4 text-[var(--color-text-muted)]";
    return /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h(
      "button",
      {
        ref: b,
        onClick: v,
        className: "flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors",
        title: "Switch host"
      },
      /* @__PURE__ */ e.h("span", { className: "truncate" }, g ? g.name : "No hosts"),
      /* @__PURE__ */ e.h(
        "svg",
        {
          className: `w-3 h-3 shrink-0 text-[var(--color-text-muted)] transition-transform ${a ? "rotate-180" : ""}`,
          viewBox: "0 0 24 24",
          fill: "none",
          stroke: "currentColor",
          strokeWidth: "2"
        },
        /* @__PURE__ */ e.h("path", { d: "M6 9l6 6 6-6" })
      )
    ), a && e.ReactDOM.createPortal(
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
          var s, u, h, R;
          return (R = (h = (u = (s = t.iframe) == null ? void 0 : s.contentWindow) == null ? void 0 : u.UI) == null ? void 0 : h.toggleVirtualKeyboard) == null ? void 0 : R.call(h);
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
          const { src: s } = t.get(), u = s === "android" ? E.absoluteApiUrl(`/panel/viewer/${o}`) : s;
          u && window.open(u, `remote-screen-${o}`, "popup=1,width=1280,height=800");
        },
        disabled: !o,
        className: `${C} disabled:opacity-30`,
        title: "Pop out"
      },
      /* @__PURE__ */ e.h("svg", { className: k, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" }), /* @__PURE__ */ e.h("polyline", { points: "15 3 21 3 21 9" }), /* @__PURE__ */ e.h("line", { x1: "10", y1: "14", x2: "21", y2: "3" }))
    ));
  }
  function L() {
    const { hosts: r, selectedId: o, src: a, srcKey: l, error: i } = I(), p = W(null), b = W(null), g = r.find((d) => d.id === o), v = (g == null ? void 0 : g.protocol) === "android";
    N(() => {
      t.load();
    }, []), N(() => {
      t.iframe = p.current;
    }, [l]);
    const C = _(() => {
      var x;
      const d = (x = p.current) == null ? void 0 : x.contentWindow, n = t.creds;
      if (t.iframe = p.current, !d || !n || !n.password && !n.username) return;
      let c = 0;
      const f = () => {
        var m;
        const w = (m = d.UI) == null ? void 0 : m.rfb;
        if (!w) {
          ++c < 40 && setTimeout(f, 100);
          return;
        }
        w.addEventListener("credentialsrequired", () => {
          w.sendCredentials({ username: n.username || "", password: n.password || "" });
        });
      };
      f();
    }, []);
    N(() => {
      if (!v || !o) return;
      let d = !0, n = null, c = null, f = 0;
      const x = () => {
        d && (n = new WebSocket(E.wsUrl(`/ws/android/${o}`)), n.binaryType = "blob", t.androidWs = n, n.onopen = () => {
          f = 0, t.set({ error: null });
        }, n.onmessage = async (w) => {
          if (!d || !(w.data instanceof Blob)) return;
          const m = await createImageBitmap(w.data), y = b.current;
          if (!y) {
            m.close();
            return;
          }
          y.width = m.width, y.height = m.height, y.getContext("2d").drawImage(m, 0, 0), m.close();
        }, n.onclose = () => {
          if (d) {
            if (t.androidWs = null, f += 1, f > 6) {
              t.set({ error: "Android stream lost — press Reconnect." });
              return;
            }
            c = setTimeout(x, Math.min(1e3 * f, 5e3));
          }
        });
      };
      return x(), () => {
        d = !1, clearTimeout(c), t.androidWs = null;
        try {
          n && n.close();
        } catch {
        }
      };
    }, [v, o, l]);
    const k = (d) => {
      const n = b.current;
      if (!n || !n.width || !n.height) return null;
      const c = n.getBoundingClientRect(), f = n.width / n.height, x = c.width / c.height, w = f > x ? c.width : c.height * f, m = f > x ? c.width / f : c.height, y = (d.clientX - (c.left + (c.width - w) / 2)) / w, K = (d.clientY - (c.top + (c.height - m) / 2)) / m;
      return y < 0 || y > 1 || K < 0 || K > 1 ? null : { nx: y, ny: K };
    }, s = (d) => {
      const n = t.androidWs;
      (n == null ? void 0 : n.readyState) === WebSocket.OPEN && n.send(JSON.stringify(d));
    }, u = 0.02, h = W(null), R = (d) => {
      const n = k(d);
      h.current = n ? { ...n, t: Date.now() } : null;
    }, T = (d) => {
      const n = h.current;
      h.current = null;
      const c = k(d);
      if (!n || !c) return;
      Math.hypot(c.nx - n.nx, c.ny - n.ny) < u ? s({ type: "tap", nx: c.nx, ny: c.ny }) : s({
        type: "swipe",
        nx1: n.nx,
        ny1: n.ny,
        nx2: c.nx,
        ny2: c.ny,
        // Match the real gesture duration: a flick and a slow drag scroll
        // very differently on Android.
        duration_ms: Math.min(Math.max(Date.now() - n.t, 50), 2e3)
      });
    };
    return /* @__PURE__ */ e.h("div", { className: "flex flex-col h-full bg-black" }, /* @__PURE__ */ e.h("div", { className: "flex-1 relative" }, i ? /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300" }, i) : r.length ? v ? /* @__PURE__ */ e.h(
      "canvas",
      {
        ref: b,
        onPointerDown: R,
        onPointerUp: T,
        onPointerLeave: () => {
          h.current = null;
        },
        className: "absolute inset-0 w-full h-full object-contain touch-none"
      }
    ) : /* @__PURE__ */ e.h(
      "iframe",
      {
        ref: p,
        key: l,
        src: a,
        onLoad: C,
        className: "absolute inset-0 w-full h-full border-0",
        title: "Remote Screen"
      }
    ) : /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]" }, /* @__PURE__ */ e.h("span", null, "No hosts yet."), /* @__PURE__ */ e.h("button", { onClick: A, className: "text-[var(--color-accent)] hover:underline" }, "Add one in Settings"))), v && r.length > 0 && /* @__PURE__ */ e.h("div", { className: `shrink-0 flex items-center justify-center gap-10 py-2.5
                          bg-[var(--color-bg-header)] border-t border-[var(--color-border)]` }, /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_BACK"), className: M, title: "Back" }, /* @__PURE__ */ e.h(
      "svg",
      {
        className: B,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "2",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      },
      /* @__PURE__ */ e.h("polyline", { points: "15 18 9 12 15 6" })
    )), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_HOME"), className: M, title: "Home" }, /* @__PURE__ */ e.h("svg", { className: B, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("circle", { cx: "12", cy: "12", r: "8" }))), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_APP_SWITCH"), className: M, title: "Recents" }, /* @__PURE__ */ e.h("svg", { className: B, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "5", y: "5", width: "14", height: "14", rx: "1.5" })))));
  }
  e.registerWindow(O, L), e.registerWindowActions(O, D);
}
export {
  j as register
};
