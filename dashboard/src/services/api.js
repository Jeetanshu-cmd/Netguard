// Central REST client. Swaps between the mock layer and real fetch calls
// based on VITE_USE_MOCKS, so components never branch on that flag.
//
// TODO(backend): once api/ is live, set VITE_USE_MOCKS=false in .env.local
// and verify every endpoint below matches AGENTS.md + README §8.
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
    return request(`/flows${qs ? `?${qs}` : ''}`)
  },

  async getAlerts(params = {}) {
    if (USE_MOCKS) return mockApi.getAlerts()
    const qs = new URLSearchParams(params).toString()
    return request(`/alerts${qs ? `?${qs}` : ''}`)
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
