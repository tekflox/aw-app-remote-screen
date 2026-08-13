const W = "remote-screen.main";
function A(e) {
  const { useState: S, useEffect: v, useCallback: R, useRef: y, useSyncExternalStore: B } = e.React, k = e.app;
  async function N(n, o, a) {
    const c = { method: n }, l = await k.fetch(o, c);
    if (!l.ok) {
      let u = "";
      try {
        u = (await l.json()).detail || "";
      } catch {
        u = await l.text();
      }
      throw new Error(`${l.status}: ${u}`);
    }
    return l.json();
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
    subscribe(n) {
      return t.listeners.add(n), () => t.listeners.delete(n);
    },
    get() {
      return t.state;
    },
    set(n) {
      t.state = { ...t.state, ...n }, t.listeners.forEach((o) => o());
    },
    async load() {
      return t.loading || (t.loading = (async () => {
        try {
          const [{ hosts: n }, o] = await Promise.all([
            N("GET", "/hosts"),
            N("GET", "/settings")
          ]);
          t.set({ hosts: n || [], settings: o, error: null }), !t.state.selectedId && (n != null && n.length) && t.select(n[0].id);
        } catch (n) {
          t.set({ error: n.message });
        } finally {
          t.loading = null;
        }
      })()), t.loading;
    },
    select(n) {
      t.set({ selectedId: n }), t.connect(n);
    },
    // Android's three system buttons. They are not part of the mirrored
    // framebuffer — screencap captures the app surface, while Back/Home/
    // Recents are the OS navigation bar, so without these the device is
    // effectively view-only past the first screen. `adb shell input keyevent`
    // is the same channel taps already use.
    sendKey(n) {
      const o = t.androidWs;
      (o == null ? void 0 : o.readyState) === WebSocket.OPEN && o.send(JSON.stringify({ type: "key", code: n }));
    },
    async connect(n) {
      const o = t.state.hosts.find((a) => a.id === n);
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
          const a = await N("GET", `/hosts/${n}/credentials`);
          t.creds = a, t.set({
            src: K(n, a.password, t.state.settings),
            srcKey: t.state.srcKey + 1,
            error: null
          });
        } catch (a) {
          t.set({ error: a.message });
        }
      }
    }
  };
  function E() {
    return B(t.subscribe, t.get);
  }
  function K(n, o, a) {
    const c = new URL(k.wsUrl(`/ws/bridge/${n}`)), l = new URLSearchParams({
      host: c.hostname,
      port: c.port || (c.protocol === "wss:" ? "443" : "80"),
      path: c.pathname.replace(/^\//, "") + c.search,
      // noVNC wants no leading slash
      encrypt: c.protocol === "wss:" ? "1" : "0",
      autoconnect: "true",
      reconnect: "true",
      resize: (a == null ? void 0 : a.default_scaling) || "scale",
      view_only: a != null && a.view_only ? "1" : "0"
    });
    return o && l.set("password", o), `/novnc/vnc.html?${l.toString()}`;
  }
  function _({ className: n }) {
    return /* @__PURE__ */ e.h(
      "svg",
      {
        className: n || "w-3.5 h-3.5 shrink-0 text-[var(--color-text-muted)]",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "2",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      },
      /* @__PURE__ */ e.h("rect", { x: "2", y: "4", width: "20", height: "13", rx: "2" }),
      /* @__PURE__ */ e.h("path", { d: "M8 21h8M12 17v4" })
    );
  }
  const M = () => {
    var n;
    return (n = window.__awOpenAppWindow) == null ? void 0 : n.call(window, "remote-screen.hosts");
  };
  function $() {
    return /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var n;
          return (n = window.__awOpenAppWindow) == null ? void 0 : n.call(window, W);
        },
        className: "w-full text-left px-3 py-2 hover:bg-white/5 transition-colors flex items-center gap-2"
      },
      /* @__PURE__ */ e.h(_, null),
      /* @__PURE__ */ e.h("span", { className: "text-xs text-[var(--color-text-primary)]" }, "Remote Screen")
    );
  }
  function I() {
    const { hosts: n, selectedId: o } = E(), [a, c] = S(!1), [l, u] = S(null), x = y(null), p = n.find((r) => r.id === o), b = (p == null ? void 0 : p.protocol) === "android";
    v(() => {
      t.load();
    }, []);
    const C = R(() => {
      c((r) => {
        var d;
        if (r) return !1;
        const i = (d = x.current) == null ? void 0 : d.getBoundingClientRect();
        return i && u({ top: i.bottom + 6, left: i.left }), !0;
      });
    }, []);
    v(() => {
      if (!a) return;
      const r = (i) => i.key === "Escape" && c(!1);
      return window.addEventListener("keydown", r), () => window.removeEventListener("keydown", r);
    }, [a]);
    const h = "p-1.5 rounded hover:bg-white/10 transition-colors", s = "w-4 h-4 text-[var(--color-text-muted)]";
    return /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h(
      "button",
      {
        ref: x,
        onClick: C,
        className: "flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors",
        title: "Switch host"
      },
      /* @__PURE__ */ e.h("span", { className: "truncate" }, p ? p.name : "No hosts"),
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
      /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h("div", { className: "fixed inset-0 z-[9998]", onClick: () => c(!1) }), /* @__PURE__ */ e.h(
        "div",
        {
          className: "fixed w-72 max-h-80 overflow-y-auto bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-2xl shadow-black/60 z-[9999]",
          style: { top: (l == null ? void 0 : l.top) ?? 0, left: (l == null ? void 0 : l.left) ?? 0 }
        },
        n.map((r) => /* @__PURE__ */ e.h(
          "button",
          {
            key: r.id,
            onClick: () => {
              t.select(r.id), c(!1);
            },
            className: `w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${r.id === o ? "bg-[var(--color-accent)]/10" : ""}`
          },
          /* @__PURE__ */ e.h("div", { className: "text-xs font-medium text-[var(--color-text-primary)] truncate" }, r.name),
          /* @__PURE__ */ e.h("div", { className: "text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono" }, r.protocol === "android" ? `android · ${r.device_serial || "default device"}` : `${r.host}:${r.port}`, r.supported ? "" : " · not connectable")
        )),
        /* @__PURE__ */ e.h(
          "button",
          {
            onClick: () => {
              c(!1), M();
            },
            className: "w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5"
          },
          /* @__PURE__ */ e.h("svg", { className: "w-3 h-3 shrink-0", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M12 5v14M5 12h14" })),
          "Manage hosts"
        )
      )),
      document.body
    ), /* @__PURE__ */ e.h("button", { onClick: () => o && t.connect(o), className: h, title: "Reconnect" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M21 12a9 9 0 1 1-3-6.7" }), /* @__PURE__ */ e.h("path", { d: "M21 3v6h-6" }))), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var r, i, d, f;
          return (f = (d = (i = (r = t.iframe) == null ? void 0 : r.contentWindow) == null ? void 0 : i.UI) == null ? void 0 : d.toggleVirtualKeyboard) == null ? void 0 : f.call(d);
        },
        className: h,
        title: "Toggle keyboard"
      },
      /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "2", y: "6", width: "20", height: "12", rx: "2" }), /* @__PURE__ */ e.h("path", { d: "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" }))
    ), b && /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h("span", { className: "w-px h-4 bg-[var(--color-border)] mx-0.5" }), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_BACK"), className: h, title: "Back" }, /* @__PURE__ */ e.h(
      "svg",
      {
        className: s,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "2",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      },
      /* @__PURE__ */ e.h("polyline", { points: "15 18 9 12 15 6" })
    )), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_HOME"), className: h, title: "Home" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("circle", { cx: "12", cy: "12", r: "8" }))), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_APP_SWITCH"), className: h, title: "Recents" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "5", y: "5", width: "14", height: "14", rx: "1.5" }))), /* @__PURE__ */ e.h("span", { className: "w-px h-4 bg-[var(--color-border)] mx-0.5" })), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          const { src: r } = t.get();
          r && r !== "android" && window.open(r, `remote-screen-${o}`, "popup=1,width=1280,height=800");
        },
        disabled: !o,
        className: `${h} disabled:opacity-30`,
        title: "Pop out"
      },
      /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" }), /* @__PURE__ */ e.h("polyline", { points: "15 3 21 3 21 9" }), /* @__PURE__ */ e.h("line", { x1: "10", y1: "14", x2: "21", y2: "3" }))
    ));
  }
  function O() {
    const { hosts: n, selectedId: o, src: a, srcKey: c, error: l } = E(), u = y(null), x = y(null), p = n.find((s) => s.id === o), b = (p == null ? void 0 : p.protocol) === "android";
    v(() => {
      t.load();
    }, []), v(() => {
      t.iframe = u.current;
    }, [c]);
    const C = R(() => {
      var f;
      const s = (f = u.current) == null ? void 0 : f.contentWindow, r = t.creds;
      if (t.iframe = u.current, !s || !r) return;
      let i = 0;
      const d = () => {
        var w;
        const m = (w = s.UI) == null ? void 0 : w.rfb;
        if (!m) {
          ++i < 40 && setTimeout(d, 100);
          return;
        }
        m.addEventListener("credentialsrequired", () => {
          m.sendCredentials({ username: r.username || "", password: r.password || "" });
        });
      };
      d();
    }, []);
    v(() => {
      if (!b || !o) return;
      let s = !0, r = null, i = null, d = 0;
      const f = () => {
        s && (r = new WebSocket(k.wsUrl(`/ws/android/${o}`)), r.binaryType = "blob", t.androidWs = r, r.onopen = () => {
          d = 0, t.set({ error: null });
        }, r.onmessage = async (m) => {
          if (!s || !(m.data instanceof Blob)) return;
          const w = await createImageBitmap(m.data), g = x.current;
          if (!g) {
            w.close();
            return;
          }
          g.width = w.width, g.height = w.height, g.getContext("2d").drawImage(w, 0, 0), w.close();
        }, r.onclose = () => {
          if (s) {
            if (t.androidWs = null, d += 1, d > 6) {
              t.set({ error: "Android stream lost — press Reconnect." });
              return;
            }
            i = setTimeout(f, Math.min(1e3 * d, 5e3));
          }
        });
      };
      return f(), () => {
        s = !1, clearTimeout(i), t.androidWs = null;
        try {
          r && r.close();
        } catch {
        }
      };
    }, [b, o, c]);
    const h = (s) => {
      var m;
      const r = x.current;
      if (!r) return;
      const i = r.getBoundingClientRect(), d = Math.round((s.clientX - i.left) * (r.width / i.width)), f = Math.round((s.clientY - i.top) * (r.height / i.height));
      ((m = t.androidWs) == null ? void 0 : m.readyState) === WebSocket.OPEN && t.androidWs.send(JSON.stringify({ type: "tap", x: d, y: f }));
    };
    return /* @__PURE__ */ e.h("div", { className: "flex flex-col h-full bg-black" }, /* @__PURE__ */ e.h("div", { className: "flex-1 relative" }, l ? /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300" }, l) : n.length ? b ? /* @__PURE__ */ e.h(
      "canvas",
      {
        ref: x,
        onClick: h,
        className: "absolute inset-0 w-full h-full object-contain"
      }
    ) : /* @__PURE__ */ e.h(
      "iframe",
      {
        ref: u,
        key: c,
        src: a,
        onLoad: C,
        className: "absolute inset-0 w-full h-full border-0",
        title: "Remote Screen"
      }
    ) : /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]" }, /* @__PURE__ */ e.h("span", null, "No hosts yet."), /* @__PURE__ */ e.h("button", { onClick: M, className: "text-[var(--color-accent)] hover:underline" }, "Add one in Settings"))));
  }
  e.registerSlot("core.nav.workspace", $), e.registerWindow(W, O), e.registerWindowActions(W, I);
}
export {
  A as register
};
