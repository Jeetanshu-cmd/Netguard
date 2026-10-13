// Section 1: "One packet, traced." A ~600vh track holds a sticky 100vh stage.
// Scroll progress scrubs the GSAP timeline (diagram) and drives the step
// list, caption and log. React state only changes when the step / visible
// line count changes, never per scroll frame.
import { useCallback, useMemo, useRef, useState } from 'react'
import { useScrollProgress } from '../../hooks/useScrollProgress.js'
import { useTraceData } from '../../hooks/useTraceData.js'
import { TraceDiagram } from './TraceDiagram.jsx'
import { TraceLog } from './TraceLog.jsx'
import { buildTraceTimeline } from './traceTimeline.js'
import { STEPS, buildTraceLines } from './traceSteps.js'
import styles from './Trace.module.css'

const SOURCE_BADGE = { live: 'LIVE FLOW', sim: 'SIM', 'sim-sample': 'SIM SAMPLE' }

export function PacketTrace() {
  const { trace, refresh, canRefresh } = useTraceData()
  const trackRef = useRef(null)
  const [step, setStep] = useState(0)
  const [lineCount, setLineCount] = useState(0)
  const last = useRef({ step: 0, count: 0 })
  const lines = useMemo(() => buildTraceLines(trace), [trace])

  const onProgress = useCallback(
    (p) => {
      const s = Math.min(STEPS.length - 1, Math.floor(p * STEPS.length))
      // a line appears ~35% of the way through its step; scrolling up removes it again
      const c = lines.filter((_, i) => p >= (i + 0.35) / STEPS.length).length
      if (s !== last.current.step) {
        last.current.step = s
        setStep(s)
      }
      if (c !== last.current.count) {
        last.current.count = c
        setLineCount(c)
      }
    },
    [lines],
  )

  const { reduced } = useScrollProgress(trackRef, {
    build: (root) => buildTraceTimeline(root, trace),
    deps: [trace],
    onProgress,
  })

  const current = STEPS[step]

  return (
    <section className={styles.section} aria-labelledby="trace-heading">
      <header className={styles.head}>
        <h2 id="trace-heading" className={styles.h2}>One packet, traced.</h2>
        <p className={styles.sub}>
          From raw packet to alert. Scroll to step through it.{' '}
          <span className={styles.tagSim}>{SOURCE_BADGE[trace.source]}</span>
          {canRefresh && (
            <button type="button" className={styles.linkBtn} onClick={refresh}>
              Use latest flow
            </button>
          )}
        </p>
      </header>

      <div ref={trackRef} className={reduced ? styles.trackStatic : styles.track}>
        <div className={reduced ? styles.stageStatic : styles.stage}>
          <nav className={styles.steps} aria-label="Trace steps">
            <p className={styles.stepCompact} aria-hidden="true">
              <span>{String(step + 1).padStart(2, '0')} / 08</span> {current.key}
            </p>
            <ol className={styles.stepList}>
              {STEPS.map((s, i) => (
                <li key={s.key} className={i === step ? styles.stepActive : i < step ? styles.stepDone : styles.step} aria-current={i === step ? 'step' : undefined}>
                  <span className={styles.stepNum}>{String(i + 1).padStart(2, '0')}</span>
                  <span className={styles.stepName}>{s.key}</span>
                  <span className={styles.stepDot} />
                </li>
              ))}
            </ol>
            <div className={styles.caption} aria-live="polite">
              <h3 className={styles.captionTitle}>{current.title}</h3>
              <p className={styles.captionBody}>{current.body(trace)}</p>
            </div>
          </nav>

          <div className={styles.diagram}>
            <TraceDiagram trace={trace} />
          </div>

          <TraceLog lines={lines} count={lineCount} trace={trace} />
        </div>
      </div>
    </section>
  )
}
