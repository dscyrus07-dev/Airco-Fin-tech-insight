'use client'

import { useEffect, useState } from 'react'
import ResultStep from '../results/ResultStep'
import { ProcessingResult } from '@/types'
import { getJob } from '@/lib/statementsApi'
import type { WorkflowDoc } from '@/app/hooks/useStatementWorkflow'

interface ReportListProps {
  docs: WorkflowDoc[]
}

/** Per-file report: the existing ResultStep fed from the job's result_data. */
export default function ReportList({ docs }: ReportListProps) {
  const finished = docs.filter((d) => d.document.job_id && d.job?.status === 'completed')
  const failed = docs.filter((d) => d.document.job_id && d.job?.status === 'failed')
  const [results, setResults] = useState<Record<string, ProcessingResult>>({})
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const missing = finished.filter(({ document: d }) => d.job_id && !results[d.job_id])
    if (!missing.length) return
    missing.forEach(async ({ document: d }) => {
      try {
        const job = await getJob(d.job_id!)
        // apply even if a later effect run started: keyed by job_id, harmless
        if (job.result_data) setResults((r) => ({ ...r, [d.job_id!]: job.result_data as unknown as ProcessingResult }))
      } catch {
        // history-backed row may lag; retried below
      }
    })
    const t = setTimeout(() => setRetry((n) => n + 1), 2500)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished.map((f) => f.document.job_id).join(','), retry])

  if (!finished.length && !failed.length) return null

  return (
    <div className="w-full min-w-0 space-y-6">
      {failed.length > 0 && (
        <div className="rounded border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Some statements could not be processed:</p>
          <ul className="mt-2 space-y-1 text-sm text-red-700">
            {failed.map(({ document: d, job }) => (
              <li key={d.document_id}>
                {d.filename} — {job?.error_message || 'processing failed'}
              </li>
            ))}
          </ul>
        </div>
      )}
      {finished.map(({ document: d }) => {
        const result = d.job_id ? results[d.job_id] : undefined
        return (
          <div key={d.document_id} className="rounded-2xl border border-border p-4 shadow-sm sm:p-6">
            <p className="mb-3 truncate text-sm font-medium">{d.filename}</p>
            {result ? (
              <ResultStep result={result} />
            ) : (
              <p className="text-sm text-neutral-500">Report is being prepared…</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
