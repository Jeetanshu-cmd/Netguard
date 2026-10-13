// Presentational SVG for the packet trace. It renders the final layout only;
// traceTimeline.js animates it via the data-* hooks below. Elements whose text
// is written by GSAP (data-num) intentionally have no React children.
import { memo } from 'react'
import styles from './Trace.module.css'
import {
  BAR_W, CARD_W, CARD_XS, CELL, CELL_GAP, CELL_X0, CLASS_NAMES, COLORS, CX, GATES, GATE_W, GATE_X0,
  H, W, Y, fanPath, mergePath,
} from './traceLayout.js'
import { LABELS } from '../../utils/constants.js'

function verdictOf(trace) {
  if (trace.alertTriggered) {
    return {
      color: COLORS.red,
      gate: 'GATE OPEN · ALERT',
      out: `ALERT OPEN · ${trace.label} · ${trace.src_ip} · ${trace.confidence.toFixed(2)}`,
      engine: ' flows → 1 alert',
    }
  }
  if (trace.label === 'Benign') {
    return { color: COLORS.green, gate: 'BENIGN · logged', out: 'ALLOWED · LOGGED', engine: ' flows · no alert raised' }
  }
  return {
    color: COLORS.amber,
    gate: `BELOW ${trace.threshold} · logged`,
    out: `LOGGED · ${trace.label} ${trace.confidence.toFixed(2)} ≤ ${trace.threshold}`,
    engine: ' flows · no alert raised',
  }
}

