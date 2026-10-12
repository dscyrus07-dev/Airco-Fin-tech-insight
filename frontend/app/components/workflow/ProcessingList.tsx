'use client'

import ProcessingStep from '../processing/ProcessingStep'
import type { WorkflowDoc } from '@/app/hooks/useStatementWorkflow'

interface ProcessingListProps {
  docs: WorkflowDoc[]
}

/** One ProcessingStep per confirmed file — jobs run in parallel on the backend. */
export default function ProcessingList({ docs }: ProcessingListProps) {
  const active = docs.filter((d) => d.document.workflow_status === 'PROCESSING' && d.document.job_id)
  if (!active.length) return null
  return (
    <div className="w-full min-w-0 space-y-4">
      {active.length > 1 && (
        <p className="text-sm text-neutral-600">Processing {active.length} statements in parallel…</p>
      )}
      {active.map(({ document: d }) => (
        <div key={d.document_id} className="rounded-2xl border border-border p-4 shadow-sm sm:p-6">
          <p className="mb-2 truncate text-sm font-medium">{d.filename}</p>
          <ProcessingStep
            key={d.job_id ?? d.document_id}
            jobId={d.job_id}
            mode="free"
            fileName={d.filename}
            bankName={d.effective_bank?.name || d.bank?.name || null}
            onComplete={() => {}}
            onError={() => {}}
          />
        </div>
      ))}
    </div>
  )
}
