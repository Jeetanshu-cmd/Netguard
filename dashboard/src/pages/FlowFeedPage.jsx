// Live Flow: classified flows stream in over /ws/flows. History is seeded from
// GET /flows so the page is not empty on arrival. Capped at MAX_ROWS so the DOM
// stays bounded; handlers use functional setState so the socket callback is
// registered once.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'
import { useFlowSocket } from '../hooks/useFlowSocket.js'
import { LabelBadge } from '../components/LabelBadge.jsx'
import { ConnectionStatus } from '../components/ConnectionStatus.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { ALERT_THRESHOLD } from '../utils/constants.js'
import styles from './FlowFeedPage.module.css'

const MAX_ROWS = 200
const RATE_WINDOW_MS = 10000

const TONE = {
  Benign: styles.toneBenign,
  DoS_DDoS: styles.toneDos,
  PortScan: styles.tonePort,
  BruteForce: styles.toneBrute,
}

function formatTime(unixSeconds) {
  if (!unixSeconds) return '—'
  return new Date(unixSeconds * 1000).toLocaleTimeString([], { hour12: false })
}

function Stat({ label, value, tone }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={`${styles.statValue} ${tone ?? ''} tabular-nums`}>{value}</span>
    </div>
  )
}

export function FlowFeedPage() {
  const { token } = useAuth()
  const [flows, setFlows] = useState([])
  const [threatsOnly, setThreatsOnly] = useState(false)
  const [rate, setRate] = useState(0)
  const arrivals = useRef([])

  // History first, so the table is useful before the first live flow lands.
  useEffect(() => {
    let cancelled = false
    api
      .getFlows({ limit: 50 })
      .then(({ flows: rows = [] }) => {
        if (cancelled) return
        const history = rows.map((f) => ({ ...f, timestamp: f.timestamp ?? f.ts }))
        setFlows((current) => {
          const ids = new Set(current.map((f) => f.id))
          return [...current, ...history.filter((f) => !ids.has(f.id))].slice(0, MAX_ROWS)
        })
      })
      .catch(() => {
        // the live stream still works without history
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleFlow = useCallback((flow) => {
    arrivals.current.push(Date.now())
    setFlows((current) => [{ ...flow, live: true }, ...current].slice(0, MAX_ROWS))
  }, [])

  const { status } = useFlowSocket(token, { onFlow: handleFlow })

  useEffect(() => {
    const id = setInterval(() => {
      const cutoff = Date.now() - RATE_WINDOW_MS
      arrivals.current = arrivals.current.filter((t) => t >= cutoff)
      setRate(arrivals.current.length / (RATE_WINDOW_MS / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const threats = useMemo(() => flows.filter((f) => f.label !== 'Benign').length, [flows])
  const alertGrade = useMemo(
    () => flows.filter((f) => f.label !== 'Benign' && f.confidence > ALERT_THRESHOLD).length,
    [flows],
  )
  const visible = threatsOnly ? flows.filter((f) => f.label !== 'Benign') : flows

  return (
    <section aria-labelledby="flow-feed-heading">
      <PageHeader
        id="flow-feed-heading"
        eyebrow="Live flow"
        title="Every flow, as it is classified."
        description={`Each row is one network conversation with the label and confidence the model gave it. Rows highlighted in red are non-Benign above ${ALERT_THRESHOLD} confidence, the level that raises an alert.`}
      >
        <ConnectionStatus status={status} />
      </PageHeader>

      <div className={styles.toolbar}>
        <div className={styles.stats}>
          <Stat label="Flows loaded" value={flows.length} />
          <Stat label="Threats" value={threats} tone={threats ? styles.bad : undefined} />
          <Stat label="Alert-grade" value={alertGrade} tone={alertGrade ? styles.bad : undefined} />
          <Stat label="Rate" value={`${rate.toFixed(1)}/s`} />
        </div>
        <div className={styles.segment} role="group" aria-label="Filter flows">
          <button type="button" aria-pressed={!threatsOnly} onClick={() => setThreatsOnly(false)}>
            All
          </button>
          <button type="button" aria-pressed={threatsOnly} onClick={() => setThreatsOnly(true)}>
            Threats only
          </button>
        </div>
      </div>

      {visible.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>
            {flows.length === 0 ? 'Waiting for flows…' : 'No threats in the loaded flows.'}
          </p>
          <p className={styles.emptyText}>
            {flows.length === 0
              ? 'Start the sensor on a network you own, or replay a CSV with python -m capture.replay.'
              : 'Everything loaded so far is Benign. Switch back to All to see it.'}
          </p>
        </div>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <caption className="visually-hidden">Live classified network flows, most recent first</caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Source</th>
                <th scope="col">Destination</th>
                <th scope="col">Label</th>
                <th scope="col">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((flow) => {
                const isThreat = flow.label !== 'Benign'
                const isAlert = isThreat && flow.confidence > ALERT_THRESHOLD
                const rowClass = [
                  styles.row,
                  isAlert ? styles.rowAlert : isThreat ? styles.rowThreat : '',
                  flow.live ? styles.rowNew : '',
                ].join(' ')
                const dest = flow.dst_port != null ? `${flow.dst_ip}:${flow.dst_port}` : flow.dst_ip
                return (
                  <tr key={flow.id} className={rowClass}>
                    <td className={`${styles.mono} tabular-nums`}>{formatTime(flow.timestamp)}</td>
                    <td className={styles.mono}>{flow.src_ip ?? '—'}</td>
                    <td className={styles.mono}>{dest ?? '—'}</td>
                    <td>
                      <LabelBadge label={flow.label} />
                    </td>
                    <td>
                      <span className={styles.conf}>
                        <span className={styles.confTrack} aria-hidden="true">
                          <span
                            className={`${styles.confFill} ${TONE[flow.label] ?? ''}`}
                            style={{ width: `${Math.round(flow.confidence * 100)}%` }}
                          />
                        </span>
                        <span className="tabular-nums">{flow.confidence.toFixed(2)}</span>
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
