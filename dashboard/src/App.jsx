// Route-level code splitting: StatsPage pulls in Chart.js (~200KB), so it's
// lazy-loaded and out of the initial bundle that Login/FlowFeed/Alerts need
// (bundle-dynamic-imports principle, applied via React.lazy for Vite/SPA
// rather than next/dynamic).
import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell.jsx'
import { ProtectedRoute } from './components/ProtectedRoute.jsx'
import { LoginPage } from './pages/LoginPage.jsx'
import { FlowFeedPage } from './pages/FlowFeedPage.jsx'
import { AlertsPage } from './pages/AlertsPage.jsx'

const StatsPage = lazy(() => import('./pages/StatsPage.jsx').then((m) => ({ default: m.StatsPage })))

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<FlowFeedPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route
          path="stats"
          element={
            <Suspense fallback={<p>Loading stats…</p>}>
              <StatsPage />
            </Suspense>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
