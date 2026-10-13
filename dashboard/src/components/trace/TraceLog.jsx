import styles from './Trace.module.css'

const TONE = { info: styles.toneInfo, ok: styles.toneOk, bad: styles.toneBad, muted: styles.toneMuted }

const SOURCE_LABEL = { live: 'LIVE FLOW', sim: 'SIM', 'sim-sample': 'SIM SAMPLE' }

export function TraceLog({ lines, count, trace }) {
  return (
    <aside className={styles.log} aria-label="Trace log">
      <div className={styles.logHead}>
        <span>TRACE · {String(trace.id).slice(0, 18).toUpperCase()}</span>
        <span className={trace.source === 'live' ? styles.tagLive : styles.tagSim}>
          {SOURCE_LABEL[trace.source]}
        </span>
      </div>
      <ol className={styles.logRows}>
        {lines.slice(0, count).map((line, i) => (
          <li key={i} className={styles.logRow}>
            <span className={styles.logTime}>{line.t}</span>
            <span className={TONE[line.tone]}>{line.text}</span>
          </li>
        ))}
        <li className={styles.cursor} aria-hidden="true" />
      </ol>
      <p className={styles.logNote}>
        T+ clock is illustrative stage order, not measured latency. Bars for non-winning classes show
        the remaining probability split for display; only the TOP label and its confidence come from
        the model.
      </p>
    </aside>
  )
}
