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

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000'

export const TOKEN_STORAGE_KEY = 'netguard.jwt'
