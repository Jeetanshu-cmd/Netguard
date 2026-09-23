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
