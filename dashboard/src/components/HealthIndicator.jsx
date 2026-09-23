// Polls /health and /capture/status on an interval and renders a compact
// status pill. Uses derived boolean state (isHealthy/isSensorOnline) rather
// than exposing raw timestamps to consumers, keeping re-renders minimal
// (rerender-derived-state).
import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import styles from './HealthIndicator.module.css'

const POLL_INTERVAL_MS = 15000

export function HealthIndicator() {
  const [apiHealthy, setApiHealthy] = useState(null) // null = unknown yet
  const [sensorOnline, setSensorOnline] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const health = await api.getHealth()
        if (!cancelled) setApiHealthy(health.status === 'healthy' && health.model_loaded)
      } catch {
        if (!cancelled) setApiHealthy(false)
      }

      try {
        const capture = await api.getCaptureStatus()
        if (!cancelled) setSensorOnline(Boolean(capture.sensor_online))
      } catch {
        if (!cancelled) setSensorOnline(false)
      }
    }

    poll()
    const interval = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <div className={styles.wrapper} role="status" aria-live="polite">
      <StatusPill label="API" ok={apiHealthy} />
      <StatusPill label="Sensor" ok={sensorOnline} />
    </div>
  )
}

function StatusPill({ label, ok }) {
  const stateClass = ok === null ? styles.unknown : ok ? styles.ok : styles.down
  const stateText = ok === null ? 'checking…' : ok ? 'online' : 'offline'

  return (
    <span className={`${styles.pill} ${stateClass}`}>
      <span className={styles.dot} aria-hidden="true" />
      {label}: {stateText}
    </span>
  )
}
