// Sign-in screen. Left: what NetGuard does and how (all facts from the project
// README / AGENTS.md). Right: the real login form (POST /auth/login).
import { useId, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ShieldLogo } from '../components/ShieldLogo.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { USE_MOCKS } from '../utils/constants.js'
import styles from './LoginPage.module.css'

const FACTS = [
  { value: '19', label: 'flow features' },
  { value: '4', label: 'attack classes' },
  { value: '0.85', label: 'alert threshold' },
  { value: '30s', label: 'de-dup window' },
]

const STEPS = [
  { tag: 'SENSOR', title: 'Sniff', text: 'Scapy reads a real network interface and groups packets into two-way flows.' },
  { tag: '19 FEATURES', title: 'Measure', text: 'Each finished flow becomes 19 statistics: sizes, rates, timings, TCP flags. Payloads are never stored.' },
  { tag: 'RANDOM FOREST', title: 'Classify', text: 'A trained model labels the flow and says how sure it is, within seconds.' },
  { tag: 'WEBSOCKET', title: 'Alert', text: 'Above 0.85 confidence, one alert per attacker is raised and pushed to this dashboard live.' },
]

const CLASSES = [
  { key: 'Benign', tone: 'benign', text: 'Normal browsing, DNS lookups and streaming.', signals: 'steady rates · full handshakes' },
  { key: 'DoS_DDoS', tone: 'dos', text: 'Floods that try to exhaust a service: SYN bursts and volumetric traffic.', signals: 'packets_per_sec ↑ · syn_count ↑' },
  { key: 'PortScan', tone: 'scan', text: 'Reconnaissance that probes many ports and never completes the handshake.', signals: 'many dst_port · syn without ack' },
  { key: 'BruteForce', tone: 'brute', text: 'Rapid, repeated login attempts against SSH, FTP or web auth.', signals: 'fwd_packets ↑ · same dst_port' },
]

const STACK = ['Scapy sensor', 'FastAPI', 'Random Forest', 'SQLite', 'WebSocket', 'React']

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
    if (!username || !password) return
    const ok = await login(username, password)
    if (ok) navigate(from, { replace: true })
  }

  const showUsernameError = submitted && !username
  const showPasswordError = submitted && !password

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <ShieldLogo size={24} className={styles.brandMark} />
          <span>NetGuard AI</span>
        </div>
        <nav className={styles.pillNav} aria-label="Page sections">
          <a href="#how">How it works</a>
          <a href="#detect">What it detects</a>
          <a href="#stack">Under the hood</a>
        </nav>
        <a className={styles.signinLink} href="#signin">Sign in</a>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.intro}>
            <p className={styles.eyebrow}>Network attack detection</p>
            <h1 className={styles.h1}>Watch an attack build, flow by flow.</h1>
            <p className={styles.lead}>
              NetGuard listens to live traffic, classifies every flow in seconds, and raises one clear
              alert per attacker instead of ten thousand popups.
            </p>
            <dl className={styles.facts}>
              {FACTS.map((f) => (
                <div key={f.label}>
                  <dt>{f.label}</dt>
                  <dd>{f.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <form id="signin" className={styles.card} onSubmit={handleSubmit} noValidate>
            <h2 className={styles.cardTitle}>Sign in</h2>
            <p className={styles.cardSub}>Viewers can watch. Admins can also acknowledge alerts.</p>

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
                <p id={`${usernameId}-error`} className={styles.fieldError}>Enter your username.</p>
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
                <p id={`${passwordId}-error`} className={styles.fieldError}>Enter your password.</p>
              )}
            </div>

            {error && (
              <p className={styles.formError} role="alert">{error}</p>
            )}

            <button type="submit" className={styles.submit} disabled={isLoading}>
              {isLoading ? 'Signing in…' : 'Sign in'}
              <span aria-hidden="true">→</span>
            </button>

            <p className={styles.hint}>
              {USE_MOCKS
                ? 'Demo mode: any non-empty username and password signs in.'
                : 'No account yet? An admin creates users with the seed_admin script.'}
            </p>
          </form>
        </section>

        <section id="how" className={styles.section} aria-labelledby="how-h">
          <p className={styles.eyebrow}>The pipeline</p>
          <h2 id="how-h" className={styles.h2}>From raw packet to alert.</h2>
          <ol className={styles.steps}>
            {STEPS.map((s, i) => (
              <li key={s.title} className={styles.step}>
                <span className={styles.stepNum}>{String(i + 1).padStart(2, '0')}</span>
                <span className={styles.stepTag}>{s.tag}</span>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="detect" className={styles.section} aria-labelledby="detect-h">
          <p className={styles.eyebrow}>Detection classes</p>
          <h2 id="detect-h" className={styles.h2}>Four labels, each with a fingerprint.</h2>
          <ul className={styles.classes}>
            {CLASSES.map((c) => (
              <li key={c.key} className={`${styles.class} ${styles[c.tone]}`}>
                <span className={styles.classKey}>{c.key}</span>
                <p>{c.text}</p>
                <span className={styles.signals}>{c.signals}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="stack" className={styles.section} aria-labelledby="stack-h">
          <p className={styles.eyebrow}>Under the hood</p>
          <h2 id="stack-h" className={styles.h2}>Small, readable, Python-first.</h2>
          <ul className={styles.stack}>
            {STACK.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className={styles.note}>
            Trained on CICIDS2017 plus traffic captured in our own lab. Capture only on networks you own
            or have written permission to test.
          </p>
        </section>
      </main>
    </div>
  )
}
