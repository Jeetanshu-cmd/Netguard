// Mock REST responses. Shapes match AGENTS.md + README §8 additions.
// TODO(backend): delete this file once api/ routes are live; remove the
// USE_MOCKS branches in services/api.js at the same time.
import { makeMockAlert, makeMockAlertableFlow, makeMockStats, makeMockTopSourceIps } from './mockData'

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

let mockAlerts = null

function seedAlerts() {
  if (mockAlerts) return mockAlerts
  // Only non-Benign, >85% confidence flows may seed an alert (README §3).
  mockAlerts = Array.from({ length: 4 }, () => makeMockAlert(makeMockAlertableFlow()))
  return mockAlerts
}

export const mockApi = {
  async login(username, _password) {
    await delay(400)
    if (!username) {
      const err = new Error('Invalid credentials')
      err.status = 401
      throw err
    }
    // Fake JWT-shaped string (not a real signature) purely for local demo.
    return { token: `mock.${btoa(username)}.token`, role: 'Admin' }
  },

  async getFlows() {
    await delay(300)
    return { flows: Array.from({ length: 20 }, () => makeMockFlow()) }
  },

  async getAlerts() {
    await delay(300)
    return { alerts: seedAlerts() }
  },

  async getStats() {
    await delay(300)
    return { buckets: makeMockStats(), top_source_ips: makeMockTopSourceIps() }
  },

  async getHealth() {
    await delay(150)
    return { status: 'healthy', model_loaded: true, timestamp: new Date().toISOString() }
  },

  async getCaptureStatus() {
    await delay(150)
    return {
      sensor_online: true,
      last_heartbeat: new Date().toISOString(),
      last_ingest: new Date().toISOString(),
    }
  },
}
