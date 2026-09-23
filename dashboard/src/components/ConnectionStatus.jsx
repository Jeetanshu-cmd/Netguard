import styles from './ConnectionStatus.module.css'

const STATUS_TEXT = {
  connecting: 'Connecting…',
  open: 'Live',
  reconnecting: 'Reconnecting…',
  closed: 'Disconnected',
}

const STATUS_CLASS = {
  connecting: styles.pending,
  open: styles.live,
  reconnecting: styles.pending,
  closed: styles.down,
}

export function ConnectionStatus({ status }) {
  return (
    <span className={`${styles.pill} ${STATUS_CLASS[status] ?? styles.down}`} role="status" aria-live="polite">
      <span className={styles.dot} aria-hidden="true" />
      {STATUS_TEXT[status] ?? 'Unknown'}
    </span>
  )
}
