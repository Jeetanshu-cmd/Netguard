import styles from './LabelBadge.module.css'

const LABEL_CLASS = {
  Benign: styles.benign,
  DoS_DDoS: styles.dosDdos,
  PortScan: styles.portScan,
  BruteForce: styles.bruteForce,
}

export function LabelBadge({ label }) {
  const className = LABEL_CLASS[label] ?? styles.unknown
  return <span className={`${styles.badge} ${className}`}>{label}</span>
}
