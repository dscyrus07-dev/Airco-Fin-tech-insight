'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Loader2,
  ShieldCheck,
} from 'lucide-react'
import { ProcessingMode, ProcessingResult } from '@/types'

const FREE_MESSAGES = [
  'Extracting transactions...',
  'Detecting bank format...',
  'Running rule engine...',
  'Categorizing transactions...',
  'Detecting recurring patterns...',
  'Generating structured report...',
]

const HYBRID_MESSAGES = [
  'Extracting transactions...',
  'Detecting bank format...',
  'Running rule engine...',
  'Classifying with AI...',
  'Validating AI categories...',
  'Detecting recurring patterns...',
  'Generating structured report...',
]

type HygieneProgress = {
  is_healthy?: boolean
  file_name?: string
  page_count?: number
  bank_name?: string
  format_id?: string
  transaction_count?: number
  start_date?: string
  end_date?: string
  issues?: string[]
  warnings?: string[]
}

type JobProgress = {
  stage?: string
  message?: string
  hygiene?: HygieneProgress
  hygiene_complete?: boolean
  updated_at?: string
}

interface ProcessingStepProps {
  jobId?: string | null
  mode?: ProcessingMode
  fileName?: string | null
  bankName?: string | null
  onComplete: (result: ProcessingResult) => void
  onError: (message: string) => void
}

function stageLabel(stage?: string, hasJob?: boolean): string {
  if (!hasJob) return 'Uploading PDF…'
  switch ((stage || '').toLowerCase()) {
    case 'queued':
      return 'Job queued'
    case 'hygiene':
      return 'Hygiene check in progress'
    case 'hygiene_complete':
      return 'Hygiene check complete'
    case 'parsing':
      return 'Parsing transactions'
    case 'report':
      return 'Generating Excel report'
    case 'completed':
      return 'Completed'
    default:
      return 'Processing statement'
  }
}

