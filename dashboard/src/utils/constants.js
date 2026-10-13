// Shared constants for labels, alert thresholds, and API config.
// Mirrors AGENTS.md §2 (labels) and §5 (alert threshold).

export const LABELS = ['Benign', 'DoS_DDoS', 'PortScan', 'BruteForce']

export const LABEL_COLORS = {
  Benign: '#0070f3',
  DoS_DDoS: '#ee0000',
  PortScan: '#ab570a',
  BruteForce: '#7928ca',
}

export const ALERT_THRESHOLD = 0.85

// Mocks are opt-in (VITE_USE_MOCKS=true); the default talks to the real API.
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

// Same-origin by default so the dashboard works from any device that can open
// it (no hardcoded localhost). Dev: Vite proxies /api and /ws to the FastAPI
// server. Prod: FastAPI serves dist/ itself, so REST paths are root-relative.
// Override with VITE_API_BASE_URL / VITE_WS_BASE_URL to point elsewhere.
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? '/api' : '')

export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ?? `${wsProtocol}//${window.location.host}`

export const TOKEN_STORAGE_KEY = 'netguard.jwt'
