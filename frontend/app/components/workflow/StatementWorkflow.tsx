'use client'

import { useState } from 'react'
import { useStatementWorkflow } from '@/app/hooks/useStatementWorkflow'
import UploadDropzone from './UploadDropzone'
import ReviewTable from './ReviewTable'
import ProcessingList from './ProcessingList'
import ReportList from './ReportList'

const STEPS = ['Upload', 'Review', 'Processing', 'Report'] as const

interface StatementWorkflowProps {
  profileName?: string
  onJobsSettled?: () => void
}

/** Unified single entry: Upload → Review → Processing → Report. */
export default function StatementWorkflow({ profileName, onJobsSettled }: StatementWorkflowProps) {
  const wf = useStatementWorkflow(onJobsSettled)
  const [holderName, setHolderName] = useState(profileName || '')
  const [bankHint, setBankHint] = useState('')
  const ORDER: Record<string, number> = { upload: 0, review: 1, processing: 2, report: 3 }
  const stepIdx = ORDER[wf.step] ?? 0

  return (
    <section className="w-full min-w-0">
      <ol className="mb-6 flex items-center" aria-label="Progress">
        {STEPS.map((label, i) => (
          <li key={label} className={`flex items-center ${i < STEPS.length - 1 ? 'flex-1' : ''}`}>
            <div className="flex flex-col items-center">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-all duration-300 ${
                  i < stepIdx
                    ? 'bg-emerald-500 text-white'
                    : i === stepIdx
                      ? 'bg-indigo-600 text-white ring-4 ring-indigo-100'
                      : 'bg-slate-100 text-slate-400'
                }`}
              >
                {i < stepIdx ? '\u2713' : i + 1}
              </span>
              <span className={`mt-1.5 text-[11px] font-medium ${i <= stepIdx ? 'text-slate-700' : 'text-slate-400'}`}>{label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="mx-2 mb-5 h-0.5 flex-1 rounded-full bg-slate-100">
                <div className={`h-full rounded-full bg-emerald-400 transition-all duration-500 ${i < stepIdx ? 'w-full' : 'w-0'}`} />
              </div>
            )}
          </li>
        ))}
      </ol>

      <div className="card-surface animate-fade-up p-5 sm:p-7 lg:p-9">
        {wf.error && wf.step !== 'upload' && (
          <div role="alert" className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-700">{wf.error}</p>
          </div>
        )}

        {wf.step === 'upload' && (
          <UploadDropzone
            onFiles={wf.pickFiles}
            fileCount={wf.fileCount}
            onAnalyze={wf.analyze}
            busy={wf.busy}
            error={wf.error}
            banks={wf.banks}
            catalog={wf.catalog}
            holderName={holderName}
            onHolderName={setHolderName}
            bankHint={bankHint}
            onBankHint={setBankHint}
          />
        )}

        {wf.step === 'review' && (
          <ReviewTable
            docs={wf.docs}
            banks={wf.banks}
            catalog={wf.catalog}
            busy={wf.busy}
            passwords={wf.passwords}
            onOverride={wf.setOverride}
            onAccountType={wf.setAccountType}
            onStatementLabel={wf.setStatementLabel}
            onPassword={wf.setPassword}
            onConfirmOne={wf.confirmOne}
            onConfirmAll={wf.confirmAllDetected}
            onUnlock={wf.unlock}
            onProcess={() => wf.process({ fullName: holderName || undefined })}
          />
        )}

        {wf.step === 'processing' && <ProcessingList docs={wf.docs} />}

        {wf.step === 'report' && (
          <>
            <ReportList docs={wf.docs} />
            <div className="mt-6 flex items-center justify-end border-t border-neutral-100 pt-4">
              <button
                onClick={wf.reset}
                className="btn-primary rounded-lg px-4 py-2 text-sm font-semibold"
              >
                New Statement
              </button>
            </div>
          </>
        )}

        {wf.step !== 'processing' && wf.step !== 'report' && wf.step !== 'upload' && (
          <div className="mt-6 border-t border-neutral-100 pt-4">
            <button
              onClick={wf.reset}
              className="text-sm text-neutral-500 transition-colors hover:text-black"
            >
              Start over
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
