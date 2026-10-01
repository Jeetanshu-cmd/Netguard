// Alerts panel. Loads existing alerts via REST (/alerts) on mount, then
// keeps them live via WS "alert" messages merged in by (src_ip, label) —
// matching the backend's own de-dup key (AGENTS.md §5 / README §8).
// A dedicated useFlowSocket connection is used here so this page can be
// visited independently of the Live Feed page and still see alert pushes.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'
import { useFlowSocket } from '../hooks/useFlowSocket.js'
import { LabelBadge } from '../components/LabelBadge.jsx'
import { ConnectionStatus } from '../components/ConnectionStatus.jsx'
import styles from './AlertsPage.module.css'

function alertKey(alert) {
  return `${alert.src_ip}::${alert.label}`
}

function mergeAlert(current, incoming) {
  const key = alertKey(incoming)
  const existingIndex = current.findIndex((a) => alertKey(a) === key)

  if (existingIndex === -1) {
    return [{ ...incoming, flow_count: incoming.flow_count ?? 1 }, ...current]
  }

  const next = [...current]
  const existing = next[existingIndex]
  next[existingIndex] = {
    ...existing,
    ...incoming,
    flow_count: (existing.flow_count ?? 1) + 1,
    first_seen: existing.first_seen ?? incoming.first_seen,
    last_seen: incoming.last_seen ?? incoming.timestamp ?? existing.last_seen,
  }
  return next
}

function formatTime(unixSeconds) {
  if (!unixSeconds) return '—'
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(unixSeconds * 1000))
}

export function AlertsPage() {
  const { token } = useAuth()
  const [alerts, setAlerts] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setIsLoading(true)
      setLoadError(null)
      try {
        const { alerts: initial } = await api.getAlerts()
        if (!cancelled) setAlerts(initial)
      } catch (err) {
        if (!cancelled) setLoadError(err.message ?? 'Failed to load alerts')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const handleAlert = useCallback((alert) => {
    setAlerts((current) => mergeAlert(current, alert))
  }, [])

  const { status } = useFlowSocket(token, { onAlert: handleAlert })

  const handleAcknowledge = useCallback(async (id) => {
    setAlerts((current) => current.map((a) => (a.id === id ? { ...a, status: 'acknowledged' } : a)))
    try {
      await api.acknowledgeAlert(id, 'acknowledged')
    } catch {
      // Revert on failure so the UI doesn't lie about state.
      setAlerts((current) => current.map((a) => (a.id === id ? { ...a, status: 'open' } : a)))
    }
  }, [])

  const openAlerts = alerts.filter((a) => a.status !== 'acknowledged' && a.status !== 'resolved')
  const resolvedAlerts = alerts.filter((a) => a.status === 'acknowledged' || a.status === 'resolved')

  return (
    <section aria-labelledby="alerts-heading">
      <div className={styles.headerRow}>
        <h1 id="alerts-heading" className={styles.heading}>
          Alerts
        </h1>
        <ConnectionStatus status={status} />
      </div>

      <p className={styles.description}>
        Aggregated per source IP and label. New detections above the {(0.85 * 100).toFixed(0)}%
        confidence threshold raise or update an alert here in real time.
      </p>

      {isLoading && <p className={styles.description}>Loading alerts…</p>}

      {loadError && (
        <p className={styles.formError} role="alert">
          {loadError}
        </p>
      )}

      {!isLoading && openAlerts.length === 0 && !loadError && (
        <div className={styles.emptyState}>No active alerts. All clear.</div>
      )}

      {openAlerts.length > 0 && (
        <ul className={styles.alertList}>
          {openAlerts.map((alert) => (
            <li key={alert.id} className={styles.alertCard}>
              <div className={styles.alertMain}>
                <LabelBadge label={alert.label} />
                <span className={styles.mono}>{alert.src_ip}</span>
                <span className={styles.count}>
                  {alert.flow_count} flow{alert.flow_count === 1 ? '' : 's'}
                </span>
              </div>
              <div className={styles.alertMeta}>
                <span>First seen {formatTime(alert.first_seen)}</span>
                <span>Last seen {formatTime(alert.last_seen)}</span>
                <span className="tabular-nums">
                  Max confidence {(alert.max_confidence * 100).toFixed(1)}%
                </span>
              </div>
              <button
                type="button"
                className={styles.ackButton}
                onClick={() => handleAcknowledge(alert.id)}
              >
                Acknowledge
              </button>
            </li>
          ))}
        </ul>
      )}

      {resolvedAlerts.length > 0 && (
        <details className={styles.resolvedGroup}>
          <summary>Acknowledged ({resolvedAlerts.length})</summary>
          <ul className={styles.alertList}>
            {resolvedAlerts.map((alert) => (
              <li key={alert.id} className={`${styles.alertCard} ${styles.alertCardMuted}`}>
                <div className={styles.alertMain}>
                  <LabelBadge label={alert.label} />
                  <span className={styles.mono}>{alert.src_ip}</span>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
