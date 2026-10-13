// Builds the single paused GSAP timeline that ScrollTrigger scrubs.
// Timeline time == step index: step i occupies [i, i + 1], total length 8.
// Every tween is an explicit fromTo with immediateRender:false, and initial
// states are applied with tl.set at 0, so scrubbing in either direction (or
// jumping) always lands on the right state: the whole thing is reversible.
import { gsap } from 'gsap'
import { LABELS } from '../../utils/constants.js'
import { CARD_CX, COLORS, CX, GATE_W, BAR_W, Y, bezier } from './traceLayout.js'

const DIM = 0.16

export function buildTraceTimeline(root, trace) {
  const q = (sel) => Array.from(root.querySelectorAll(sel))
  const one = (sel) => root.querySelector(sel)
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'none' } })
  const from = (target, a, b, at) => tl.fromTo(target, a, { ...b, immediateRender: false }, at)

  const winner = Math.max(0, LABELS.indexOf(trace.label))
  const verdict = trace.alertTriggered ? COLORS.red : trace.label === 'Benign' ? COLORS.green : COLORS.amber

  const groups = {
    table: q('[data-g="table"]'),
    features: q('[data-g="features"]'),
    infer: q('[data-g="infer"]'),
    classes: q('[data-g="classes"]'),
    gate: q('[data-g="gate"]'),
    alert: q('[data-g="alert"]'),
    out: q('[data-g="out"]'),
  }
  const pill = q('[data-g="pill"]')
  const dot = one('[data-t="dot"]')
  const halo = one('[data-t="halo"]')
  const progA = one('[data-t="progA"]')
  const progB = one('[data-t="progB"]')
  const gates = q('[data-gate]')
  const cells = q('[data-cell]')
  const fans = q('[data-fan]')
  const merges = q('[data-merge]')
  const cards = q('[data-card]')
  const bars = q('[data-bar]')
  const top = one('[data-t="top"]')
  const confFill = one('[data-t="confFill"]')
  const alertBox = one('[data-t="alertBox"]')
  const outBox = one('[data-t="outBox"]')
  const outText = one('[data-t="outText"]')
  const winnerMerge = merges[winner]

  // ---- initial state (time 0) ----------------------------------------------
  Object.values(groups).forEach((g) => tl.set(g, { opacity: DIM }, 0))
  tl.set(pill, { opacity: 0, y: 8 }, 0)
  tl.set(gates, { fill: COLORS.dim }, 0)
  tl.set(cells, { fill: COLORS.dim }, 0)
  tl.set([...fans, ...merges], { strokeDashoffset: 1 }, 0)
  tl.set(merges.filter((_, i) => i !== winner), { opacity: 0 }, 0)
  tl.set(bars, { attr: { width: 0 } }, 0)
  tl.set(top, { opacity: 0 }, 0)
  tl.set(confFill, { attr: { width: 0 } }, 0)
  tl.set(confFill, { fill: COLORS.accent }, 0)
  tl.set(halo, { fill: COLORS.accent }, 0)
  tl.set(progB, { stroke: COLORS.accent }, 0)
  tl.set([alertBox, outBox], { stroke: '#2a2f3a' }, 0)
  tl.set(outText, { fill: '#6b7280' }, 0)

  // ---- travelling dot --------------------------------------------------------
  const pos = { x: CX, y: Y.pillBottom }
  const place = () => {
    dot.setAttribute('transform', `translate(${pos.x} ${pos.y})`)
    progA.setAttribute('y2', Math.max(Y.pillBottom, Math.min(pos.y, Y.inferBottom)))
    progB.setAttribute('y2', Math.max(Y.mergeEnd, Math.min(pos.y, Y.outTop)))
  }
  place()
  let cur = { x: CX, y: Y.pillBottom }
  const move = (x, y, at, dur) => {
    const a = { ...cur }
    from(pos, { x: a.x, y: a.y }, { x, y, duration: dur, onUpdate: place }, at)
    cur = { x, y }
  }
  const curve = (p0, p1, p2, p3, at, dur) => {
    const o = { t: 0 }
    from(o, { t: 0 }, {
      t: 1,
      duration: dur,
      onUpdate: () => {
        const p = bezier(o.t, p0, p1, p2, p3)
        pos.x = p.x
        pos.y = p.y
        place()
      },
    }, at)
    cur = { x: p3[0], y: p3[1] }
  }

  // 01 PACKET
  from(pill, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.35 }, 0)
  move(CX, 104, 0, 1)

  // 02 FLOW TABLE: gates turn green as the dot passes
  from(groups.table, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 1)
  gates.forEach((g, i) => from(g, { fill: COLORS.dim }, { fill: COLORS.green, duration: 0.12 }, 1.3 + i * 0.2))
  move(CX, 160, 1, 1)

  // 03 FEATURES: 19 cells fill in blue
  from(groups.features, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 2)
  cells.forEach((c, i) => from(c, { fill: COLORS.dim }, { fill: COLORS.accent, duration: 0.1 }, 2.15 + i * 0.04))
  move(CX, 252, 2, 1)

  // 04 INFERENCE: line fans out to the four class cards
  from(groups.infer, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 3)
  move(CX, Y.inferBottom, 3, 0.3)
  fans.forEach((f, i) => from(f, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.55 }, 3.35 + i * 0.03))
  from(groups.classes, { opacity: DIM }, { opacity: 0.5, duration: 0.2 }, 3.6)

  // 05 CLASSES: bars animate to predict_proba, winner gets TOP, others fade
  from(groups.classes, { opacity: 0.5 }, { opacity: 1, duration: 0.15 }, 4)
  curve(
    [CX, Y.inferBottom], [CX, Y.inferBottom + 26], [CARD_CX[winner], Y.cardTop - 26], [CARD_CX[winner], Y.cardTop],
    4, 0.35,
  )
  move(CARD_CX[winner], Y.cardBottom, 4.35, 0.5)
  bars.forEach((b, i) => from(b, { attr: { width: 0 } }, { attr: { width: trace.probs[i] * BAR_W }, duration: 0.55 }, 4.2))
  q('[data-num^="p"]').forEach((el) => {
    const i = Number(el.dataset.num.slice(1))
    el.textContent = '0.00'
    const o = { v: 0 }
    from(o, { v: 0 }, { v: trace.probs[i], duration: 0.55, onUpdate: () => { el.textContent = o.v.toFixed(2) } }, 4.2)
  })
  from(top, { opacity: 0 }, { opacity: 1, duration: 0.12 }, 4.78)
  cards.forEach((c, i) => {
    if (i !== winner) from(c, { opacity: 1 }, { opacity: DIM, duration: 0.15 }, 4.85)
  })
  fans.forEach((f, i) => {
    if (i !== winner) from(f, { opacity: 1 }, { opacity: 0.1, duration: 0.15 }, 4.85)
  })

  // 06 CONFIDENCE: path converges on the 0.85 gate, then turns red / green
  from(winnerMerge, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.4 }, 5)
  curve(
    [CARD_CX[winner], Y.cardBottom], [CARD_CX[winner], Y.cardBottom + 24], [CX, Y.mergeEnd - 22], [CX, Y.mergeEnd],
    5, 0.4,
  )
  from(groups.gate, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 5.35)
  move(CX, Y.gate, 5.4, 0.2)
  from(confFill, { attr: { width: 0 } }, { attr: { width: trace.confidence * GATE_W }, duration: 0.4 }, 5.45)
  const confEl = one('[data-num="conf"]')
  confEl.textContent = '0.00'
  const co = { v: 0 }
  from(co, { v: 0 }, { v: trace.confidence, duration: 0.4, onUpdate: () => { confEl.textContent = co.v.toFixed(2) } }, 5.45)
  from(halo, { fill: COLORS.accent }, { fill: verdict, duration: 0.15 }, 5.8)
  from(progB, { stroke: COLORS.accent }, { stroke: verdict, duration: 0.15 }, 5.8)
  from(winnerMerge, { stroke: COLORS.accent }, { stroke: verdict, duration: 0.15 }, 5.8)
  from(confFill, { fill: COLORS.accent }, { fill: verdict, duration: 0.15 }, 5.8)

  // 07 ALERT ENGINE: counter ticks up
  from(groups.alert, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 6)
  move(CX, 572, 6, 1)
  from(alertBox, { stroke: '#2a2f3a' }, { stroke: verdict, duration: 0.2 }, 6.1)
  const countEl = one('[data-num="count"]')
  countEl.textContent = '0'
  const ko = { v: 0 }
  const target = trace.alertTriggered ? trace.flowCount : 0
  from(ko, { v: 0 }, { v: target, duration: 0.7, onUpdate: () => { countEl.textContent = Math.round(ko.v).toLocaleString('en-US') } }, 6.2)

  // 08 DASHBOARD: verdict pill lights up
  from(groups.out, { opacity: DIM }, { opacity: 1, duration: 0.15 }, 7)
  move(CX, Y.outTop, 7, 1)
  from(outBox, { stroke: '#2a2f3a' }, { stroke: verdict, duration: 0.2 }, 7.3)
  from(outText, { fill: '#6b7280' }, { fill: verdict, duration: 0.2 }, 7.3)

  tl.set({}, {}, 8) // pin total duration to exactly 8 (one unit per step)
  return tl
}
