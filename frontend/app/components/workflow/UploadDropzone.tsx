'use client'

import { useRef, useState } from 'react'
import type { BankCatalogEntry, BankOption } from '@/lib/statementsApi'
import { catalogFromBanks, isSelectable } from '@/lib/bankSupport'
import BankSelect from '@/app/components/bank/BankSelect'
import BankSupportPanel from '@/app/components/bank/BankSupportPanel'

interface UploadDropzoneProps {
  onFiles: (list: FileList | null) => void
  fileCount: number
  onAnalyze: () => Promise<void>
  busy: string | null
  error: string | null
  banks: BankOption[]
  catalog?: BankCatalogEntry[]
  holderName?: string
  onHolderName?: (v: string) => void
  bankHint?: string
  onBankHint?: (v: string) => void
}

export default function UploadDropzone({
  onFiles,
  fileCount,
  onAnalyze,
  busy,
  error,
  banks,
  catalog,
  holderName,
  onHolderName,
  bankHint,
  onBankHint,
}: UploadDropzoneProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const effectiveCatalog = catalog?.length ? catalog : catalogFromBanks(banks)

  return (
    <div className="w-full max-w-2xl min-w-0">
      <h1 className="text-2xl font-bold text-slate-900">Analyze statements</h1>
      <p className="mt-1 text-sm text-gray-600">
        Upload one or more bank statement PDFs. We detect the bank and layout first; nothing is processed until you
        confirm.
      </p>

      <div
        role="button"
        tabIndex={0}
        aria-label="Upload statements"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          onFiles(e.dataTransfer.files)
        }}
        className={`mt-6 cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-300 ${
          dragOver
            ? 'scale-[1.01] border-indigo-500 bg-indigo-50'
            : 'border-slate-300 bg-slate-50/60 hover:border-indigo-400 hover:bg-indigo-50/50'
        }`}
      >
        <p className="text-base font-semibold text-slate-800">Drop up to 20 PDF statements here</p>
        <p className="mt-1 text-xs text-neutral-500">or click to choose files</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={(e) => onFiles(e.target.files)}
          aria-label="Select PDF statements"
        />
      </div>

      <details className="mt-4 rounded border border-neutral-200 px-4 py-3" open={detailsOpen}>
        <summary className="cursor-pointer text-sm font-medium text-neutral-700" onClick={(e) => { e.preventDefault(); setDetailsOpen((o) => !o) }}>
          Details (optional)
        </summary>
        <div className="mt-3 space-y-3">
          {onHolderName && (
            <label className="block">
              <span className="text-xs font-medium text-neutral-600">Holder name</span>
              <input
                value={holderName ?? ''}
                onChange={(e) => onHolderName(e.target.value)}
                maxLength={120}
                placeholder="Prefilled from your profile"
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
              />
            </label>
          )}
          {onBankHint && (
            <div className="block">
              <span className="text-xs font-medium text-neutral-600">I already know the bank</span>
              <BankSelect
                catalog={effectiveCatalog.filter((b) => isSelectable(b.support_state))}
                value={bankHint ?? ''}
                onChange={onBankHint}
                ariaLabel="Bank hint"
                placeholder="Detect automatically"
                showPlaceholder
                className="mt-1 w-full rounded border px-3 py-2 text-sm"
              />
            </div>
          )}
        </div>
      </details>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={() => void onAnalyze()}
          disabled={!fileCount || !!busy}
          className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-40"
        >
          Analyze {fileCount ? `(${fileCount})` : ''}
        </button>
        {busy && <span className="text-sm text-gray-600">{busy}</span>}
      </div>

      <BankSupportPanel catalog={effectiveCatalog} />

      {error && (
        <div role="alert" className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}
    </div>
  )
}
