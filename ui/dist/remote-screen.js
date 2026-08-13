const N = "remote-screen.main";
function O(e) {
  const { useState: C, useEffect: x, useCallback: W, useRef: b, useSyncExternalStore: M } = e.React, g = e.app;
  async function y(r, o, a) {
    const c = { method: r }, l = await g.fetch(o, c);
    if (!l.ok) {
      let f = "";
      try {
        f = (await l.json()).detail || "";
      } catch {
        f = await l.text();
      }
      throw new Error(`${l.status}: ${f}`);
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
            y("GET", "/hosts"),
            y("GET", "/settings")
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
          const a = await y("GET", `/hosts/${r}/credentials`);
          t.creds = a, t.set({
            src: B(r, a.password, t.state.settings),
            srcKey: t.state.srcKey + 1,
            error: null
          });
        } catch (a) {
          t.set({ error: a.message });
        }
      }
    }
  };
  function S() {
    return M(t.subscribe, t.get);
  }
  function B(r, o, a) {
    const c = new URL(g.wsUrl(`/ws/bridge/${r}`)), l = new URLSearchParams({
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
  function K({ className: r }) {
    return /* @__PURE__ */ e.h(
      "svg",
      {
        className: r || "w-3.5 h-3.5 shrink-0 text-[var(--color-text-muted)]",
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
  const R = () => {
    var r;
    return (r = window.__awOpenAppWindow) == null ? void 0 : r.call(window, "remote-screen.hosts");
  };
  function $() {
    return /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var r;
          return (r = window.__awOpenAppWindow) == null ? void 0 : r.call(window, N);
        },
        className: "w-full text-left px-3 py-2 hover:bg-white/5 transition-colors flex items-center gap-2"
      },
      /* @__PURE__ */ e.h(K, null),
      /* @__PURE__ */ e.h("span", { className: "text-xs text-[var(--color-text-primary)]" }, "Remote Screen")
    );
  }
  function _() {
    const { hosts: r, selectedId: o } = S(), [a, c] = C(!1), [l, f] = C(null), w = b(null), m = r.find((n) => n.id === o), v = (m == null ? void 0 : m.protocol) === "android";
    x(() => {
      t.load();
    }, []);
    const k = W(() => {
      c((n) => {
        var d;
        if (n) return !1;
        const i = (d = w.current) == null ? void 0 : d.getBoundingClientRect();
        return i && f({ top: i.bottom + 6, left: i.left }), !0;
      });
    }, []);
    x(() => {
      if (!a) return;
      const n = (i) => i.key === "Escape" && c(!1);
      return window.addEventListener("keydown", n), () => window.removeEventListener("keydown", n);
    }, [a]);
    const p = "p-1.5 rounded hover:bg-white/10 transition-colors", s = "w-4 h-4 text-[var(--color-text-muted)]";
    return /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h(
      "button",
      {
        ref: w,
        onClick: k,
        className: "flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors",
        title: "Switch host"
      },
      /* @__PURE__ */ e.h("span", { className: "truncate" }, m ? m.name : "No hosts"),
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
        r.map((n) => /* @__PURE__ */ e.h(
          "button",
          {
            key: n.id,
            onClick: () => {
              t.select(n.id), c(!1);
            },
            className: `w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${n.id === o ? "bg-[var(--color-accent)]/10" : ""}`
          },
          /* @__PURE__ */ e.h("div", { className: "text-xs font-medium text-[var(--color-text-primary)] truncate" }, n.name),
          /* @__PURE__ */ e.h("div", { className: "text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono" }, n.protocol === "android" ? `android · ${n.device_serial || "default device"}` : `${n.host}:${n.port}`, n.supported ? "" : " · not connectable")
        )),
        /* @__PURE__ */ e.h(
          "button",
          {
            onClick: () => {
              c(!1), R();
            },
            className: "w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5"
          },
          /* @__PURE__ */ e.h("svg", { className: "w-3 h-3 shrink-0", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M12 5v14M5 12h14" })),
          "Manage hosts"
        )
      )),
      document.body
    ), /* @__PURE__ */ e.h("button", { onClick: () => o && t.connect(o), className: p, title: "Reconnect" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M21 12a9 9 0 1 1-3-6.7" }), /* @__PURE__ */ e.h("path", { d: "M21 3v6h-6" }))), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var n, i, d, u;
          return (u = (d = (i = (n = t.iframe) == null ? void 0 : n.contentWindow) == null ? void 0 : i.UI) == null ? void 0 : d.toggleVirtualKeyboard) == null ? void 0 : u.call(d);
        },
        className: p,
        title: "Toggle keyboard"
      },
      /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "2", y: "6", width: "20", height: "12", rx: "2" }), /* @__PURE__ */ e.h("path", { d: "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" }))
    ), v && /* @__PURE__ */ e.h(e.React.Fragment, null, /* @__PURE__ */ e.h("span", { className: "w-px h-4 bg-[var(--color-border)] mx-0.5" }), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_BACK"), className: p, title: "Back" }, /* @__PURE__ */ e.h(
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
    )), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_HOME"), className: p, title: "Home" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("circle", { cx: "12", cy: "12", r: "8" }))), /* @__PURE__ */ e.h("button", { onClick: () => t.sendKey("KEYCODE_APP_SWITCH"), className: p, title: "Recents" }, /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "5", y: "5", width: "14", height: "14", rx: "1.5" }))), /* @__PURE__ */ e.h("span", { className: "w-px h-4 bg-[var(--color-border)] mx-0.5" })), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          const { src: n } = t.get();
          n && n !== "android" && window.open(n, `remote-screen-${o}`, "popup=1,width=1280,height=800");
        },
        disabled: !o,
        className: `${p} disabled:opacity-30`,
        title: "Pop out"
      },
      /* @__PURE__ */ e.h("svg", { className: s, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" }), /* @__PURE__ */ e.h("polyline", { points: "15 3 21 3 21 9" }), /* @__PURE__ */ e.h("line", { x1: "10", y1: "14", x2: "21", y2: "3" }))
    ));
  }
  function I() {
    const { hosts: r, selectedId: o, src: a, srcKey: c, error: l } = S(), f = b(null), w = b(null), m = r.find((s) => s.id === o), v = (m == null ? void 0 : m.protocol) === "android";
    x(() => {
      t.load();
    }, []), x(() => {
      t.iframe = f.current;
    }, [c]);
    const k = W(() => {
      var u;
      const s = (u = f.current) == null ? void 0 : u.contentWindow, n = t.creds;
      if (t.iframe = f.current, !s || !n) return;
      let i = 0;
      const d = () => {
        var E;
        const h = (E = s.UI) == null ? void 0 : E.rfb;
        if (!h) {
          ++i < 40 && setTimeout(d, 100);
          return;
        }
        h.addEventListener("credentialsrequired", () => {
          h.sendCredentials({ username: n.username || "", password: n.password || "" });
        });
      };
      d();
    }, []);
    x(() => {
      if (!v || !o) return;
      const s = new WebSocket(g.wsUrl(`/ws/android/${o}`));
      s.binaryType = "blob", t.androidWs = s;
      let n = !0;
      return s.onmessage = async (i) => {
        if (!n || !(i.data instanceof Blob)) return;
        const d = await createImageBitmap(i.data), u = w.current;
        u && (u.width = d.width, u.height = d.height, u.getContext("2d").drawImage(d, 0, 0), d.close());
      }, s.onerror = () => t.set({ error: "Android stream failed" }), () => {
        n = !1, t.androidWs = null, s.close();
      };
    }, [v, o, c]);
    const p = (s) => {
      var h;
      const n = w.current;
      if (!n) return;
      const i = n.getBoundingClientRect(), d = Math.round((s.clientX - i.left) * (n.width / i.width)), u = Math.round((s.clientY - i.top) * (n.height / i.height));
      ((h = t.androidWs) == null ? void 0 : h.readyState) === WebSocket.OPEN && t.androidWs.send(JSON.stringify({ type: "tap", x: d, y: u }));
    };
    return /* @__PURE__ */ e.h("div", { className: "flex flex-col h-full bg-black" }, /* @__PURE__ */ e.h("div", { className: "flex-1 relative" }, l ? /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300" }, l) : r.length ? v ? /* @__PURE__ */ e.h(
      "canvas",
      {
        ref: w,
        onClick: p,
        className: "absolute inset-0 w-full h-full object-contain"
      }
    ) : /* @__PURE__ */ e.h(
      "iframe",
      {
        ref: f,
        key: c,
        src: a,
        onLoad: k,
        className: "absolute inset-0 w-full h-full border-0",
        title: "Remote Screen"
      }
    ) : /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]" }, /* @__PURE__ */ e.h("span", null, "No hosts yet."), /* @__PURE__ */ e.h("button", { onClick: R, className: "text-[var(--color-accent)] hover:underline" }, "Add one in Settings"))));
  }
  e.registerSlot("core.nav.workspace", $), e.registerWindow(N, I), e.registerWindowActions(N, _);
}
export {
  O as register
};
