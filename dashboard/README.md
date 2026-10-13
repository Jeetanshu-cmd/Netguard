# NetGuard AI — Dashboard

React 18 + Vite frontend for NetGuard AI. See the root `README.md` (§9) and `AGENTS.md` for the
full system contract.

## Stack

- React 18 + Vite
- GSAP + ScrollTrigger (`@gsap/react`) for the Overview scroll sections; inline SVG + `<canvas>`
- Inter / JetBrains Mono bundled via `@fontsource` (works offline on an isolated lab network)
- react-router-dom 6 (Declarative Mode / `<BrowserRouter>`)
- Chart.js + react-chartjs-2 (lazy-loaded on the Stats route only)
- Native browser `WebSocket` (no socket.io) via `hooks/useFlowSocket.js`

## Running

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build to dist/
npm run lint      # oxlint
```

## Connecting to the backend (default)

The dashboard talks to the real API by default and uses **same-origin URLs**, so it works from any
device that can open it. There is no hardcoded `localhost`.

| Mode | How the browser reaches the API |
|---|---|
| `npm run dev` | Vite serves the UI on `:5173` (listening on all interfaces) and proxies `/api/*` and `/ws/*` to FastAPI on `:8000` (see `vite.config.js`). No CORS needed. |
| Production | `npm run build`, then run FastAPI. If `dashboard/dist` exists, `api/main.py` serves it on the same port as the API. |

```bash
# on the machine running the backend
uvicorn api.main:app --host 0.0.0.0 --port 8000      # 0.0.0.0 = reachable from other devices
cd dashboard && npm run build                          # then open http://<server-ip>:8000 on any device
# or, for development:  npm run dev  ->  http://<server-ip>:5173
```

Browser page loads (`Accept: text/html`) get `index.html`; `fetch` calls and WebSockets reach the API
untouched, so SPA routes such as `/alerts` and `/stats` do not collide with API routes of the same name.
`VITE_API_BASE_URL` / `VITE_WS_BASE_URL` override this if the API lives elsewhere.

Auth: `POST /auth/login` returns `{ access_token, token_type, role }`; the role (`admin` | `viewer`) is also
read from the JWT so it survives a reload. Admins get an **Acknowledge** button (`PATCH /alerts/{id}`);
viewers are read-only. The API enforces this regardless of the UI.

## Mock mode (opt-in)

For demoing the UI without a backend, set `VITE_USE_MOCKS=true` in `.env.local`. `src/mocks/*` then fakes
`/auth/login`, `/flows`, `/alerts`, `/stats`, `/health`, `/capture/status` and `/ws/flows`. The Overview
page's own **Show simulated data** toggle is independent of this and works against the real backend.

## Overview page (`/overview`)

Scroll-driven section built with GSAP + ScrollTrigger (lazy-loaded, so it is not in the initial bundle):

- **One packet, traced.** ~600vh track with a sticky stage. Scroll scrubs one GSAP timeline (8 steps),
  fully reversible. It replays a real recent flow when one exists, else a labelled `SIM SAMPLE`.
  Only the TOP label and its confidence are real model output; the other class bars show the remaining
  probability split for display (the WebSocket event carries no per-class probabilities).
- **3-panel story** with a canvas particle field (capped lower on mobile, paused offscreen).
- **Live topology**: graph, activity feed (open alerts pinned), stat grid.

All three read one `LiveDataProvider` (`context/LiveDataContext.jsx`): one `/ws/flows` connection plus a
15 s REST poll of `/stats` and `/alerts` as fallback. Live and simulated data are separate slices and are
never mixed; simulated values are labelled `SIM`. If `/capture/status` returns 404, sensor status is
derived from the time of the last flow. `prefers-reduced-motion` renders the static final state.

## Structure

```
src/
├── pages/        LoginPage, FlowFeedPage, AlertsPage, StatsPage
├── components/    AppShell, LabelBadge, ConnectionStatus, HealthIndicator, ProtectedRoute
├── hooks/        useAuth, useFlowSocket (WS with token param + reconnect backoff)
├── services/     api.js (REST client), socket.js (WS factory), tokenStorage.js
├── context/      AuthContext (JWT state), LiveDataContext (shared WS + REST store)
├── components/   trace/ (PacketTrace), story/, topology/ (LiveTopology, ParticleField)
├── mocks/        opt-in mock REST + mock WebSocket
└── utils/        constants.js (labels, colors, env flags)
```

## Known gaps / TODOs

- `GET /capture/status` and `GET /export/flows.csv` (README §8) are not implemented by the API yet; the
  dashboard degrades gracefully (derives sensor status) and has no CSV export view.
- `StatsPage` and `AlertsPage` still assume the old mock shapes in places (time-series `/stats`, `flow_count`
  increments); only the Overview page is written against the real `/stats` counts shape.
- The `/model-info` response has no model version field, so the stat shows the model type.
- No frontend unit tests yet (no test runner is configured in `package.json`).
