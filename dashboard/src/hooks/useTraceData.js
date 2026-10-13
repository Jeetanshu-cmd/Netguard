// Chooses the flow that the "One packet, traced." section replays.
//
// Real flows come from the shared live store (WebSocket + /flows). The WS
// payload carries only label + confidence (AGENTS.md §4), so the probabilities
// of the non-winning classes are NOT real model output: they are the leftover
// probability mass split for display, and TraceDiagram says so.
// When there is no flow yet, a clearly labelled SIM sample is used.
import { useCallback, useMemo, useState } from 'react'
import { useLiveData } from './useLiveData.js'
import { ALERT_THRESHOLD, LABELS } from '../utils/constants.js'

const SIM_SAMPLE = {
  id: 'sim-sample',
  source: 'sim-sample',
  label: 'PortScan',
  confidence: 0.97,
  src_ip: '10.0.0.4',
  dst_ip: '10.0.0.9',
  dst_port: 22,
  flowCount: 10000,
}

const LEFTOVER_WEIGHTS = [0.5, 0.3, 0.2]

// Winner gets the reported confidence; the rest share (1 - confidence).
export function buildProbs(label, confidence) {
  const rest = Math.max(0, 1 - confidence)
  let k = 0
  return LABELS.map((l) => (l === label ? confidence : rest * LEFTOVER_WEIGHTS[k++]))
}

function toTrace(flow, source, alerts, threshold) {
  const alert = alerts.find((a) => a.src_ip === flow.src_ip && a.label === flow.label)
  return {
    id: flow.id,
    source,
    label: flow.label,
    confidence: flow.confidence,
    src_ip: flow.src_ip,
    dst_ip: flow.dst_ip,
    dst_port: flow.dst_port ?? null,
    flowCount: flow.flowCount ?? alert?.flow_count ?? 1,
    threshold,
  }
}

function finish(trace) {
  const threshold = trace.threshold ?? ALERT_THRESHOLD
  return {
    ...trace,
    threshold,
    probs: buildProbs(trace.label, trace.confidence),
    alertTriggered: trace.label !== 'Benign' && trace.confidence > threshold,
  }
}

export function useTraceData() {
  const { mode, lastAttackFlow, lastFlow, alerts, threshold } = useLiveData()
  const source = mode === 'sim' ? 'sim' : 'live'
  const flow = lastAttackFlow ?? lastFlow

  const candidate = useMemo(
    () => (flow ? toTrace(flow, source, alerts, threshold) : null),
    [flow, source, alerts, threshold],
  )

  // The replayed flow is frozen once chosen so the timeline is not rebuilt
  // under the user's finger while new flows stream in. "Use latest" re-picks.
  // (State is adjusted during render, React's pattern for derived-but-sticky state.)
  const [picked, setPicked] = useState(null)
  if (candidate && (!picked || picked.source !== candidate.source)) setPicked(candidate)
  else if (!candidate && picked && picked.source !== source) setPicked(null)

  const refresh = useCallback(() => setPicked(candidate), [candidate])

  const trace = useMemo(() => finish(picked ?? { ...SIM_SAMPLE, threshold }), [picked, threshold])
  return { trace, refresh, canRefresh: Boolean(candidate && picked && candidate.id !== picked.id) }
}
