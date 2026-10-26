'use client'

import { useRef, useState } from 'react'
import type { BankCatalogEntry, BankOption, OcrCatalog } from '@/lib/statementsApi'
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
  ocr?: OcrCatalog | null
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
  ocr,
}: UploadDropzoneProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const effectiveCatalog = catalog?.length ? catalog : catalogFromBanks(banks)

  return (
    <div className="w-full min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#01275C] dark:text-white">Analyze statements</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Upload one or more bank statement PDFs. We detect the bank and layout first; nothing is processed until you
            confirm.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          <span className="rounded-full border border-[#A1B2CE]/50 bg-[#01275C]/5 px-3 py-1 text-[#01275C] dark:border-blue-400/30 dark:bg-blue-950/60 dark:text-blue-200">
            Up to 20 PDFs / batch
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 dark:border-slate-700 dark:bg-slate-800/80">
            7-day auto-delete
          </span>
        </div>
      </div>

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
        className={`mt-6 flex flex-col items-center justify-center cursor-pointer rounded-2xl border-2 border-dashed px-6 py-11 text-center transition-all duration-300 ${
          dragOver
            ? 'scale-[1.005] border-[#01275C] bg-[#01275C]/5 dark:border-blue-400 dark:bg-blue-950/40'
            : 'border-[#A1B2CE]/70 bg-slate-50/70 hover:border-[#01275C] hover:bg-[#01275C]/[0.03] dark:border-slate-700 dark:bg-[#08152B]/70 dark:hover:border-blue-400/70 dark:hover:bg-blue-950/30'
        }`}
      >
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#01275C] text-white shadow-sm ring-4 ring-[#A1B2CE]/30 dark:bg-blue-600 dark:ring-blue-400/20">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <p className="text-base font-semibold text-slate-900 dark:text-white">Drop up to 20 PDF statements here</p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">or click to choose files</p>
        {fileCount > 0 && (
          <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#01275C] px-3.5 py-1 text-xs font-semibold text-white dark:bg-blue-600">
            {fileCount} PDF{fileCount === 1 ? '' : 's'} selected — ready to analyze
          </span>
        )}
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

      <details
        className="mt-4 rounded-xl border border-slate-200/90 bg-slate-50/50 px-4 py-3.5 dark:border-slate-700/80 dark:bg-[#08152B]/60"
        open={detailsOpen}
      >
        <summary
          className="cursor-pointer text-sm font-semibold text-slate-700 dark:text-slate-200"
          onClick={(e) => {
            e.preventDefault()
            setDetailsOpen((o) => !o)
          }}
        >
          Details (optional)
        </summary>
        <div className="mt-3.5 grid gap-4 sm:grid-cols-2">
          {onHolderName && (
            <label className="block">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Holder name</span>
              <input
                value={holderName ?? ''}
                onChange={(e) => onHolderName(e.target.value)}
                maxLength={120}
                placeholder="Prefilled from your profile"
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-900 shadow-2xs dark:border-slate-700 dark:bg-[#0B1B36] dark:text-slate-100"
              />
            </label>
          )}
          {onBankHint && (
            <div className="block">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">I already know the bank</span>
              <BankSelect
                catalog={effectiveCatalog.filter((b) => isSelectable(b.support_state))}
                value={bankHint ?? ''}
                onChange={onBankHint}
                ariaLabel="Bank hint"
                placeholder="Detect automatically"
                showPlaceholder
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm text-slate-900 shadow-2xs dark:border-slate-700 dark:bg-[#0B1B36] dark:text-slate-100"
              />
            </div>
          )}
        </div>
      </details>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={() => void onAnalyze()}
          disabled={!fileCount || !!busy}
          className="btn-primary rounded-xl px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-45"
        >
          Analyze {fileCount ? `(${fileCount})` : ''}
        </button>
        {busy && <span className="text-sm font-medium text-[#01275C] dark:text-blue-300">{busy}</span>}
      </div>

      <BankSupportPanel catalog={effectiveCatalog} ocr={ocr} />

      {error && (
        <div role="alert" className="mt-4 rounded-xl border border-red-300 bg-red-50 p-3.5 text-sm text-red-800 dark:border-red-800/60 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </div>
      )}
    </div>
  )
}
