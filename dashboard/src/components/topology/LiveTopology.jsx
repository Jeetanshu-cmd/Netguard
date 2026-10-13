// Section 3: live topology graph, activity feed and stat grid, all fed by the
// shared LiveDataContext. No value here is invented: missing data shows "—",
// and simulated data (toggle) is labelled SIM everywhere.
import { useEffect, useState } from 'react'
import { useAuth } from '../../hooks/useAuth.js'
import { useLiveData } from '../../hooks/useLiveData.js'
import { LABELS } from '../../utils/constants.js'
import { LinkStatus } from './LinkStatus.jsx'
import styles from './Topology.module.css'

const CLUSTERS = [
  { label: 'Benign', name: 'BENIGN', color: 'var(--nd-green)' },
  { label: 'DoS_DDoS', name: 'DOS_DDOS', color: 'var(--nd-red)' },
  { label: 'PortScan', name: 'PORTSCAN', color: 'var(--nd-red)' },
  { label: 'BruteForce', name: 'BRUTEFORCE', color: 'var(--nd-red)' },
]

// Two coordinate sets for the same graph: horizontal on desktop, vertical on phones.
const LAYOUTS = {
  wide: {
    box: [900, 370],
    nodes: { in: [60, 185], sensor: [190, 185], clf: [320, 185], alerts: [660, 185], out: [810, 185] },
    clusters: [[490, 50], [490, 140], [490, 230], [490, 320]],
    horizontal: true,
  },
  narrow: {
    box: [360, 600],
    nodes: { in: [180, 30], sensor: [180, 100], clf: [180, 170], alerts: [180, 470], out: [180, 550] },
    clusters: [[50, 320], [140, 320], [230, 320], [320, 320]],
    horizontal: false,
  },
}

function useIsNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 767px)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const onChange = (e) => setNarrow(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return narrow
}

function edge(a, b, horizontal) {
  const [x0, y0] = a
  const [x1, y1] = b
  return horizontal
    ? `M ${x0} ${y0} C ${(x0 + x1) / 2} ${y0}, ${(x0 + x1) / 2} ${y1}, ${x1} ${y1}`
    : `M ${x0} ${y0} C ${x0} ${(y0 + y1) / 2}, ${x1} ${(y0 + y1) / 2}, ${x1} ${y1}`
}

function Node({ at, text, w = 84 }) {
  return (
    <g transform={`translate(${at[0]} ${at[1]})`}>
      <rect x={-w / 2} y="-17" width={w} height="34" rx="7" className={styles.node} />
      <text y="4" textAnchor="middle" className={styles.nodeText}>{text}</text>
    </g>
  )
}

