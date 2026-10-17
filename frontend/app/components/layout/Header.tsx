'use client'

import Image from 'next/image'
import Link from 'next/link'
import { KeyRound, UserCircle2 } from 'lucide-react'
import { unifiedEntry } from '@/lib/flags'

interface HeaderProps {
  onProfileClick?: () => void
  /** Optional level chip, e.g. "Lv 2 · Explorer". */
  levelLabel?: string
}

const pill =
  'flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:-translate-y-px hover:border-indigo-300 hover:text-indigo-700'

export default function Header({ onProfileClick, levelLabel }: HeaderProps) {
  const unified = unifiedEntry()
  return (
    <header className="glass sticky top-0 z-30 -mx-4 mb-8 border-b border-slate-200/70 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 py-3">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" alt="Airco Insights" width={36} height={36} className="rounded-lg shadow-sm" />
          <div className="leading-tight">
            <h1 className="text-lg font-bold tracking-tight text-slate-900">Airco Insights</h1>
            <p className="hidden text-xs tracking-wide text-slate-500 sm:block">Financial Categorization Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {levelLabel && (
            <span className="hidden rounded-full bg-gradient-to-r from-indigo-600 to-fuchsia-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm md:inline-block">
              {levelLabel}
            </span>
          )}
          {!unified && (
            <Link href="/analyze" className={pill}>
              Analyze
            </Link>
          )}
          <Link href="/dashboard/api-keys" className={pill}>
            <KeyRound className="h-4 w-4" />
            <span>API Keys</span>
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
