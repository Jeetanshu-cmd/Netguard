// Single source of truth for the Overview page: one /ws/flows connection plus
// REST polling (README §8), feeding both the packet trace and the topology.
//
// Two independent slices are kept: "live" (real API + WebSocket) and "sim"
// (generated in the browser, only runs while the toggle is on). The published
// `view` is exactly one of them, never a blend, and carries `mode` so every
// consumer can label simulated values.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../hooks/useAuth.js'
import { useFlowSocket } from '../hooks/useFlowSocket.js'
import { makeMockFlow } from '../mocks/mockData.js'
import {
  applyStats,
  createSlice,
  ingestAlert,
  ingestFlow,
  seedAlerts,
  seedFlows,
  snapshot,
} from '../utils/liveStore.js'
import { ALERT_THRESHOLD } from '../utils/constants.js'
import { LiveDataContext } from './liveDataContextDefinition.js'

const POLL_MS = 15000
const PUBLISH_MS = 250
const SENSOR_FRESH_S = 30
const SIM_INTERVAL_MS = 700

function resolveSensor(capture, view, mode) {
  if (mode === 'sim') return { state: 'sim', source: 'sim' }
  if (capture) {
    const online = capture.sensor_online ?? capture.online ?? capture.status === 'online'
    return { state: online ? 'online' : 'offline', source: 'api' }
  }
  // /capture/status unavailable: derive from the time of the last ingested flow.
  if (view.lastFlowAt == null) return { state: 'unknown', source: 'derived' }
  const age = Date.now() / 1000 - view.lastFlowAt
  return { state: age < SENSOR_FRESH_S ? 'online' : 'offline', source: 'derived' }
}

export function LiveDataProvider({ children }) {
  const { token } = useAuth()
  const live = useRef(createSlice())
  const sim = useRef(createSlice())
  const simAlertCounts = useRef(new Map())
  const capture = useRef({ data: null, unavailable: false })
  const meta = useRef({ model: null, threshold: ALERT_THRESHOLD, apiError: null })

  const [simulate, setSimulate] = useState(false)
  const simulateRef = useRef(false)
  const [view, setView] = useState(() => ({
    ...snapshot(createSlice()),
    mode: 'live',
    sensor: { state: 'unknown', source: 'derived' },
    model: null,
    threshold: ALERT_THRESHOLD,
    apiError: null,
  }))

  const publish = useCallback(() => {
    const mode = simulateRef.current ? 'sim' : 'live'
    const slice = mode === 'sim' ? sim.current : live.current
    const snap = snapshot(slice)
    slice.dirty = false
    setView({
      ...snap,
      mode,
      sensor: resolveSensor(capture.current.data, snap, mode),
      model: meta.current.model,
      threshold: meta.current.threshold,
      apiError: meta.current.apiError,
    })
  }, [])

  // Low-rate publisher: bursts of flows cost one render per tick, not one each.
  useEffect(() => {
    let ticks = 0
    const id = setInterval(() => {
      ticks += 1
      const slice = simulateRef.current ? sim.current : live.current
      if (slice.dirty || ticks % 4 === 0) publish()
    }, PUBLISH_MS)
    return () => clearInterval(id)
  }, [publish])

  const handleFlow = useCallback((flow) => ingestFlow(live.current, flow), [])
  const handleAlert = useCallback((alert) => ingestAlert(live.current, alert), [])
  const { status: socketStatus } = useFlowSocket(token, { onFlow: handleFlow, onAlert: handleAlert })

  // REST: initial history + 15 s poll as the fallback when the socket is down.
  useEffect(() => {
    if (!token) return undefined
    let cancelled = false

    async function pollCore() {
      const [stats, alerts] = await Promise.allSettled([
        api.getStatsSummary(),
        api.getAlerts({ limit: 100 }),
      ])
      if (cancelled) return
      if (stats.status === 'fulfilled') applyStats(live.current, stats.value)
      if (alerts.status === 'fulfilled') seedAlerts(live.current, alerts.value.alerts ?? [])
      meta.current.apiError =
        stats.status === 'rejected' && alerts.status === 'rejected' ? stats.reason.message : null
      if (!capture.current.unavailable) {
        try {
          capture.current.data = await api.getCaptureStatus()
        } catch (err) {
          // 404 = endpoint not implemented yet -> derive sensor state from last flow.
          if (err.status === 404) capture.current.unavailable = true
          capture.current.data = null
        }
      }
      live.current.dirty = true
    }

    async function loadOnce() {
      const [flows, model] = await Promise.allSettled([api.getFlows({ limit: 100 }), api.getModelInfo()])
      if (cancelled) return
      if (flows.status === 'fulfilled') seedFlows(live.current, flows.value.flows ?? [])
      if (model.status === 'fulfilled') {
        meta.current.model = model.value.model_type ?? null
        meta.current.threshold = model.value.alert_threshold ?? ALERT_THRESHOLD
      }
      live.current.dirty = true
    }

    loadOnce().then(pollCore)
    const id = setInterval(pollCore, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [token])

  // Simulated generator: only runs while the toggle is on, writes only to `sim`.
  useEffect(() => {
    simulateRef.current = simulate
    sim.current.dirty = true
    live.current.dirty = true
    publish()
    if (!simulate) return undefined
    const id = setInterval(() => {
      const flow = makeMockFlow()
      ingestFlow(sim.current, flow)
      if (flow.label !== 'Benign' && flow.confidence > ALERT_THRESHOLD) {
        const key = `${flow.src_ip}::${flow.label}`
        const count = (simAlertCounts.current.get(key) ?? 0) + 1
        simAlertCounts.current.set(key, count)
        ingestAlert(sim.current, {
          id: `sim-${key}`,
          src_ip: flow.src_ip,
          label: flow.label,
          confidence: flow.confidence,
          flow_count: count,
          status: sim.current.alerts.get(`sim-${key}`)?.status ?? 'open',
          timestamp: flow.timestamp,
        })
      }
    }, SIM_INTERVAL_MS)
    return () => clearInterval(id)
  }, [simulate, publish])

  const acknowledgeAlert = useCallback(
    async (id) => {
      const slice = simulateRef.current ? sim.current : live.current
      const previous = slice.alerts.get(id)
      if (!previous) return
      slice.alerts.set(id, { ...previous, status: 'acknowledged' })
      slice.dirty = true
      if (simulateRef.current) return
      try {
        await api.acknowledgeAlert(id, 'acknowledged')
      } catch {
        slice.alerts.set(id, previous) // revert so the UI never lies about state
        slice.dirty = true
        throw new Error('Could not acknowledge alert')
      }
    },
    [],
  )

  const value = useMemo(
    () => ({ ...view, socketStatus, simulate, setSimulate, acknowledgeAlert }),
    [view, socketStatus, simulate, acknowledgeAlert],
  )

  return <LiveDataContext.Provider value={value}>{children}</LiveDataContext.Provider>
}