function Topology({ view, activeLabel }) {
  const narrow = useIsNarrow()
  const L = narrow ? LAYOUTS.narrow : LAYOUTS.wide
  const max = Math.max(1, ...LABELS.map((l) => view.counts[l]))
  const { nodes, clusters, horizontal } = L

  return (
    <svg className={styles.graph} viewBox={`0 0 ${L.box[0]} ${L.box[1]}`} role="img"
      aria-label="Topology: NIC to sensor to classifier to four class clusters to alert engine to dashboard.">
      <defs>
        <pattern id="nd-topo-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" className={styles.gridDot} />
        </pattern>
      </defs>
      <rect width={L.box[0]} height={L.box[1]} fill="url(#nd-topo-grid)" />

      <path d={edge(nodes.in, nodes.sensor, horizontal)} className={styles.edge} />
      <path d={edge(nodes.sensor, nodes.clf, horizontal)} className={styles.edge} />
      {CLUSTERS.map((c, i) => (
        <g key={c.label}>
          <path d={edge(nodes.clf, clusters[i], horizontal)} className={activeLabel === c.label ? styles.edgeHot : styles.edge} style={{ '--hot': c.color }} />
          <path d={edge(clusters[i], nodes.alerts, horizontal)} className={styles.edge} />
        </g>
      ))}
      <path d={edge(nodes.alerts, nodes.out, horizontal)} className={styles.edge} />

      <Node at={nodes.in} text="IN · NIC" />
      <Node at={nodes.sensor} text="SENSOR" />
      <Node at={nodes.clf} text="CLASSIFIER" w={96} />
      <Node at={nodes.alerts} text="ALERTS" />
      <Node at={nodes.out} text="OUT · DASH" w={96} />

      {CLUSTERS.map((c, i) => {
        const [x, y] = clusters[i]
        const count = view.counts[c.label]
        const r = 14 + 16 * Math.sqrt(count / max)
        const active = activeLabel === c.label
        return (
          <g key={c.label} transform={`translate(${x} ${y})`}>
            {active && <circle r={r + 8} className={styles.ring} style={{ stroke: c.color }} />}
            <circle r={r} className={styles.cluster} style={{ fill: c.color }} />
            <text y={r + 14} textAnchor="middle" className={styles.clusterName}>{c.name}</text>
            <text y={r + 26} textAnchor="middle" className={styles.clusterCount}>
              {view.hasData ? count.toLocaleString('en-US') : '—'}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function ago(ts) {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false })
}

function Feed({ view, isAdmin }) {
  const tag = view.mode === 'sim' ? 'SIM' : 'LIVE'
  const status = new Map(view.alerts.map((a) => [a.id, a.status]))
  // Up to 3 open alerts stay pinned on top so busy flow traffic can never push
  // an actionable alert (and its Acknowledge button) out of view.
  const pinned = view.alerts.filter((a) => a.status === 'open').slice(0, 3)
  const pinnedIds = new Set(pinned.map((a) => a.id))
  const rows = [
    ...pinned.map((a) => ({ ...a, kind: 'alert', key: `pin-${a.id}`, pinned: true })),
    ...view.feed.filter((r) => !(r.kind === 'alert' && pinnedIds.has(r.id))),
  ].slice(0, 12)
  return (
    <ol className={styles.feed} aria-label="Activity feed, newest first">
      {rows.length === 0 && <li className={styles.feedEmpty}>Waiting for flows…</li>}
      {rows.map((row, i) => {
        const style = { opacity: row.pinned ? 1 : Math.max(0.3, 1 - (i - pinned.length) * 0.07) }
        if (row.kind === 'alert') {
          const state = status.get(row.id) ?? row.status
          return (
            <li key={row.key} style={style} className={`${styles.feedRow} ${styles.feedAlert}`}>
              <span className={styles.feedText}>
                ALERT {row.label.toUpperCase()} {row.src_ip} ×{row.flow_count} {state.toUpperCase()}
              </span>
              {isAdmin && state === 'open' && (
                <AckButton id={row.id} />
              )}
              <span className={view.mode === 'sim' ? styles.tagSim : styles.tagLive}>{tag}</span>
            </li>
          )
        }
        const where = row.dst_port != null ? `:${row.dst_port}` : row.dst_ip
        return (
          <li key={row.key} style={style} className={styles.feedRow}>
            <span className={styles.feedText}>
              <span className={styles.feedTime}>{ago(row.timestamp)}</span> FLOW {row.src_ip} → {where}{' '}
              <b className={row.label === 'Benign' ? styles.okText : styles.badText}>{row.label.toUpperCase()}</b>{' '}
              {row.confidence.toFixed(2)}
            </span>
            <span className={view.mode === 'sim' ? styles.tagSim : styles.tagLive}>{tag}</span>
          </li>
        )
      })}
    </ol>
  )
}

function AckButton({ id }) {
  const { acknowledgeAlert } = useLiveData()
  const [error, setError] = useState(false)
  return (
    <button
      type="button"
      className={styles.ack}
      onClick={() => acknowledgeAlert(id).catch(() => setError(true))}
    >
      {error ? 'Retry' : 'Acknowledge'}
    </button>
  )
}

function Stat({ label, value, tone, badge, sub }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statHead}>
        <span>{label}</span>
        {badge && <span className={badge === 'SIM' ? styles.tagSim : styles.tagLive}>{badge}</span>}
      </div>
      <div className={`${styles.statValue} ${String(value).length > 10 ? styles.statValueSm : ''} ${tone ?? ''} tabular-nums`}>{value}</div>
      {sub && <div className={styles.statSub}>{sub}</div>}
    </div>
  )
}

function Stats({ view }) {
  const badge = view.mode === 'sim' ? 'SIM' : 'LIVE'
  const dash = '—'
  const n = (v) => (view.hasData && v != null ? v : dash)
  const sensorTone = { online: styles.okText, offline: styles.badText }[view.sensor.state]
  const sensorText =
    view.sensor.state === 'sim' ? 'SIM' : view.sensor.state === 'unknown' ? dash : view.sensor.state.toUpperCase()
  return (
    <div className={styles.stats}>
      <Stat label="Flows Inspected" value={n(view.total.toLocaleString('en-US'))} badge={badge} />
      <Stat label="Threats Flagged" value={n(view.threats.toLocaleString('en-US'))} badge={badge} />
      <Stat label="Open Alerts" value={view.openAlerts == null ? dash : view.openAlerts} badge={badge} />
      <Stat label="Avg Confidence" value={view.avgConfidence == null ? dash : view.avgConfidence.toFixed(2)} badge={badge} sub="last 200 flows" />
      <Stat label="Flows/sec" value={n(view.flowsPerSec.toFixed(1))} badge={badge} sub="10 s window" />
      <Stat
        label="Sensor Status"
        value={sensorText}
        tone={sensorTone}
        badge={badge}
        sub={view.sensor.source === 'derived' ? 'from last flow' : undefined}
      />
      <Stat label="Model" value={view.model ?? dash} badge={view.model ? 'LIVE' : undefined} />
      <Stat label="Threshold" value={Number(view.threshold).toFixed(2)} />
    </div>
  )
}

export function LiveTopology() {
  const view = useLiveData()
  const { role } = useAuth()
  const isAdmin = String(role ?? '').toLowerCase() === 'admin'

  // The cluster that just received a flow gets the rotating ring for ~1.2 s.
  const [activeLabel, setActiveLabel] = useState(null)
  const lastId = view.lastFlow?.id
  const lastLabel = view.lastFlow?.label
  useEffect(() => {
    if (!lastId) return undefined
    setActiveLabel(lastLabel)
    const id = setTimeout(() => setActiveLabel(null), 1200)
    return () => clearTimeout(id)
  }, [lastId, lastLabel])

  return (
    <section className={styles.section} aria-labelledby="topo-heading">
      <header className={styles.head}>
        <div>
          <h2 id="topo-heading" className={styles.h2}>Live topology</h2>
          <p className={styles.sub}>Every classified flow, as it moves through the pipeline.</p>
        </div>
        <div className={styles.controls}>
          <LinkStatus status={view.socketStatus} />
          <button
            type="button"
            role="switch"
            aria-checked={view.simulate}
            className={view.simulate ? styles.toggleOn : styles.toggle}
            onClick={() => view.setSimulate(!view.simulate)}
          >
            <span className={styles.toggleKnob} />
            Show simulated data
          </button>
        </div>
      </header>

      {view.mode === 'sim' && (
        <p className={styles.simBanner} role="note">
          SIM · Simulated flows generated in this browser. Nothing below is real network traffic.
        </p>
      )}
      {view.mode === 'live' && view.socketStatus === 'reconnecting' && (
        <p className={styles.warnBanner} role="status">Reconnecting to /ws/flows… values may be stale until the link is back.</p>
      )}
      {view.apiError && view.mode === 'live' && (
        <p className={styles.warnBanner} role="status">API unreachable: {view.apiError}</p>
      )}

      <div className={styles.body}>
        <div className={styles.graphWrap}>
          <Topology view={view} activeLabel={activeLabel} />
        </div>
        <div className={styles.side}>
          <h3 className={styles.h3}>Activity</h3>
          <Feed view={view} isAdmin={isAdmin} />
        </div>
      </div>

      <Stats view={view} />
    </section>
  )
}
