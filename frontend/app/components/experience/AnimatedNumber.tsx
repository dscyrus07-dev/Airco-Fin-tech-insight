'use client'

import { useEffect, useRef, useState } from 'react'

interface AnimatedNumberProps {
  value: number
  duration?: number
  className?: string
  /** Text appended after the number, e.g. "%". */
  suffix?: string
}

/** Counts up to `value` once on mount and whenever it changes. Honors reduced-motion. */
export default function AnimatedNumber({ value, duration = 900, className, suffix = '' }: AnimatedNumberProps) {
  const [shown, setShown] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    const target = Number.isFinite(value) ? value : 0
    const reduce =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || duration <= 0 || typeof requestAnimationFrame !== 'function') {
      from.current = target
      setShown(target)
      return
    }
    const start = from.current
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      const cur = Math.round(start + (target - start) * eased)
      setShown(cur)
      if (p < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])

  return (
    <span className={className}>
      {shown.toLocaleString()}
      {suffix}
    </span>
  )
}
