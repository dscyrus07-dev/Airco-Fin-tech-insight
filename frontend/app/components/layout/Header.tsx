'use client'

import Image from 'next/image'
import { UserCircle2 } from 'lucide-react'

interface HeaderProps {
  onProfileClick?: () => void
}

export default function Header({ onProfileClick }: HeaderProps) {
  return (
    <header className="w-full pt-10 pb-6">
      <div className="relative mb-2 flex max-w-[1440px] mx-auto items-center justify-center px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center text-center gap-2">
          <div className="flex items-center justify-center gap-3">
          <Image
            src="/logo.png"
            alt="Airco Insights"
            width={36}
            height={36}
            className="rounded"
          />
          <h1 className="text-2xl font-semibold tracking-tight text-black">
            Airco Insights
          </h1>
          </div>
          <p className="text-sm text-neutral-500 tracking-wide">
            Financial Categorization Engine
          </p>
        </div>
        <button
          onClick={onProfileClick}
          className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm font-medium text-neutral-700 shadow-sm transition hover:border-neutral-300 hover:bg-neutral-50 sm:right-6 lg:right-8"
        >
          <UserCircle2 className="h-5 w-5" />
          Profile
        </button>
      </div>
    </header>
  )
}
