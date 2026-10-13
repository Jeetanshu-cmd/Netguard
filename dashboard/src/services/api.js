// Central REST client. Swaps between the mock layer and real fetch calls
// based on VITE_USE_MOCKS, so components never branch on that flag.
//
// Real responses are normalised to the shapes the pages already consume
// ({ flows }, { alerts }); the API returns bare arrays for those routes.
import { API_BASE_URL, USE_MOCKS } from '../utils/constants'
import { getToken } from './tokenStorage'
import { mockApi } from '../mocks/mockApi'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Network error — is the API reachable?', 0)
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const data = await response.json()
      message = data.detail ?? data.message ?? message
    } catch {
      // response had no JSON body
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) return null
  return response.json()
}

export const api = {
  async login(username, password) {
    if (USE_MOCKS) return mockApi.login(username, password)
    return request('/auth/login', { method: 'POST', body: { username, password }, auth: false })
  },

  async getFlows(params = {}) {
    if (USE_MOCKS) return mockApi.getFlows()
    const qs = new URLSearchParams(params).toString()
    const data = await request(`/flows${qs ? `?${qs}` : ''}`)
    return Array.isArray(data) ? { flows: data } : data
  },

  async getAlerts(params = {}) {
    if (USE_MOCKS) return mockApi.getAlerts()
    const qs = new URLSearchParams(params).toString()
    const data = await request(`/alerts${qs ? `?${qs}` : ''}`)
    return Array.isArray(data) ? { alerts: data } : data
  },

  async acknowledgeAlert(id, status = 'acknowledged') {
    if (USE_MOCKS) return { id, status }
    return request(`/alerts/${id}`, { method: 'PATCH', body: { status } })
  },

  async getStats(params = {}) {
    if (USE_MOCKS) return mockApi.getStats()
    const qs = new URLSearchParams(params).toString()
    return request(`/stats${qs ? `?${qs}` : ''}`)
  },

  // Per-label counts for a window: { total, counts: { Benign, DoS_DDoS, ... } }.
  async getStatsSummary(params = {}) {
    if (USE_MOCKS) return { total: 0, counts: {} }
    const qs = new URLSearchParams(params).toString()
    return request(`/stats${qs ? `?${qs}` : ''}`)
  },

  async getModelInfo() {
    if (USE_MOCKS) {
      return { model_type: 'RandomForestClassifier', alert_threshold: 0.85 }
    }
    return request('/model-info', { auth: false })
  },

  async getHealth() {
    if (USE_MOCKS) return mockApi.getHealth()
    return request('/health', { auth: false })
  },

  async getCaptureStatus() {
    if (USE_MOCKS) return mockApi.getCaptureStatus()
    return request('/capture/status')
  },
}

export { ApiError }
