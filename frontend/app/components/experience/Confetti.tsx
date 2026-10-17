'use client'

import { useMemo } from 'react'
import type { CSSProperties } from 'react'

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#38bdf8']

interface ConfettiProps {
  /** Changing this value replays the burst. */
  burstKey: number
  count?: number
}

/** CSS-only confetti burst (no canvas, no library). Pointer-events none; hidden for reduced-motion users. */
export default function Confetti({ burstKey, count = 26 }: ConfettiProps) {
  const pieces = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        // deterministic spread per burst so renders are stable and testable
        const a = ((i * 137.5 + burstKey * 29) % 360) * (Math.PI / 180)
        const dist = 90 + ((i * 37 + burstKey * 11) % 120)
        return {
          id: i,
          dx: `${Math.round(Math.cos(a) * dist)}px`,
          dy: `${Math.round(Math.sin(a) * dist - 40)}px`,
          rot: `${(i * 53) % 540}deg`,
          color: COLORS[i % COLORS.length],
          delay: `${(i % 6) * 25}ms`,
          w: 6 + (i % 3) * 2,
        }
      }),
    [burstKey, count]
  )

  if (!burstKey) return null
  return (
    <div
      key={burstKey}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-10 overflow-visible motion-reduce:hidden"
    >
      <div className="absolute left-1/2 top-1/2">
        {pieces.map((p) => (
          <span
            key={p.id}
            className="absolute block animate-confetti-fall rounded-[2px]"
            style={
              {
                width: p.w,
                height: p.w * 1.6,
                backgroundColor: p.color,
                animationDelay: p.delay,
                '--dx': p.dx,
                '--dy': p.dy,
                '--rot': p.rot,
              } as CSSProperties
            }
          />
        ))}
      </div>
    </div>
  )
}