function TraceDiagramBase({ trace }) {
  const winner = Math.max(0, LABELS.indexOf(trace.label))
  const v = verdictOf(trace)
  const dst = trace.dst_port != null ? `${trace.dst_ip}:${trace.dst_port}` : trace.dst_ip
  const pillText =
    trace.source === 'sim-sample'
      ? 'SNIFF eth0 · tcp 10.0.0.4:51234 → 10.0.0.9:22'
      : `SNIFF · ${trace.src_ip} → ${dst}`
  const gateX = GATE_X0 + trace.threshold * GATE_W

  return (
    <svg
      className={styles.svg}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={`Trace of one flow from ${trace.src_ip} classified ${trace.label} with confidence ${trace.confidence.toFixed(2)}${trace.alertTriggered ? ', raising an alert' : ', logged without an alert'}.`}
    >
      <defs>
        <pattern id="nd-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" className={styles.gridDot} />
        </pattern>
      </defs>
      <rect width={W} height={H} fill="url(#nd-grid)" />

      {/* spine: faint dashed base + blue progress overlays */}
      <line x1={CX} y1={Y.pillBottom} x2={CX} y2={Y.inferBottom} className={styles.spine} />
      <line x1={CX} y1={Y.mergeEnd} x2={CX} y2={Y.outTop} className={styles.spine} />
      <line data-t="progA" x1={CX} y1={Y.pillBottom} x2={CX} y2={Y.pillBottom} className={styles.prog} />
      <line data-t="progB" x1={CX} y1={Y.mergeEnd} x2={CX} y2={Y.mergeEnd} className={styles.prog} />

      {/* 01 packet */}
      <g data-g="pill">
        <rect x="90" y={Y.pillTop} width="340" height="32" rx="8" className={styles.pillBox} />
        <text x={CX} y={Y.pillTop + 20} textAnchor="middle" className={styles.pillText}>{pillText}</text>
      </g>

      {/* 02 flow table */}
      <g data-g="table">
        <text x={GATE_X0} y="98" className={styles.lbl}>FLOW TABLE</text>
        <line x1={GATE_X0} y1={Y.table} x2={GATE_X0 + GATE_W} y2={Y.table} className={styles.bar} />
        {GATES.map((g) => (
          <g key={g.label}>
            <rect data-gate x={g.x - 5} y={Y.table - 5} width="10" height="10" />
            <text x={g.x} y={Y.table + 24} textAnchor="middle" className={styles.lbl}>{g.label}</text>
          </g>
        ))}
      </g>

      {/* 03 features */}
      <g data-g="features">
        <text x={CX} y={Y.featLabel} textAnchor="middle" className={styles.lbl}>19 FEATURES</text>
        {Array.from({ length: 19 }, (_, i) => {
          const row = i < 10 ? 0 : 1
          const col = row === 0 ? i : i - 10
          const x = CELL_X0 + col * (CELL + CELL_GAP) + (row === 1 ? (CELL + CELL_GAP) / 2 : 0)
          const y = row === 0 ? Y.featRow1 : Y.featRow2
          return <rect key={i} data-cell x={x} y={y} width={CELL} height={CELL - 6} rx="3" />
        })}
      </g>

      {/* 04 inference */}
      <g data-g="infer">
        <rect x="146" y={Y.inferTop} width="228" height="24" rx="6" className={styles.pillBox} />
        <text x={CX} y={Y.inferTop + 16} textAnchor="middle" className={styles.lbl}>RANDOM FOREST · predict_proba</text>
        {CLASS_NAMES.map((n, i) => (
          <path key={n} data-fan d={fanPath(i)} pathLength="1" strokeDasharray="1" className={styles.fan} />
        ))}
      </g>

      {/* 05 classes */}
      <g data-g="classes">
        {CLASS_NAMES.map((name, i) => {
          const x = CARD_XS[i]
          return (
            <g key={name} data-card>
              <rect x={x} y={Y.cardTop} width={CARD_W} height={Y.cardBottom - Y.cardTop} rx="8" className={styles.card} />
              <text x={x + 10} y={Y.cardTop + 22} className={styles.cardName}>{name}</text>
              <rect x={x + 8} y={Y.cardTop + 50} width={BAR_W} height="5" rx="2.5" className={styles.barTrack} />
              <rect data-bar x={x + 8} y={Y.cardTop + 50} width="0" height="5" rx="2.5" className={styles.barFill} />
              <text data-num={`p${i}`} x={x + 10} y={Y.cardTop + 80} className={styles.cardNum} />
              {i === winner && (
                <g data-t="top">
                  <rect x={x + CARD_W - 40} y={Y.cardTop + 8} width="32" height="14" rx="3" className={styles.topBadge} />
                  <text x={x + CARD_W - 24} y={Y.cardTop + 18} textAnchor="middle" className={styles.topText}>TOP</text>
                </g>
              )}
            </g>
          )
        })}
      </g>
      {CLASS_NAMES.map((n, i) => (
        <path key={n} data-merge d={mergePath(i)} pathLength="1" strokeDasharray="1" className={styles.merge} />
      ))}

      {/* 06 confidence gate */}
      <g data-g="gate">
        <text x={GATE_X0} y="470" className={styles.lbl}>CONFIDENCE GATE</text>
        <text x={GATE_X0 + GATE_W} y="470" textAnchor="end" className={styles.lbl}>
          <tspan>CONF </tspan>
          <tspan data-num="conf" className={styles.strong} />
        </text>
        <rect x={GATE_X0} y="480" width={GATE_W} height="8" rx="4" className={styles.barTrack} />
        <rect data-t="confFill" x={GATE_X0} y="480" width="0" height="8" rx="4" />
        <line x1={gateX} y1="474" x2={gateX} y2="494" className={styles.marker} />
        <text x={gateX} y="508" textAnchor="middle" className={styles.lbl}>{trace.threshold}</text>
        <text x={GATE_X0} y="508" className={styles.lbl} fill={v.color}>{v.gate}</text>
      </g>

      {/* 07 alert engine */}
      <g data-g="alert">
        <rect data-t="alertBox" x="90" y={Y.alertTop} width="340" height={Y.alertBottom - Y.alertTop} rx="8" className={styles.card} />
        <text x={CX} y={Y.alertTop + 22} textAnchor="middle" className={styles.lbl}>(src_ip, label) · 30s WINDOW</text>
        <text data-num="count" x={CX - 4} y={Y.alertTop + 54} textAnchor="end" className={styles.counter} />
        <text x={CX} y={Y.alertTop + 54} className={styles.lbl}>{v.engine}</text>
      </g>

      {/* 08 dashboard */}
      <g data-g="out">
        <rect data-t="outBox" x="80" y={Y.outTop} width="360" height={Y.outBottom - Y.outTop} rx="18" className={styles.outBox} />
        <text data-t="outText" x={CX} y={Y.outTop + 22} textAnchor="middle" className={styles.pillText}>{v.out}</text>
        <text x={CX} y={Y.outBottom + 22} textAnchor="middle" className={styles.lbl}>WEBSOCKET PUSH</text>
      </g>

      <g data-t="dot" transform={`translate(${CX} ${Y.pillBottom})`}>
        <circle data-t="halo" r="11" opacity="0.35" />
        <circle r="3.5" fill="#fff" />
      </g>
    </svg>
  )
}

export const TraceDiagram = memo(TraceDiagramBase)
