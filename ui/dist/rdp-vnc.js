const R = "rdp-vnc.main";
function D(e) {
  var g;
  const { useState: l, useEffect: w, useCallback: f, useRef: S } = e.React, b = e.app || ((g = e.sdk) == null ? void 0 : g.api) || {};
  async function p(o, i, n) {
    const d = { method: o }, r = await b.fetch(`/api/apps/rdp-vnc${i}`, d);
    if (!r.ok) {
      let c = "";
      try {
        c = (await r.json()).detail || "";
      } catch {
        c = await r.text();
      }
      throw new Error(`${r.status}: ${c}`);
    }
    return r.json();
  }
  function k(o, i, n) {
    const d = b.wsUrl(`/api/apps/rdp-vnc/ws/bridge/${o}`), r = new URL(d), c = new URLSearchParams({
      host: r.hostname,
      port: r.port || (r.protocol === "wss:" ? "443" : "80"),
      // noVNC wants the path WITHOUT a leading slash.
      path: r.pathname.replace(/^\//, "") + r.search,
      encrypt: r.protocol === "wss:" ? "1" : "0",
      autoconnect: "true",
      reconnect: "true",
      resize: (n == null ? void 0 : n.default_scaling) || "scale",
      view_only: n != null && n.view_only ? "1" : "0"
    });
    return i && c.set("password", i), `/novnc/vnc.html?${c.toString()}`;
  }
  function _({ className: o }) {
    return /* @__PURE__ */ e.h(
      "svg",
      {
        className: o || "w-3.5 h-3.5 shrink-0 text-[var(--color-text-muted)]",
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
  function I() {
    return /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var o;
          return (o = window.__awOpenAppWindow) == null ? void 0 : o.call(window, R);
        },
        className: "w-full text-left px-3 py-2 hover:bg-white/5 transition-colors flex items-center gap-2"
      },
      /* @__PURE__ */ e.h(_, null),
      /* @__PURE__ */ e.h("span", { className: "text-xs text-[var(--color-text-primary)]" }, "Remote Desktop")
    );
  }
  function B() {
    const [o, i] = l([]), [n, d] = l(null), [r, c] = l(""), [y, m] = l(""), [E, U] = l(0), [v, u] = l(!1), [N, h] = l(null), C = S(null), M = o.find((t) => t.id === r), j = f(async () => {
      const [{ hosts: t }, s] = await Promise.all([
        p("GET", "/hosts"),
        p("GET", "/settings")
      ]);
      return i(t || []), d(s), t || [];
    }, []);
    w(() => {
      j().then((t) => {
        !r && t.length && c(t[0].id);
      }).catch((t) => h(t.message));
    }, []);
    const $ = f(async (t) => {
      if (!t) {
        m("");
        return;
      }
      h(null);
      const s = o.find((a) => a.id === t);
      if (s && !s.supported) {
        m(""), h(`${s.name} is saved as ${s.protocol.toUpperCase()}, which has no browser client yet — only VNC can be opened from here.`);
        return;
      }
      try {
        const { password: a } = await p("GET", `/hosts/${t}/credentials`);
        m(k(t, a, n)), U((x) => x + 1);
      } catch (a) {
        h(a.message);
      }
    }, [o, n]);
    w(() => {
      r && n && $(r);
    }, [r, n]);
    const W = () => {
      var t;
      u(!1), (t = window.__awOpenAppWindow) == null || t.call(window, "rdp-vnc.hosts");
    };
    return /* @__PURE__ */ e.h("div", { className: "flex flex-col h-full bg-black" }, /* @__PURE__ */ e.h("div", { className: "flex items-center gap-1.5 px-2 py-1.5 bg-[var(--color-bg-header)] border-b border-[var(--color-border)] shrink-0" }, /* @__PURE__ */ e.h("div", { className: "relative" }, /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => u((t) => !t),
        className: "flex items-center gap-1 text-[11px] bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[var(--color-text-primary)] max-w-[200px] hover:border-[var(--color-accent)] transition-colors",
        title: "Switch host"
      },
      /* @__PURE__ */ e.h("span", { className: "truncate" }, M ? M.name : "No hosts"),
      /* @__PURE__ */ e.h(
        "svg",
        {
          className: `w-3 h-3 shrink-0 text-[var(--color-text-muted)] transition-transform ${v ? "rotate-180" : ""}`,
          viewBox: "0 0 24 24",
          fill: "none",
          stroke: "currentColor",
          strokeWidth: "2"
        },
        /* @__PURE__ */ e.h("path", { d: "M6 9l6 6 6-6" })
      )
    ), v && /* @__PURE__ */ e.h("div", { className: "absolute left-0 top-full mt-1 w-72 max-h-80 overflow-y-auto bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-2xl shadow-black/60 z-50" }, o.map((t) => /* @__PURE__ */ e.h(
      "button",
      {
        key: t.id,
        onClick: () => {
          c(t.id), u(!1);
        },
        className: `w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-[var(--color-border)] last:border-0 ${t.id === r ? "bg-[var(--color-accent)]/10" : ""}`
      },
      /* @__PURE__ */ e.h("div", { className: "text-xs font-medium text-[var(--color-text-primary)] truncate" }, t.name),
      /* @__PURE__ */ e.h("div", { className: "text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate font-mono" }, t.host, ":", t.port, t.supported ? "" : ` · ${t.protocol.toUpperCase()} (not connectable)`)
    )), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: W,
        className: "w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-white/5 flex items-center gap-1.5"
      },
      /* @__PURE__ */ e.h("svg", { className: "w-3 h-3 shrink-0", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M12 5v14M5 12h14" })),
      "Manage hosts"
    ))), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => r && $(r),
        className: "p-1.5 rounded hover:bg-white/10 transition-colors",
        title: "Reconnect"
      },
      /* @__PURE__ */ e.h("svg", { className: "w-4 h-4 text-[var(--color-text-muted)]", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M21 12a9 9 0 1 1-3-6.7" }), /* @__PURE__ */ e.h("path", { d: "M21 3v6h-6" }))
    ), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: () => {
          var t, s, a, x;
          return (x = (a = (s = (t = C.current) == null ? void 0 : t.contentWindow) == null ? void 0 : s.UI) == null ? void 0 : a.toggleVirtualKeyboard) == null ? void 0 : x.call(a);
        },
        className: "p-1.5 rounded hover:bg-white/10 transition-colors",
        title: "Toggle keyboard"
      },
      /* @__PURE__ */ e.h("svg", { className: "w-4 h-4 text-[var(--color-text-muted)]", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("rect", { x: "2", y: "6", width: "20", height: "12", rx: "2" }), /* @__PURE__ */ e.h("path", { d: "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h12" }))
    ), /* @__PURE__ */ e.h(
      "button",
      {
        onClick: async () => {
          if (!r) return;
          const { password: t } = await p("GET", `/hosts/${r}/credentials`);
          window.open(
            k(r, t, n),
            `rdp-vnc-${r}`,
            "popup=1,width=1280,height=800"
          );
        },
        disabled: !r,
        className: "p-1.5 rounded hover:bg-white/10 transition-colors disabled:opacity-30",
        title: "Pop out to new window"
      },
      /* @__PURE__ */ e.h("svg", { className: "w-4 h-4 text-[var(--color-text-muted)]", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2" }, /* @__PURE__ */ e.h("path", { d: "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" }), /* @__PURE__ */ e.h("polyline", { points: "15 3 21 3 21 9" }), /* @__PURE__ */ e.h("line", { x1: "10", y1: "14", x2: "21", y2: "3" }))
    )), /* @__PURE__ */ e.h("div", { className: "flex-1 relative" }, N ? /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-red-300" }, N) : o.length ? /* @__PURE__ */ e.h(
      "iframe",
      {
        ref: C,
        key: E,
        src: y,
        className: "absolute inset-0 w-full h-full border-0",
        title: "Remote Desktop"
      }
    ) : /* @__PURE__ */ e.h("div", { className: "absolute inset-0 flex flex-col items-center justify-center gap-2 text-xs text-[var(--color-text-muted)]" }, /* @__PURE__ */ e.h("span", null, "No hosts yet."), /* @__PURE__ */ e.h("button", { onClick: W, className: "text-[var(--color-accent)] hover:underline" }, "Add one in Settings"))), v && /* @__PURE__ */ e.h("div", { className: "fixed inset-0 z-40", onClick: () => u(!1) }));
  }
  e.registerSlot("core.nav.workspace", I), e.registerWindow(R, B);
}
export {
  D as register
};
