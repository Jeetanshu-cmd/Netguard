import { NavLink, Outlet } from 'react-router-dom'
import { HealthIndicator } from '../components/HealthIndicator.jsx'
import { ShieldLogo } from '../components/ShieldLogo.jsx'
import { ThemeToggle } from '../components/ThemeToggle.jsx'
import { useAuth } from '../hooks/useAuth.js'
import styles from './AppShell.module.css'

const NAV_ITEMS = [
  { to: '/', label: 'Live Feed' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/stats', label: 'Stats' },
]

export function AppShell() {
  const { logout } = useAuth()

  return (
    <div className={styles.shell}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <header className={styles.header}>
        <div className={styles.brand}>
          <ShieldLogo className={styles.brandMark} size={22} />
          <span>NetGuard AI</span>
        </div>

        <nav className={styles.nav} aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? styles.navLinkActive : styles.navLink)}
              end={item.to === '/'}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className={styles.headerRight}>
          <HealthIndicator />
          <ThemeToggle />
          <button type="button" className={styles.logoutButton} onClick={logout}>
            Log Out
          </button>
        </div>
      </header>

      <main id="main-content" className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
