import { useCallback, useMemo, useState } from 'react'
import { api } from '../services/api'
import { clearToken, getRoleFromToken, getToken, setToken } from '../services/tokenStorage'
import { AuthContext } from './authContextDefinition.js'

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken())
  const [role, setRole] = useState(() => getRoleFromToken(getToken()))
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const login = useCallback(async (username, password) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await api.login(username, password)
      // Real API returns { access_token, token_type, role }; the mock returns { token, role }.
      const jwt = result.access_token ?? result.token
      setToken(jwt)
      setTokenState(jwt)
      setRole(result.role ?? getRoleFromToken(jwt))
      return true
    } catch (err) {
      setError(err.message ?? 'Login failed')
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setTokenState(null)
    setRole(null)
  }, [])

  const value = useMemo(
    () => ({ token, role, error, isLoading, login, logout, isAuthenticated: Boolean(token) }),
    [token, role, error, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
