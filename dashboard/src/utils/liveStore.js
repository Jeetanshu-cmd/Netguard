// Pure accumulators behind LiveDataContext. One "slice" per data source
// (live API/WebSocket vs. simulated) so simulated numbers can never leak into
// real ones. The context ingests into refs and publishes snapshot() at a low
// rate, so a flow burst does not re-render React per event.
import { LABELS } from './constants.js'

const MAX_FLOWS = 200
const MAX_FEED = 40
const RATE_WINDOW_MS = 10000

function zeroCounts() {
  return Object.fromEntries(LABELS.map((l) => [l, 0]))
}

export function createSlice() {
  return {
    base: { total: 0, counts: zeroCounts() }, // last REST /stats result
    delta: { total: 0, counts: zeroCounts() }, // flows seen over WS since base
    flows: [], // newest first, capped
    arrivals: [], // Date.now() of each flow seen over WS, for flows/sec
    alerts: new Map(), // id -> alert
    alertsLoaded: false,
    feed: [],
    lastFlowAt: null, // unix seconds of the newest flow
    dirty: true,
  }
}

function pushFeed(slice, item) {
  slice.feed.unshift(item)
  if (slice.feed.length > MAX_FEED) slice.feed.length = MAX_FEED
}

// WS "flow" events and REST /flows rows (ts) are both normalised to `timestamp`.
export function normaliseFlow(raw) {
  return { ...raw, timestamp: raw.timestamp ?? raw.ts }
}

export function ingestFlow(slice, raw, now = Date.now()) {
  const flow = normaliseFlow(raw)
  slice.flows.unshift(flow)
  if (slice.flows.length > MAX_FLOWS) slice.flows.length = MAX_FLOWS
  slice.arrivals.push(now)
  slice.delta.total += 1
  if (flow.label in slice.delta.counts) slice.delta.counts[flow.label] += 1
  slice.lastFlowAt = Math.max(slice.lastFlowAt ?? 0, flow.timestamp ?? now / 1000)
  pushFeed(slice, { kind: 'flow', key: `f-${flow.id}`, ...flow })
  slice.dirty = true
}

export function ingestAlert(slice, raw) {
  const alert = {
    id: raw.id,
    src_ip: raw.src_ip,
    label: raw.label,
    max_confidence: raw.max_confidence ?? raw.confidence,
    flow_count: raw.flow_count ?? 1,
    status: raw.status ?? 'open',
    first_seen: raw.first_seen ?? raw.timestamp,
    last_seen: raw.last_seen ?? raw.timestamp,
  }
  const existing = slice.alerts.get(alert.id)
  slice.alerts.set(alert.id, { ...existing, ...alert, first_seen: existing?.first_seen ?? alert.first_seen })
  pushFeed(slice, { kind: 'alert', key: `a-${alert.id}-${alert.flow_count}`, ...alert, timestamp: alert.last_seen })
  slice.dirty = true
}

// REST history: seeds the table/averages without touching live counters.
export function seedFlows(slice, rows) {
  const flows = rows.map(normaliseFlow)
  slice.flows = [...slice.flows, ...flows.filter((f) => !slice.flows.some((s) => s.id === f.id))]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, MAX_FLOWS)
  // Recent history fills an empty activity feed so it isn't blank on first load.
  if (slice.feed.length === 0) {
    slice.feed = flows.slice(0, MAX_FEED).map((f) => ({ kind: 'flow', key: `f-${f.id}`, ...f }))
  }
  if (flows.length) slice.lastFlowAt = Math.max(slice.lastFlowAt ?? 0, ...flows.map((f) => f.timestamp ?? 0))
  slice.dirty = true
}

export function seedAlerts(slice, rows) {
  for (const row of rows) slice.alerts.set(row.id, { ...slice.alerts.get(row.id), ...row })
  slice.alertsLoaded = true
  slice.dirty = true
}

// A new /stats result replaces the baseline and restarts the WS delta, so
// flows are never double counted.
export function applyStats(slice, stats) {
  const counts = zeroCounts()
  const src = stats.counts ?? stats.by_label ?? {}
  for (const label of LABELS) counts[label] = Number(src[label] ?? stats[label] ?? 0)
  slice.base = { total: Number(stats.total ?? LABELS.reduce((n, l) => n + counts[l], 0)), counts }
  slice.delta = { total: 0, counts: zeroCounts() }
  slice.dirty = true
}

export function snapshot(slice, now = Date.now()) {
  const counts = {}
  for (const l of LABELS) counts[l] = slice.base.counts[l] + slice.delta.counts[l]
  const total = slice.base.total + slice.delta.total
  const threats = total - counts.Benign

  const cutoff = now - RATE_WINDOW_MS
  while (slice.arrivals.length && slice.arrivals[0] < cutoff) slice.arrivals.shift()
  const flowsPerSec = slice.arrivals.length / (RATE_WINDOW_MS / 1000)

  const confs = slice.flows.map((f) => f.confidence).filter((c) => typeof c === 'number')
  const alerts = [...slice.alerts.values()].sort((a, b) => (b.last_seen ?? 0) - (a.last_seen ?? 0))
  const lastAttack = slice.flows.find((f) => f.label !== 'Benign' && f.confidence > 0.85)

  return {
    hasData: total > 0 || slice.flows.length > 0,
    total,
    threats,
    counts,
    flowsPerSec,
    avgConfidence: confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null,
    openAlerts: slice.alertsLoaded ? alerts.filter((a) => a.status === 'open').length : null,
    alerts,
    feed: slice.feed.slice(0, 12),
    flows: slice.flows,
    lastFlow: slice.flows[0] ?? null,
    lastAttackFlow: lastAttack ?? null,
    lastFlowAt: slice.lastFlowAt,
  }
}
