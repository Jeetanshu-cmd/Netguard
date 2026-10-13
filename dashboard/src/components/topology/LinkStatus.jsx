import styles from './Topology.module.css'

const TEXT = {
  open: 'LIVE',
  connecting: 'CONNECTING…',
  reconnecting: 'RECONNECTING…',
  closed: 'DISCONNECTED',
}
const TONE = { open: styles.linkOk, connecting: styles.linkWarn, reconnecting: styles.linkWarn, closed: styles.linkBad }

// WebSocket link state, mirroring useFlowSocket's status values.
export function LinkStatus({ status }) {
  return (
    <span className={`${styles.link} ${TONE[status] ?? styles.linkBad}`} role="status" aria-live="polite">
      <span className={styles.linkDot} aria-hidden="true" />
      {TEXT[status] ?? 'UNKNOWN'}
    </span>
  )
}
