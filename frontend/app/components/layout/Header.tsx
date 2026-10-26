'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { KeyRound, Moon, Sun, UserCircle2 } from 'lucide-react'
import { unifiedEntry } from '@/lib/flags'

interface HeaderProps {
  onProfileClick?: () => void
  /** Optional level chip, e.g. "Lv 2 · Explorer". */
  levelLabel?: string
}

const pill =
  'flex items-center gap-2 rounded-full border border-slate-200/90 bg-white/90 px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:-translate-y-px hover:border-[#01275C]/40 hover:text-[#01275C] dark:border-slate-700/80 dark:bg-[#0B1B36]/90 dark:text-slate-200 dark:hover:border-blue-400/50 dark:hover:text-white'

export function useThemeMode() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    const sync = () => setDark(document.documentElement.classList.contains('dark'))
    sync()
    const obs = new MutationObserver(sync)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])

  const toggle = () => {
    const next = !document.documentElement.classList.contains('dark')
    document.documentElement.classList.toggle('dark', next)
    setDark(next)
    try {
      localStorage.setItem('airco-theme', next ? 'dark' : 'light')
    } catch {
      // ignore storage errors
    }
  }

  return { dark, toggle }
}

export default function Header({ onProfileClick, levelLabel }: HeaderProps) {
  const unified = unifiedEntry()
  const { dark, toggle } = useThemeMode()

  return (
    <header className="glass sticky top-0 z-30 mb-6 w-full border-b border-slate-200/80 transition-colors dark:border-slate-800/80">
      <div className="mx-auto flex w-full items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-10 xl:px-12">
        <div className="flex items-center gap-3.5">
          <div className="flex items-center gap-3">
            <Image
              src={dark ? '/logo-wordmark-dark.png' : '/logo-wordmark-light.png'}
              alt="AiRCo — From Data to Intelligence"
              width={132}
              height={42}
              className="h-9 w-auto object-contain sm:h-10"
              priority
              unoptimized
            />
          </div>
          <span className="hidden h-7 w-px bg-slate-200 dark:bg-slate-700/80 sm:block" aria-hidden="true" />
          <div className="leading-tight">
            <h1 className="text-base font-bold tracking-tight text-[#01275C] dark:text-white sm:text-lg">
              Airco Insights
            </h1>
            <p className="hidden text-xs font-medium tracking-wide text-slate-500 dark:text-slate-400 sm:block">
              Financial Categorization Engine
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-2.5">
          {levelLabel && (
            <span className="hidden rounded-full bg-gradient-to-r from-[#01275C] to-[#0D3B82] px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm ring-1 ring-[#A1B2CE]/30 dark:from-[#1D4ED8] dark:to-[#0D3B82] md:inline-block">
              {levelLabel}
            </span>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={pill}
          >
            {dark ? (
              <>
                <Sun className="h-4 w-4 text-amber-400" />
                <span className="hidden sm:inline">Light</span>
              </>
            ) : (
              <>
                <Moon className="h-4 w-4 text-[#01275C]" />
                <span className="hidden sm:inline">Dark</span>
              </>
            )}
          </button>
          {!unified && (
            <Link href="/analyze" className={pill}>
              Analyze
            </Link>
          )}
          <Link href="/dashboard/api-keys" className={pill}>
            <KeyRound className="h-4 w-4" />
            <span className="hidden sm:inline">API Keys</span>
          </Link>
          <button onClick={onProfileClick} className={pill}>
            <UserCircle2 className="h-4 w-4" />
            <span>Profile</span>
          </button>
        </div>
      </div>
    </header>
  )
}
