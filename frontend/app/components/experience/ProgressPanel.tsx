'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import AnimatedNumber from './AnimatedNumber'
import Confetti from './Confetti'
import Icon from './Icon'
import { computeBadges, computeQuests, computeXp, levelFor } from '@/lib/gamification'
import type { ProgressInput } from '@/lib/gamification'

interface ProgressPanelProps {
  input: ProgressInput
  seenBadges: string[]
  baselined: boolean
  onSeen: (ids: string[]) => void
  onQuestClick?: (target: 'upload' | 'guide' | 'limits' | 'report') => void
}

export default function ProgressPanel({ input, seenBadges, baselined, onSeen, onQuestClick }: ProgressPanelProps) {
  const xp = computeXp(input)
  const lv = levelFor(xp)
  const badges = useMemo(() => computeBadges(input), [input])
  const quests = useMemo(() => computeQuests(input), [input])
  const [burst, setBurst] = useState(0)
  const [toast, setToast] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const unlockedIds = badges.filter((b) => b.unlocked).map((b) => b.id)
  const fresh = badges.filter((b) => b.unlocked && !seenBadges.includes(b.id))

  useEffect(() => {
    if (fresh.length === 0) return
    let id: ReturnType<typeof setTimeout> | undefined
    if (baselined) {
      id = setTimeout(() => {
        setBurst((n) => n + 1)
        setToast(`Badge unlocked: ${fresh[0].title}`)
        if (timer.current) clearTimeout(timer.current)
        timer.current = setTimeout(() => setToast(null), 4000)
      }, 0)
    }
    onSeen(unlockedIds)
    return () => { if (id) clearTimeout(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fresh.map((b) => b.id).join('|'), baselined])

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const R = 34
  const C = 2 * Math.PI * R
  const doneQuests = quests.filter((q) => q.done).length

  return (
    <aside className="card-surface relative p-5 sm:p-6" aria-label="Your progress">
      <Confetti burstKey={burst} />
      {toast && (
        <div role="status" className="absolute inset-x-4 -top-3 z-20 animate-toast-in rounded-xl bg-slate-900 px-4 py-2 text-center text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}
      <div className="flex items-center gap-4">
        <div className="relative h-20 w-20 shrink-0">
          <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90" aria-hidden="true">
            <circle cx="40" cy="40" r={R} fill="none" stroke="#e2e8f0" strokeWidth="7" />
            <circle
              cx="40" cy="40" r={R} fill="none" stroke="url(#lvl)" strokeWidth="7" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={C * (1 - lv.pct / 100)}
              style={{ transition: 'stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1)' }}
            />
            <defs>
              <linearGradient id="lvl" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#4f46e5" />
                <stop offset="1" stopColor="#db2777" />
              </linearGradient>
            </defs>
          </svg>
          <span className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">Level</span>
            <span className="text-xl font-bold text-slate-900">{lv.level.index}</span>
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-lg font-bold text-gradient text-slate-900">{lv.level.name}</p>
          <p className="text-sm text-slate-600">
            <AnimatedNumber value={xp} /> XP
          </p>
          <p className="text-xs text-slate-500">
            {lv.next ? `${lv.xpToNext} XP to ${lv.next.name}` : 'Top level reached'}
          </p>
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Quests</h3>
          <span className="text-xs text-slate-500">{doneQuests}/{quests.length} done</span>
        </div>
        <ul className="space-y-2">
          {quests.map((q) => (
            <li key={q.id}>
              <button
                type="button"
                disabled={q.done}
                onClick={() => onQuestClick?.(q.target)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left ring-1 transition ${
                  q.done ? 'bg-emerald-50 ring-emerald-100' : 'bg-white ring-slate-200 hover:-translate-y-px hover:ring-indigo-300'
                }`}
              >
                <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${q.done ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-400'}`}>
                  <Icon name={q.done ? 'check' : 'target'} size={14} strokeWidth={2.4} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className={`block text-sm font-medium ${q.done ? 'text-emerald-800 line-through decoration-emerald-300' : 'text-slate-800'}`}>{q.title}</span>
                  <span className="block text-xs text-slate-500">{q.hint}</span>
                </span>
                <span className="text-xs font-semibold text-indigo-600">+{q.xp}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Badges</h3>
          <span className="text-xs text-slate-500">{unlockedIds.length}/{badges.length}</span>
        </div>
        <ul className="grid grid-cols-5 gap-2">
          {badges.map((b) => (
            <li
              key={b.id}
              title={`${b.title}: ${b.description}${b.unlocked ? '' : ` (${b.current}/${b.target})`}`}
              className={`flex aspect-square items-center justify-center rounded-xl ring-1 ${
                b.unlocked ? 'bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white ring-transparent shadow-md' : 'bg-slate-50 text-slate-300 ring-slate-200'
              }`}
            >
              <Icon name={b.unlocked ? b.icon : 'lock'} size={20} />
              <span className="sr-only">{b.title}{b.unlocked ? ' unlocked' : ' locked'}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 text-[11px] text-slate-400">Progress is just for fun and stored in this browser. It never affects your reports.</p>
    </aside>
  )
}
