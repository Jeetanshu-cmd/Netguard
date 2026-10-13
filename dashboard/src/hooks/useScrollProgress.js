// Scroll-scrubbed progress for a tall "track" element that contains a sticky
// stage. GSAP + ScrollTrigger are registered once here. All triggers and
// tweens are created inside useGSAP, so they are reverted on unmount and on
// dependency change (no leaks on route change).
//
// prefers-reduced-motion: no ScrollTrigger is created. The timeline (if any)
// is jumped to its end so the static final state is shown.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger, useGSAP)
// Mobile URL-bar show/hide resizes the viewport; don't refresh the trigger on it.
ScrollTrigger.config({ ignoreMobileResize: true })

const QUERY = '(prefers-reduced-motion: reduce)'

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.(QUERY).matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.(QUERY)
    if (!mq) return undefined
    const onChange = (e) => setReduced(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

// Pixels the sticky stage sits below the viewport top (the app header height).
export function getHeaderOffset() {
  return document.querySelector('header')?.offsetHeight ?? 0
}

/**
 * @param trackRef  ref to the tall element (e.g. 600vh)
 * @param opts.build       (track) => paused gsap timeline | null, built inside the GSAP context
 * @param opts.deps        extra dependencies that should rebuild the timeline
 * @param opts.onProgress  (0..1) => void, called on every scroll update
 */
export function useScrollProgress(trackRef, { build, deps = [], onProgress } = {}) {
  const reduced = usePrefersReducedMotion()
  const progress = useRef(0)
  const onProgressRef = useRef(onProgress)
  const buildRef = useRef(build)
  // Layout effect (declared before useGSAP's own) so a rebuild triggered by a
  // dependency change sees this render's callbacks, not the previous render's.
  useLayoutEffect(() => {
    onProgressRef.current = onProgress
    buildRef.current = build
  })

  useGSAP(
    () => {
      const track = trackRef.current
      if (!track) return undefined
      const tl = buildRef.current?.(track) ?? null
      const emit = (p) => {
        progress.current = p
        onProgressRef.current?.(p)
      }

      if (reduced) {
        tl?.progress(1)
        emit(1)
        return undefined
      }

      const trigger = ScrollTrigger.create({
        trigger: track,
        start: () => `top top+=${getHeaderOffset()}`,
        end: 'bottom bottom',
        scrub: tl ? 0.4 : true,
        animation: tl ?? undefined,
        invalidateOnRefresh: true,
        onUpdate: (self) => emit(self.progress),
        onRefresh: (self) => emit(self.progress),
      })
      emit(trigger.progress)
      // Web fonts change text metrics after first paint; recompute trigger positions once.
      let alive = true
      document.fonts?.ready.then(() => alive && ScrollTrigger.refresh())
      return () => {
        alive = false
      }
    },
    { scope: trackRef, dependencies: [reduced, ...deps], revertOnUpdate: true },
  )

  return { progress, reduced }
}
