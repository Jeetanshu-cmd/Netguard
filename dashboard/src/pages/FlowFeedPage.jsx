// Live Flow Feed — appends flows pushed over /ws/flows. Capped at
// MAX_ROWS so memory/DOM size stay bounded during a long-running demo;
// older rows are dropped from the tail. Uses functional setState so the
// WebSocket message handler (registered once) never needs `flows` as a
// dependency (rerender-functional-setstate).
import { useCallback, useState } from 'react'
import { useAuth } from '../hooks/useAuth.js'
import { useFlowSocket } from '../hooks/useFlowSocket.js'
import { LabelBadge } from '../components/LabelBadge.jsx'
import { ConnectionStatus } from '../components/ConnectionStatus.jsx'
import styles from './FlowFeedPage.module.css'

const MAX_ROWS = 200

function formatTime(unixSeconds) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(unixSeconds * 1000))
}

export function FlowFeedPage() {
  const { token } = useAuth()
  const [flows, setFlows] = useState([])

  const handleFlow = useCallback((flow) => {
    setFlows((current) => [flow, ...current].slice(0, MAX_ROWS))
  }, [])

  const { status } = useFlowSocket(token, { onFlow: handleFlow })

  return (
    <section aria-labelledby="flow-feed-heading">
      <div className={styles.headerRow}>
        <h1 id="flow-feed-heading" className={styles.heading}>
          Live Flow Feed
        </h1>
        <ConnectionStatus status={status} />
      </div>

      <p className={styles.description}>
        Classified network flows stream in as they are captured. Showing the latest{' '}
        {MAX_ROWS} flows.
      </p>

      {flows.length === 0 ? (
        <div className={styles.emptyState}>Waiting for flows…</div>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <caption className="visually-hidden">
              Live classified network flows, most recent first
            </caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Source IP</th>
                <th scope="col">Destination IP</th>
                <th scope="col">Port</th>
                <th scope="col">Label</th>
                <th scope="col">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {flows.map((flow) => (
                <tr key={flow.id} className={styles.row}>
                  <td className="tabular-nums">{formatTime(flow.timestamp)}</td>
                  <td className={styles.mono}>{flow.src_ip}</td>
                  <td className={styles.mono}>{flow.dst_ip}</td>
                  <td className="tabular-nums">{flow.dst_port}</td>
                  <td>
                    <LabelBadge label={flow.label} />
                  </td>
                  <td className="tabular-nums">{(flow.confidence * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
