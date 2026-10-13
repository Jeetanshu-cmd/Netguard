// Alerts: aggregated per source IP and label (the backend's own de-dup key,
// AGENTS.md §5 / README §8). Loads GET /alerts, then merges WS "alert" events by
// id. A WS alert's flow_count is already the running total, so it replaces the
// stored count instead of incrementing. Only Admins see Acknowledge
// (PATCH /alerts/{id}); the API enforces that too.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'
import { useFlowSocket } from '../hooks/useFlowSocket.js'
import { LabelBadge } from '../components/LabelBadge.jsx'
import { ConnectionStatus } from '../components/ConnectionStatus.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { ALERT_THRESHOLD } from '../utils/constants.js'
import styles from './AlertsPage.module.css'

const STRIPE = {
  DoS_DDoS: styles.stripeDos,
  PortScan: styles.stripePort,
  BruteForce: styles.stripeBrute,
}

const isClosed = (a) => a.status === 'acknowledged' || a.status === 'resolved'

function mergeAlert(current, incoming) {
  const next = {
    id: incoming.id,
    src_ip: incoming.src_ip,
    label: incoming.label,
    max_confidence: incoming.max_confidence ?? incoming.confidence,
    flow_count: incoming.flow_count ?? 1,
    status: incoming.status ?? 'open',
    first_seen: incoming.first_seen ?? incoming.timestamp,
    last_seen: incoming.last_seen ?? incoming.timestamp,
  }
  const i = current.findIndex((a) => a.id === next.id)
  if (i === -1) return [next, ...current]
  const prev = current[i]
  const merged = [...current]
  merged[i] = {
    ...prev,
    ...next,
    max_confidence: Math.max(prev.max_confidence ?? 0, next.max_confidence ?? 0),
    first_seen: prev.first_seen ?? next.first_seen,
  }
  return merged
}

const clock = (s) => (s ? new Date(s * 1000).toLocaleTimeString([], { hour12: false }) : '—')

function span(first, last) {
  if (!first || !last) return '—'
  const s = Math.max(0, Math.round(last - first))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

function Stat({ label, value, tone }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={`${styles.statValue} ${tone ?? ''} tabular-nums`}>{value}</span>
    </div>
  )
}

