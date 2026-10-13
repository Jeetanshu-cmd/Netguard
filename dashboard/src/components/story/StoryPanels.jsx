// Section 2: sticky 3-panel story with a progress bar, "02 / 03" counter and
// a particle field that converges as the panels advance.
import { useCallback, useRef, useState } from 'react'
import { useScrollProgress } from '../../hooks/useScrollProgress.js'
import { useLiveData } from '../../hooks/useLiveData.js'
import { ParticleField } from '../topology/ParticleField.jsx'
import styles from './StoryPanels.module.css'

const PANELS = [
  { title: 'One packet at a time.', body: 'Every flow starts as raw packet headers on a real network interface. No payloads are stored.' },
  { title: 'Or the whole network.', body: 'The sensor keeps a flow table for every conversation it can see and streams them to the API as they expire.' },
  { title: 'Classified in seconds.', body: 'A Random Forest labels each flow Benign, DoS_DDoS, PortScan or BruteForce, and the result reaches this dashboard over WebSocket.' },
]

export function StoryPanels() {
  const { mode, hasData, total, flowsPerSec } = useLiveData()
  const trackRef = useRef(null)
  const barRef = useRef(null)
  const [index, setIndex] = useState(0)
  const lastIndex = useRef(0)

  const onProgress = useCallback((p) => {
    if (barRef.current) barRef.current.style.transform = `scaleX(${p})`
    const i = Math.min(PANELS.length - 1, Math.floor(p * PANELS.length))
    if (i !== lastIndex.current) {
      lastIndex.current = i
      setIndex(i)
    }
  }, [])

  const { progress, reduced } = useScrollProgress(trackRef, { onProgress })
  const badge = mode === 'sim' ? 'SIM' : 'LIVE'
  const num = (v) => (hasData ? v : '—')

  return (
    <section ref={trackRef} className={reduced ? styles.trackStatic : styles.track} aria-label="How it works">
      <div className={reduced ? styles.stageStatic : styles.stage}>
        <ParticleField progressRef={progress} className={styles.canvas} />
        <div className={styles.bar} aria-hidden="true">
          <div ref={barRef} className={styles.barFill} style={{ transform: `scaleX(${reduced ? 1 : 0})` }} />
        </div>
        <p className={styles.counter} aria-hidden="true">
          {String(index + 1).padStart(2, '0')} / {String(PANELS.length).padStart(2, '0')}
        </p>

        <div className={styles.panels}>
          {PANELS.map((panel, i) => (
            <article
              key={panel.title}
              className={i === index || reduced ? styles.panelOn : styles.panel}
              aria-hidden={!reduced && i !== index}
            >
              <h2 className={styles.title}>{panel.title}</h2>
              <p className={styles.body}>{panel.body}</p>
              {i === 1 && (
                <dl className={styles.numbers}>
                  <div>
                    <dt>REAL FLOWS <span className={mode === 'sim' ? styles.sim : styles.live}>{badge}</span></dt>
                    <dd className="tabular-nums">{num(total.toLocaleString('en-US'))}</dd>
                  </div>
                  <div>
                    <dt>FLOWS/SEC <span className={mode === 'sim' ? styles.sim : styles.live}>{badge}</span></dt>
                    <dd className="tabular-nums">{num(flowsPerSec.toFixed(1))}</dd>
                  </div>
                </dl>
              )}
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
