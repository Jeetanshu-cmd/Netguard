// Token persistence. sessionStorage is used (not localStorage) so a JWT
// doesn't linger across browser restarts on a shared lab machine.
import { TOKEN_STORAGE_KEY } from '../utils/constants'

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // sessionStorage unavailable (private mode / quota) — auth simply won't persist
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // no-op
  }
}

// The JWT payload carries the role claim ("admin" | "viewer"). Decoding is for
// UI gating only; the API enforces roles on every request.
export function getRoleFromToken(token) {
  if (!token) return null
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(payload)).role ?? null
  } catch {
    return null
  }
}
