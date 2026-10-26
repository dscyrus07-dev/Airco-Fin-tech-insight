'use client'

import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import Icon from './Icon'
import type { IconName } from './Icon'

interface AccordionProps {
  title: string
  subtitle?: string
  icon: IconName
  children: ReactNode
  defaultOpen?: boolean
  /** Fired the first time the panel is opened (used to award progress). */
  onFirstOpen?: () => void
  accent?: 'indigo' | 'amber'
}

const ACCENT = {
  indigo: 'bg-[#01275C]/10 text-[#01275C] ring-[#A1B2CE]/40 dark:bg-blue-500/20 dark:text-blue-300 dark:ring-blue-400/30',
  amber: 'bg-amber-50 text-amber-600 ring-amber-100 dark:bg-amber-500/20 dark:text-amber-300 dark:ring-amber-500/30',
} as const

/** Animated drop-down panel. Content stays mounted so height can transition; hidden content is not focusable. */
export default function Accordion({ title, subtitle, icon, children, defaultOpen = false, onFirstOpen, accent = 'indigo' }: AccordionProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [fired, setFired] = useState(defaultOpen)
  const id = useId()

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && !fired) {
      setFired(true)
      onFirstOpen?.()
    }
  }

  return (
    <section className="card-surface overflow-hidden">
      <h3>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={`${id}-body`}
          className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/40 sm:px-6"
        >
          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ${ACCENT[accent]}`}>
            <Icon name={icon} size={20} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100 sm:text-base">{title}</span>
            {subtitle && <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400 sm:text-sm">{subtitle}</span>}
          </span>
          <Icon
            name="chevron"
            size={20}
            className={`shrink-0 text-slate-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          />
        </button>
      </h3>
      <div id={`${id}-body`} role="region" aria-label={title} className="accordion-body" data-open={open} {...(open ? {} : { inert: true as unknown as undefined })}>
        <div>
          <div className="border-t border-slate-100 px-5 py-5 dark:border-slate-800 sm:px-6">{children}</div>
        </div>
      </div>
    </section>
  )
}
