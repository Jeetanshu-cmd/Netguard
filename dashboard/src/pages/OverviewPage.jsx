// Overview: the scroll-driven story (packet trace, particle story) and the
// live topology, sharing one LiveDataProvider (one WebSocket for all of it).
import { useEffect, useRef } from 'react'
import { LiveDataProvider } from '../context/LiveDataContext.jsx'
import { PacketTrace } from '../components/trace/PacketTrace.jsx'
import { StoryPanels } from '../components/story/StoryPanels.jsx'
import { LiveTopology } from '../components/topology/LiveTopology.jsx'
import { getHeaderOffset } from '../hooks/useScrollProgress.js'
import styles from './OverviewPage.module.css'

export function OverviewPage() {
  const rootRef = useRef(null)

  // Sticky stages sit just under the app header, whose height changes when the
  // nav wraps on phones. Publish it as a CSS variable and keep it current.
  useEffect(() => {
    const root = rootRef.current
    const header = document.querySelector('header')
    const apply = () => root.style.setProperty('--nd-sticky-top', `${getHeaderOffset()}px`)
    apply()
    const ro = new ResizeObserver(apply)
    if (header) ro.observe(header)
    return () => ro.disconnect()
  }, [])

  return (
    <div ref={rootRef} className={styles.nd}>
      <h1 className="visually-hidden">Overview</h1>
      <LiveDataProvider>
        <PacketTrace />
        <StoryPanels />
        <LiveTopology />
      </LiveDataProvider>
    </div>
  )
}
