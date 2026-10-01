// Mock WebSocket that mimics the native browser WebSocket surface
// (readyState, onopen/onmessage/onclose/onerror, send/close) closely enough
// that useFlowSocket.js can use it without branching on mock-vs-real.
//
// TODO(backend): delete this file once /ws/flows is live; remove the
// USE_MOCKS branch in services/socket.js at the same time.
import { makeMockFlow, makeMockAlert, shouldAlert } from './mockData'

const OPEN = 1
const CLOSED = 3

export class MockFlowSocket {
  constructor(url) {
    this.url = url
    this.readyState = 0 // CONNECTING
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null

    this._flowTimer = null
    this._alertTimer = null

    // Simulate connection handshake latency.
    this._openTimer = setTimeout(() => {
      if (this._closed) return
      this.readyState = OPEN
      this.onopen?.(new Event('open'))
      this._startEmitting()
    }, 250)
  }

  _startEmitting() {
    this._flowTimer = setInterval(() => {
      const flow = makeMockFlow()
      this._emit({ type: 'flow', ...flow })

      // Follow an attack flow with an alert event, per the alert rule
      // (README §3 / AGENTS.md §5.3): non-Benign AND confidence > 0.85.
      if (shouldAlert(flow) && Math.random() < 0.5) {
        const alert = makeMockAlert(flow)
        this._emit({ type: 'alert', ...alert })
      }
    }, 900)
  }

  _emit(payload) {
    if (this.readyState !== OPEN) return
    this.onmessage?.({ data: JSON.stringify(payload) })
  }

  send() {
    // No-op: the real /ws/flows endpoint is server-push only.
  }

  close() {
    this._closed = true
    clearTimeout(this._openTimer)
    clearInterval(this._flowTimer)
    clearInterval(this._alertTimer)
    this.readyState = CLOSED
    this.onclose?.(new CloseEvent('close', { code: 1000, wasClean: true }))
  }
}
