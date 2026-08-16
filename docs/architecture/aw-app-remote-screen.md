---
repo: architecture
path: docs/architecture/aw-app-remote-screen.md
source: generated
edited: false
checksum: sha256:2777b0be453a71caea282880652e736c4e57dac6271c418d93caf6fabd39b506
---
# Remote Screen

- **repo**: aw-app-remote-screen
- **layer**: app
- **technologies**: python, react
- **health** (derived): planned

Remote screens in the browser, three protocols behind one viewer: VNC (noVNC over a raw WebSocket->TCP byte bridge), RDP (same bridge, pending a browser-side client), and Android (live ~2 fps screen mirror + tap/swipe/text/key input over the remote-agent exec channel — no VNC server involved). Hosts live in this app's own Postgres table with per-app SQL migrations; passwords in the workspace secret store. Ports the monolith's src/api/routes/remote_desktop.py + android_viewer.py + RemoteDesktopWindow.jsx.

## Connections
- `db` → **postgres** — app-owned tables in the workspace schema
- `http` → **aw-workspace** — routes mounted at /api/apps/remote-screen

## MCP tools
_none exposed_

## Requirements
_none documented_