export default function ProcessingStep({
  jobId,
  mode = 'free',
  fileName,
  bankName,
  onComplete,
  onError,
}: ProcessingStepProps) {
  const [messageIndex, setMessageIndex] = useState(0)
  const [pollError, setPollError] = useState('')
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [hygieneHoldDone, setHygieneHoldDone] = useState(false)
  const [pendingResult, setPendingResult] = useState<ProcessingResult | null>(null)
  const messages = mode === 'hybrid' ? HYBRID_MESSAGES : FREE_MESSAGES

  const hygiene = progress?.hygiene
  const hygieneReady = Boolean(progress?.hygiene_complete && hygiene)

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length)
    }, 2500)
    return () => clearInterval(interval)
  }, [messages.length])

  useEffect(() => {
    if (!hygieneReady || hygieneHoldDone) return
    const t = setTimeout(() => setHygieneHoldDone(true), 900)
    return () => clearTimeout(t)
  }, [hygieneReady, hygieneHoldDone])

  // Reset per-job UI state when a new job starts
  useEffect(() => {
    setProgress(null)
    setHygieneHoldDone(false)
    setPendingResult(null)
    setPollError('')
  }, [jobId])

  useEffect(() => {
    if (!jobId) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const poll = async () => {
      try {
        const { getValidSessionAccessToken } = await import('../../../lib/sessionToken')
        const token = await getValidSessionAccessToken()
        const response = await fetch(`/api/jobs/${jobId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        })
        const data = await response.json().catch(() => ({}))

        if (!response.ok) {
          throw new Error(data.message || 'Failed to fetch job status.')
        }

        const status = String(data.status || '').toLowerCase()
        const resultData = (data.result_data || {}) as Record<string, unknown>
        const liveProgress = (resultData.progress || null) as JobProgress | null
        if (liveProgress && !cancelled) {
          setProgress(liveProgress)
        } else if (resultData.hygiene && !cancelled) {
          setProgress({
            stage: status === 'completed' ? 'completed' : 'hygiene_complete',
            message: status === 'completed' ? 'Processing complete' : 'Hygiene check complete',
            hygiene: resultData.hygiene as HygieneProgress,
            hygiene_complete: true,
          })
        }

        if (status === 'completed' && data.result_data) {
          if (!cancelled) setPendingResult(data.result_data as ProcessingResult)
          return
        }

        if (status === 'failed' || status === 'cancelled') {
          throw new Error(data.error_message || 'Processing failed.')
        }

        if (!cancelled) {
          timer = setTimeout(poll, 1000)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Processing failed.'
        if (!cancelled) {
          setPollError(message)
          onError(message)
        }
      }
    }

    poll()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [jobId, onError])

  useEffect(() => {
    if (!pendingResult) return
    // Show green tick briefly when hygiene details are available
    if (hygieneReady && !hygieneHoldDone) return
    // If hygiene never arrives, wait a short grace period then proceed
    if (!hygieneReady) {
      const t = setTimeout(() => onComplete(pendingResult), 400)
      return () => clearTimeout(t)
    }
    onComplete(pendingResult)
  }, [pendingResult, hygieneReady, hygieneHoldDone, onComplete])


  const detailRows = useMemo(() => {
    if (!hygiene) return []
    return [
      { label: 'File', value: hygiene.file_name || fileName || '—' },
      { label: 'Bank', value: hygiene.bank_name || bankName || '—' },
      { label: 'Pages', value: String(hygiene.page_count ?? '—') },
      { label: 'Format ID', value: hygiene.format_id || '—' },
      { label: 'Transactions (est.)', value: String(hygiene.transaction_count ?? '—') },
      {
        label: 'Date range',
        value:
          hygiene.start_date && hygiene.end_date
            ? `${hygiene.start_date} → ${hygiene.end_date}`
            : '—',
      },
    ]
  }, [hygiene, fileName, bankName])

  const currentStage = !jobId ? 'uploading' : progress?.stage || 'running'
  const statusText =
    progress?.message ||
    (!jobId
      ? 'Uploading your PDF and creating a processing job…'
      : messages[messageIndex])

  return (
    <div className="animate-fade-in space-y-5 py-6">
      <div className="flex flex-col items-center text-center">
        {!hygieneReady ? (
          <Loader2 className="mb-4 h-10 w-10 animate-spin text-black" />
        ) : (
          <CheckCircle2 className="mb-4 h-10 w-10 text-emerald-600" />
        )}
        <p className="text-sm font-semibold text-black">
          {stageLabel(currentStage, Boolean(jobId))}
        </p>
        <p className="mt-1 max-w-md text-xs text-neutral-500">{statusText}</p>
        <div className="mt-3 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1">
          <span className="text-[10px] font-medium text-neutral-500">
            {mode === 'hybrid' ? 'System + AI Mode' : 'Free Mode (System Only)'}
          </span>
        </div>
        {jobId && (
          <p className="mt-2 font-mono text-[10px] text-neutral-300">
            job: {jobId.slice(0, 16)}…
          </p>
        )}
      </div>

      <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-neutral-700" />
            <h3 className="text-sm font-semibold text-black">Hygiene Check</h3>
          </div>
          {hygieneReady ? (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                hygiene?.is_healthy
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border border-amber-200'
              }`}
            >
              {hygiene?.is_healthy ? (
                <>
                  <CheckCircle2 className="h-3 w-3" /> Passed
                </>
              ) : (
                <>
                  <AlertTriangle className="h-3 w-3" /> Warnings
                </>
              )}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] font-medium text-neutral-500">
              <Loader2 className="h-3 w-3 animate-spin" /> Checking…
            </span>
          )}
        </div>

        {!hygieneReady ? (
          <div className="space-y-2">
            <div className="h-3 w-2/3 animate-pulse rounded bg-neutral-100" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-neutral-100" />
            <div className="h-3 w-3/4 animate-pulse rounded bg-neutral-100" />
            <p className="pt-2 text-xs text-neutral-400">
              Validating PDF pages, bank format, and statement structure…
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {detailRows.map((row) => (
                <div
                  key={row.label}
                  className="rounded-lg border border-neutral-100 bg-neutral-50 px-3 py-2"
                >
                  <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-400">
                    {row.label}
                  </p>
                  <p className="mt-0.5 truncate text-xs font-medium text-black" title={row.value}>
                    {row.value}
                  </p>
                </div>
              ))}
            </div>

            {!!hygiene?.issues?.length && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                  Issues
                </p>
                <ul className="space-y-1">
                  {hygiene.issues.map((issue) => (
                    <li key={issue} className="text-xs text-amber-900">
                      • {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!!hygiene?.warnings?.length && (
              <div className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
                  Warnings
                </p>
                <ul className="space-y-1">
                  {hygiene.warnings.map((warning) => (
                    <li key={warning} className="text-xs text-neutral-600">
                      • {warning}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center gap-2 rounded-lg border border-emerald-100 bg-emerald-50/60 px-3 py-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <p className="text-xs text-emerald-800">
                Hygiene check confirmed. Continuing with transaction extraction and report generation…
              </p>
            </div>
          </div>
        )}
      </div>

      {(fileName || bankName) && (
        <div className="flex items-center justify-center gap-2 text-xs text-neutral-400">
          <FileText className="h-3.5 w-3.5" />
          <span>
            {bankName ? `${bankName} · ` : ''}
            {fileName || 'Statement PDF'}
          </span>
        </div>
      )}

      {pollError && <p className="text-center text-xs text-red-600">{pollError}</p>}
    </div>
  )
}
