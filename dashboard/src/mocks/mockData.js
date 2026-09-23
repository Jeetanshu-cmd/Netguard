// Deterministic-ish fake data generators shared by the mock REST and mock
// WebSocket layers, so both produce data that looks like it came from the
// same backend (AGENTS.md §3 flow schema, §2 labels).
import { LABELS } from '../utils/constants'

const SRC_IPS = [
  '192.168.1.45', '192.168.1.52', '192.168.1.61', '192.168.1.77',
  '10.0.0.14', '10.0.0.23', '172.16.0.9',
]
const DST_IPS = ['192.168.1.1', '192.168.1.10', '10.0.0.1']
const FEATURE_NAMES = [
  'dst_port', 'flow_duration_s', 'fwd_packets', 'bwd_packets', 'fwd_bytes',
  'bwd_bytes', 'bytes_per_sec', 'packets_per_sec', 'pkt_len_mean',
  'pkt_len_std', 'pkt_len_max', 'pkt_len_min', 'syn_count', 'ack_count',
  'fin_count', 'rst_count', 'psh_count', 'iat_mean', 'iat_max',
]

let flowCounter = 0

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)]
}

function weightedLabel() {
  // Mostly benign, occasional attack labels — mirrors a realistic mix.
  const roll = Math.random()
  if (roll < 0.7) return 'Benign'
  if (roll < 0.85) return 'PortScan'
  if (roll < 0.95) return 'DoS_DDoS'
  return 'BruteForce'
}

function randomTopFeatures() {
  const shuffled = [...FEATURE_NAMES].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 3).map((feature) => ({
    feature,
    value: Number((Math.random() * 500).toFixed(2)),
    importance: Number((Math.random() * 0.3).toFixed(3)),
  }))
}

export function makeMockFlow() {
  flowCounter += 1
  const label = weightedLabel()
  const isAttack = label !== 'Benign'
  return {
    id: `flow-mock-${flowCounter}`,
    timestamp: Date.now() / 1000,
    src_ip: pick(SRC_IPS),
    dst_ip: pick(DST_IPS),
    dst_port: pick([22, 80, 443, 21, 3389, 8080]),
    label,
    confidence: isAttack
      ? Number((0.85 + Math.random() * 0.15).toFixed(4))
      : Number((0.6 + Math.random() * 0.4).toFixed(4)),
    top_features: randomTopFeatures(),
  }
}

// Alert engine rule (README §3 / AGENTS.md §5.3): an alert may only be
// raised for a flow that is non-Benign AND above the confidence threshold.
export const ALERT_CONFIDENCE_THRESHOLD = 0.85

export function shouldAlert(flow) {
  return flow.label !== 'Benign' && flow.confidence > ALERT_CONFIDENCE_THRESHOLD
}

export function makeMockAlert(fromFlow) {
  return {
    id: `alert-mock-${fromFlow.src_ip}-${fromFlow.label}`,
    src_ip: fromFlow.src_ip,
    label: fromFlow.label,
    max_confidence: fromFlow.confidence,
    flow_count: 1,
    first_seen: fromFlow.timestamp,
    last_seen: fromFlow.timestamp,
    status: 'open',
  }
}

// Keeps generating mock flows until one qualifies for an alert (non-Benign,
// confidence > threshold), then wraps it. Used by seedAlerts() so initial
// mock alert data never violates the alert-raising rule.
export function makeMockAlertableFlow() {
  let flow = makeMockFlow()
  let guard = 0
  while (!shouldAlert(flow) && guard < 100) {
    flow = makeMockFlow()
    guard += 1
  }
  return flow
}

export function makeMockStats(hoursBack = 6) {
  const now = Date.now()
  const points = []
  for (let i = hoursBack * 6; i >= 0; i -= 1) {
    const ts = now - i * 10 * 60 * 1000 // 10-minute buckets
    const bucket = { timestamp: ts }
    for (const label of LABELS) {
      bucket[label] = label === 'Benign'
        ? Math.floor(20 + Math.random() * 40)
        : Math.floor(Math.random() * 8)
    }
    points.push(bucket)
  }
  return points
}

export function makeMockTopSourceIps() {
  return SRC_IPS.slice(0, 5).map((ip) => ({
    src_ip: ip,
    flow_count: Math.floor(10 + Math.random() * 200),
  })).sort((a, b) => b.flow_count - a.flow_count)
}
