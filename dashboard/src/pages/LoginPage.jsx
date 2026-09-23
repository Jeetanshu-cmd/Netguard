import { useId, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ShieldLogo } from '../components/ShieldLogo.jsx'
import { useAuth } from '../hooks/useAuth.js'
import styles from './LoginPage.module.css'

export function LoginPage() {
  const { login, isLoading, error } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const usernameId = useId()
  const passwordId = useId()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const from = location.state?.from?.pathname ?? '/'

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitted(true)
    const ok = await login(username, password)
    if (ok) navigate(from, { replace: true })
  }

  const showUsernameError = submitted && !username
  const showPasswordError = submitted && !password

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <div className={styles.brand}>
          <ShieldLogo size={26} className={styles.brandMark} />
          <span>NetGuard AI</span>
        </div>
        <p className={styles.subtitle}>Sign in to view live network detections.</p>

        <div className={styles.field}>
          <label htmlFor={usernameId}>Username</label>
          <input
            id={usernameId}
            name="username"
            type="text"
            autoComplete="username"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={showUsernameError}
            aria-describedby={showUsernameError ? `${usernameId}-error` : undefined}
          />
          {showUsernameError && (
            <p id={`${usernameId}-error`} className={styles.fieldError}>
              Enter your username.
            </p>
          )}
        </div>

        <div className={styles.field}>
          <label htmlFor={passwordId}>Password</label>
          <input
            id={passwordId}
            name="password"
            type="password"
            autoComplete="current-password"
            spellCheck={false}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={showPasswordError}
            aria-describedby={showPasswordError ? `${passwordId}-error` : undefined}
          />
          {showPasswordError && (
            <p id={`${passwordId}-error`} className={styles.fieldError}>
              Enter your password.
            </p>
          )}
        </div>

        {error && (
          <p className={styles.formError} role="alert">
            {error}
          </p>
        )}

        <button type="submit" className={styles.submitButton} disabled={isLoading}>
          {isLoading ? 'Signing In…' : 'Sign In'}
        </button>

        <p className={styles.hint}>
          Demo mode: any non-empty username/password signs in (mock auth).
        </p>
      </form>
    </div>
  )
}
