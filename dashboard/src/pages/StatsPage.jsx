// Stats dashboard: flow counts per label over time (line) + top source IPs
// (bar). Chart.js elements are registered once at module scope (not per
// render) to avoid re-registration overhead.
import { useEffect, useMemo, useState } from 'react'
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  BarElement,
  PointElement,
  TimeScale,
  Title,
  Tooltip,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import { api } from '../services/api.js'
import { useTheme } from '../hooks/useTheme.js'
import { LABELS, LABEL_COLORS } from '../utils/constants.js'
import styles from './StatsPage.module.css'

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
)

const REFRESH_INTERVAL_MS = 30000

// Chart.js draws to canvas, so it can't inherit CSS variables directly, and
// reading them back via getComputedStyle() races with the ThemeContext
// effect that sets [data-theme] on <html> (that effect lives in a different
// component and isn't guaranteed to have committed yet when this page's
// memo runs). Mirroring the palette here keyed by theme name avoids the
// race entirely — must stay in sync with the dark/light blocks in index.css.
const CHART_PALETTE = {
  light: {
    textMuted: '#4d4d4d',
    textFaint: '#8f8f8f',
    border: '#ebebeb',
    surface: '#ffffff',
    text: '#171717',
  },
  dark: {
    textMuted: '#b4b4b4',
    textFaint: '#7a7a7a',
    border: '#262626',
    surface: '#111111',
    text: '#ededed',
  },
}

function buildChartOptions(theme) {
  const { textMuted, textFaint, border, surface, text } = CHART_PALETTE[theme] ?? CHART_PALETTE.light

  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: textMuted } },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: surface,
        titleColor: text,
        bodyColor: textMuted,
        borderColor: border,
        borderWidth: 1,
        padding: 10,
      },
    },
    scales: {
      x: { ticks: { color: textFaint }, grid: { color: border } },
      y: { ticks: { color: textFaint }, grid: { color: border }, beginAtZero: true },
    },
  }
}

export function StatsPage() {
  const { theme } = useTheme()
  const [buckets, setBuckets] = useState([])
  const [topSourceIps, setTopSourceIps] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  // Recompute chart colors whenever the theme changes, since Chart.js reads
  // plain color strings once and won't react to CSS variable updates itself.
  const baseChartOptions = useMemo(() => buildChartOptions(theme), [theme])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await api.getStats()
        if (!cancelled) {
          setBuckets(data.buckets ?? [])
          setTopSourceIps(data.top_source_ips ?? [])
          setLoadError(null)
        }
      } catch (err) {
        if (!cancelled) setLoadError(err.message ?? 'Failed to load stats')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    load()
    const interval = setInterval(load, REFRESH_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const lineData = useMemo(() => {
    const timeFormatter = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
    return {
      labels: buckets.map((b) => timeFormatter.format(new Date(b.timestamp))),
      datasets: LABELS.map((label) => ({
        label,
        data: buckets.map((b) => b[label] ?? 0),
        borderColor: LABEL_COLORS[label],
        backgroundColor: LABEL_COLORS[label],
        tension: 0.3,
        pointRadius: 0,
      })),
    }
  }, [buckets])

  const barData = useMemo(
    () => ({
      labels: topSourceIps.map((row) => row.src_ip),
      datasets: [
        {
          label: 'Flow count',
          data: topSourceIps.map((row) => row.flow_count),
          backgroundColor: '#0070f3',
          borderRadius: 4,
        },
      ],
    }),
    [topSourceIps],
  )

  return (
    <section aria-labelledby="stats-heading">
      <h1 id="stats-heading" className={styles.heading}>
        Stats
      </h1>
      <p className={styles.description}>
        Flow counts per label over time, and the busiest source IPs in the current window.
      </p>

      {isLoading && <p className={styles.description}>Loading stats…</p>}
      {loadError && (
        <p className={styles.formError} role="alert">
          {loadError}
        </p>
      )}

      {!isLoading && !loadError && (
        <div className={styles.grid}>
          <div className={styles.chartCard}>
            <h2 className={styles.chartTitle} id="flow-counts-title">
              Flow Counts by Label
            </h2>
            <div className={styles.chartBox} role="img" aria-labelledby="flow-counts-title" aria-describedby="flow-counts-desc">
              <Line data={lineData} options={baseChartOptions} />
            </div>
            <p id="flow-counts-desc" className="visually-hidden">
              Line chart of classified flow counts per label ({LABELS.join(', ')}) across the
              current time window.
            </p>
          </div>

          <div className={styles.chartCard}>
            <h2 className={styles.chartTitle} id="top-ips-title">
              Top Source IPs
            </h2>
            <div className={styles.chartBox} role="img" aria-labelledby="top-ips-title" aria-describedby="top-ips-desc">
              <Bar
                data={barData}
                options={{ ...baseChartOptions, indexAxis: 'y', plugins: { legend: { display: false } } }}
              />
            </div>
            <p id="top-ips-desc" className="visually-hidden">
              Bar chart ranking source IP addresses by flow count:{' '}
              {topSourceIps.map((row) => `${row.src_ip} (${row.flow_count})`).join(', ') || 'no data yet'}.
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
