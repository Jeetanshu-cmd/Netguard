// Creates either a real browser WebSocket or the mock one, both exposing
// the same interface. useFlowSocket.js is the only consumer.
import { USE_MOCKS, WS_BASE_URL } from '../utils/constants'
import { MockFlowSocket } from '../mocks/mockSocket'

export function createFlowSocket(token) {
  const url = `${WS_BASE_URL}/ws/flows?token=${encodeURIComponent(token ?? '')}`
  if (USE_MOCKS) return new MockFlowSocket(url)
  return new WebSocket(url)
}
