# NetGuard AI — Dashboard

React 18 + Vite frontend for NetGuard AI. See the root `README.md` (§9) and `AGENTS.md` for the
full system contract.

## Stack

- React 18 + Vite
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

## Mock mode (default)

The dashboard runs standalone against an in-browser mock layer so it's demoable before `api/`
exists. Controlled by `VITE_USE_MOCKS` in `.env.local` (copy from `.env.example`):

```
VITE_USE_MOCKS=true   # default — mock REST + mock WebSocket
VITE_USE_MOCKS=false  # real backend at VITE_API_BASE_URL / VITE_WS_BASE_URL
```

- `src/mocks/mockApi.js` — fake REST responses for `/auth/login`, `/flows`, `/alerts`, `/stats`,
  `/health`, `/capture/status`.
- `src/mocks/mockSocket.js` — fake `/ws/flows` that emits a `flow` event roughly every 900ms and
  occasionally an `alert` event, mimicking the real event schema in `AGENTS.md` §4.
- `src/mocks/mockData.js` — shared fake-data generators used by both.

Any username/password signs in under mock mode (see `mockApi.login`).

## Wiring in the real backend

1. Start `api/` (FastAPI) per the root README §10.
2. Set `VITE_USE_MOCKS=false` and confirm `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` point at it
   (defaults assume `http://localhost:8000` / `ws://localhost:8000`).
3. Delete `src/mocks/` once no longer needed for demos, and remove the `USE_MOCKS` branches in
   `src/services/api.js` and `src/services/socket.js`.
4. Verify against the real contract:
   - `POST /auth/login` → `{ token, role }`
   - `GET /flows`, `GET /alerts`, `GET /stats`, `GET /health`, `GET /capture/status`
   - `PATCH /alerts/{id}`
   - `WS /ws/flows?token=<JWT>` — messages carry a `"type"` field (`"flow"` | `"alert"`)
5. `vite.config.js` has a dev proxy for `/api` → `:8000` and `/ws` → `:8000` (ws: true) if you'd
   rather same-origin everything in dev instead of hitting `VITE_API_BASE_URL` directly.

## Structure

```
src/
├── pages/        LoginPage, FlowFeedPage, AlertsPage, StatsPage
├── components/    AppShell, LabelBadge, ConnectionStatus, HealthIndicator, ProtectedRoute
├── hooks/        useAuth, useFlowSocket (WS with token param + reconnect backoff)
├── services/     api.js (REST client), socket.js (WS factory), tokenStorage.js
├── context/      AuthContext (JWT state)
├── mocks/        mock REST + mock WebSocket — delete once api/ is live
└── utils/        constants.js (labels, colors, env flags)
```

## Known gaps / TODOs

- Auth is mock-only until `/auth/login` exists; token is stored in `sessionStorage` (not
  `localStorage`) so it doesn't persist across browser restarts.
- `/flows` (history/pagination) is fetched by the mock layer but the Flow Feed page currently
  only renders the live WebSocket stream, not paginated history — add a history view if needed.
- No CSV export (`/export/flows.csv`) view yet — roadmap item per root README §15.
- Role-based UI (Admin vs Viewer) is not yet differentiated; `acknowledgeAlert` is exposed to any
  authenticated user.
