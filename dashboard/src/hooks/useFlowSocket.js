// useFlowSocket — connects to /ws/flows (native WebSocket, token as query
// param per README §8 / AGENTS.md amendment), routes incoming messages by
// their "type" field ("flow" | "alert"), and reconnects with exponential
// backoff + jitter when the connection drops.
//
// Reconnect attempt count is transient and doesn't need to re-render the
// consumer on every retry, so it's kept in a ref (rerender-use-ref-transient-values).
// The onFlow/onAlert callbacks are captured in refs and read from inside the
// effect so identity changes on the caller's side don't force a
// reconnect (mirrors the intent of advanced-use-latest / effect-event refs,
// without relying on React 19's useEffectEvent since this app targets React 18).
import { useEffect, useRef, useState } from 'react'
import { createFlowSocket } from '../services/socket'

const MAX_BACKOFF_MS = 15000
const BASE_BACKOFF_MS = 500

export function useFlowSocket(token, { onFlow, onAlert } = {}) {
  const [status, setStatus] = useState(() => (token ? 'connecting' : 'closed'))

  const onFlowRef = useRef(onFlow)
  const onAlertRef = useRef(onAlert)

  useEffect(() => {
    onFlowRef.current = onFlow
    onAlertRef.current = onAlert
  }, [onFlow, onAlert])

  const attemptRef = useRef(0)
  const socketRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const closedByClientRef = useRef(false)

  useEffect(() => {
    if (!token) {
      setStatus('closed')
      return undefined
    }

    closedByClientRef.current = false

    function connect() {
      setStatus(attemptRef.current === 0 ? 'connecting' : 'reconnecting')
      const socket = createFlowSocket(token)
      socketRef.current = socket

      socket.onopen = () => {
        attemptRef.current = 0
        setStatus('open')
      }

      socket.onmessage = (event) => {
        let payload
        try {
          payload = JSON.parse(event.data)
        } catch {
          return // ignore malformed frames
        }

        if (payload.type === 'flow') {
          onFlowRef.current?.(payload)
        } else if (payload.type === 'alert') {
          onAlertRef.current?.(payload)
        }
      }

      socket.onclose = () => {
        if (closedByClientRef.current) {
          setStatus('closed')
          return
        }
        setStatus('reconnecting')
        const attempt = attemptRef.current + 1
        attemptRef.current = attempt
        const backoff = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS)
        const jitter = Math.random() * 0.3 * backoff
        reconnectTimerRef.current = setTimeout(connect, backoff + jitter)
      }

      socket.onerror = () => {
        // onclose fires right after; reconnect logic lives there.
      }
    }

    connect()

    return () => {
      closedByClientRef.current = true
      clearTimeout(reconnectTimerRef.current)
      socketRef.current?.close()
    }
  }, [token])

  return { status }
}