export function AlertsPage() {
  const { token, role } = useAuth()
  const isAdmin = String(role ?? '').toLowerCase() === 'admin'
  const [alerts, setAlerts] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [tab, setTab] = useState('open')

  useEffect(() => {
    let cancelled = false
    api
      .getAlerts({ limit: 100 })
      .then(({ alerts: initial = [] }) => {
        if (!cancelled) setAlerts(initial)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message ?? 'Failed to load alerts')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleAlert = useCallback((alert) => {
    setAlerts((current) => mergeAlert(current, alert))
  }, [])

  const { status } = useFlowSocket(token, { onAlert: handleAlert })

  const handleAcknowledge = useCallback(async (id) => {
    setActionError(null)
    setAlerts((current) => current.map((a) => (a.id === id ? { ...a, status: 'acknowledged' } : a)))
    try {
      await api.acknowledgeAlert(id, 'acknowledged')
    } catch (err) {
      // Revert so the UI never claims something the server refused.
      setAlerts((current) => current.map((a) => (a.id === id ? { ...a, status: 'open' } : a)))
      setActionError(err.message ?? 'Could not acknowledge the alert.')
    }
  }, [])

  const sorted = useMemo(
    () => [...alerts].sort((a, b) => (b.last_seen ?? 0) - (a.last_seen ?? 0)),
    [alerts],
  )
  const open = sorted.filter((a) => !isClosed(a))
  const closed = sorted.filter(isClosed)
  const shown = tab === 'open' ? open : tab === 'closed' ? closed : sorted
  const topConf = alerts.reduce((m, a) => Math.max(m, a.max_confidence ?? 0), 0)
  const flowsInAlerts = alerts.reduce((n, a) => n + (a.flow_count ?? 0), 0)

  return (
    <section aria-labelledby="alerts-heading">
      <PageHeader
        id="alerts-heading"
        eyebrow="Alerts"
        title="One alert per attacker."
        description={`A flow raises an alert only when it is non-Benign and above ${ALERT_THRESHOLD} confidence. Repeats from the same source IP and label inside the de-dup window update the same alert, so an attack shows up building, not as thousands of popups.`}
      >
        <ConnectionStatus status={status} />
      </PageHeader>

      <div className={styles.toolbar}>
        <div className={styles.stats}>
          <Stat label="Open" value={open.length} tone={open.length ? styles.bad : undefined} />
          <Stat label="Acknowledged" value={closed.length} />
          <Stat label="Flows covered" value={flowsInAlerts.toLocaleString('en-US')} />
          <Stat label="Top confidence" value={alerts.length ? topConf.toFixed(2) : '—'} />
        </div>
        <div className={styles.segment} role="group" aria-label="Filter alerts">
          {[
            ['open', `Open ${open.length}`],
            ['closed', `Acknowledged ${closed.length}`],
            ['all', 'All'],
          ].map(([key, text]) => (
            <button key={key} type="button" aria-pressed={tab === key} onClick={() => setTab(key)}>
              {text}
            </button>
          ))}
        </div>
      </div>

      {!isAdmin && (
        <p className={styles.note}>
          You are signed in as a viewer. Alerts are read-only; an admin can acknowledge them.
        </p>
      )}
      {loadError && <p className={styles.error} role="alert">{loadError}</p>}
      {actionError && <p className={styles.error} role="alert">{actionError}</p>}
      {isLoading && <p className={styles.note}>Loading alerts…</p>}

      {!isLoading && shown.length === 0 && !loadError && (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>{tab === 'open' ? 'All clear' : 'Nothing here'}</p>
          <p className={styles.emptyText}>
            {tab === 'open'
              ? 'No open alerts. New ones appear here the moment a flow crosses the threshold.'
              : 'No alerts match this filter yet.'}
          </p>
        </div>
      )}

      {shown.length > 0 && (
        <ul className={styles.list}>
          {shown.map((alert) => {
            const conf = alert.max_confidence ?? 0
            const closedNow = isClosed(alert)
            return (
              <li key={alert.id} className={`${styles.card} ${closedNow ? styles.cardClosed : ''}`}>
                <span className={`${styles.stripe} ${STRIPE[alert.label] ?? ''}`} aria-hidden="true" />
                <div className={styles.identity}>
                  <LabelBadge label={alert.label} />
                  <span className={styles.ip}>{alert.src_ip}</span>
                  <span className={styles.count}>
                    ×{(alert.flow_count ?? 0).toLocaleString('en-US')} flow{alert.flow_count === 1 ? '' : 's'}
                  </span>
                </div>
                <dl className={styles.meta}>
                  <div>
                    <dt>First seen</dt>
                    <dd className="tabular-nums">{clock(alert.first_seen)}</dd>
                  </div>
                  <div>
                    <dt>Last seen</dt>
                    <dd className="tabular-nums">{clock(alert.last_seen)}</dd>
                  </div>
                  <div>
                    <dt>Active for</dt>
                    <dd className="tabular-nums">{span(alert.first_seen, alert.last_seen)}</dd>
                  </div>
                </dl>
                <div className={styles.conf}>
                  <span className={styles.confValue}>{conf.toFixed(2)}</span>
                  <span className={styles.confTrack} aria-hidden="true">
                    <span className={styles.confFill} style={{ width: `${Math.round(conf * 100)}%` }} />
                  </span>
                  <span className={styles.confLabel}>max confidence</span>
                </div>
                <div className={styles.action}>
                  {closedNow ? (
                    <span className={styles.done}>Acknowledged</span>
                  ) : isAdmin ? (
                    <button type="button" className={styles.ack} onClick={() => handleAcknowledge(alert.id)}>
                      Acknowledge
                    </button>
                  ) : (
                    <span className={styles.openTag}>Open</span>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
