// <canvas> particle field: dots scattered across the canvas converge into a
// dense block as `progressRef.current` goes 0 -> 1. The rAF loop only runs
// while the canvas is on screen (IntersectionObserver) and redraws only when
// the progress value changed. Reduced motion: drawn once at progress 1.
import { useEffect, useRef } from 'react'
import { usePrefersReducedMotion } from '../../hooks/useScrollProgress.js'

const DESKTOP_COUNT = 6000
const MOBILE_COUNT = 1800
const ACCENT_SHARE = 0.14
const clamp01 = (v) => Math.max(0, Math.min(1, v))
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2)

function makeParticles(n) {
  const data = new Float32Array(n * 5) // sx, sy, tx, ty, delay (all 0..1)
  for (let i = 0; i < n; i += 1) {
    const o = i * 5
    data[o] = Math.random()
    data[o + 1] = Math.random()
    data[o + 2] = 0.52 + Math.random() * 0.4 // dense block, right side
    data[o + 3] = 0.22 + Math.random() * 0.56
    data[o + 4] = Math.random()
  }
  return data
}

export function ParticleField({ progressRef, className }) {
  const canvasRef = useRef(null)
  const reduced = usePrefersReducedMotion()

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const n = window.matchMedia('(max-width: 767px)').matches ? MOBILE_COUNT : DESKTOP_COUNT
    const data = makeParticles(n)
    const accentCount = Math.floor(n * ACCENT_SHARE)
    let width = 0
    let height = 0
    let dpr = 1
    let visible = false
    let raf = 0
    let lastP = -1

    function render(p) {
      const e = ease(clamp01(p))
      ctx.clearRect(0, 0, width, height)
      const size = Math.max(1, 1.4 * dpr)
      for (let pass = 0; pass < 2; pass += 1) {
        ctx.fillStyle = pass === 0 ? 'rgba(170, 185, 255, 0.5)' : '#3b5bff'
        const from = pass === 0 ? accentCount : 0
        const to = pass === 0 ? n : accentCount
        ctx.beginPath()
        for (let i = from; i < to; i += 1) {
          const o = i * 5
          const t = ease(clamp01((e - data[o + 4] * 0.45) / 0.55))
          const x = (data[o] + (data[o + 2] - data[o]) * t) * width
          const y = (data[o + 1] + (data[o + 3] - data[o + 1]) * t) * height
          ctx.rect(x, y, size, size)
        }
        ctx.fill()
      }
    }

    function resize() {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(2, window.devicePixelRatio || 1)
      width = Math.max(1, Math.round(rect.width * dpr))
      height = Math.max(1, Math.round(rect.height * dpr))
      canvas.width = width
      canvas.height = height
      lastP = -1
      if (reduced || !visible) render(reduced ? 1 : progressRef.current ?? 0)
    }

    function loop() {
      raf = 0
      if (!visible) return
      const p = progressRef.current ?? 0
      if (p !== lastP) {
        lastP = p
        render(p)
      }
      raf = requestAnimationFrame(loop)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    resize()

    let io = null
    if (!reduced) {
      io = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting
        if (visible && !raf) raf = requestAnimationFrame(loop)
      })
      io.observe(canvas)
    }

    return () => {
      ro.disconnect()
      io?.disconnect()
      if (raf) cancelAnimationFrame(raf)
    }
  }, [progressRef, reduced])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
