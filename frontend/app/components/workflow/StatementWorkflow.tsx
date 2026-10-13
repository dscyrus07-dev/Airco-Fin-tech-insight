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
      <div className="mb-8 flex items-center justify-center gap-1.5">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="flex flex-col items-center">
              <div className={`h-1 w-10 rounded-full transition-colors ${i <= stepIdx ? 'bg-black' : 'bg-neutral-200'}`} />
              <span className={`mt-1 text-[9px] ${i <= stepIdx ? 'text-neutral-600' : 'text-neutral-300'}`}>{label}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-border p-4 shadow-sm sm:p-6 lg:p-10">
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
                className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-800"
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
