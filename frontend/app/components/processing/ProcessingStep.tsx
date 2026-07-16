'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Layers,
  Loader2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { ProcessingMode, ProcessingResult } from '@/types'

const FREE_MESSAGES = [
  'Extracting transactions from each page…',
  'Detecting bank format and columns…',
  'Running categorization rules…',
  'Detecting recurring patterns…',
  'Building structured Excel report…',
]

const HYBRID_MESSAGES = [
  'Extracting transactions from each page…',
  'Detecting bank format and columns…',
  'Running rule engine…',
  'Classifying with AI…',
  'Validating AI categories…',
  'Building structured Excel report…',
]

const HYGIENE_SCAN_STEPS = [
  'Reading PDF structure…',
  'Detecting bank identity…',
  'Sampling pages for transactions…',
  'Validating statement date range…',
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

/** Visual phase — only one primary panel at a time */
type UiPhase = 'uploading' | 'hygiene' | 'success' | 'processing'

interface ProcessingStepProps {
  jobId?: string | null
  mode?: ProcessingMode
  fileName?: string | null
  bankName?: string | null
  onComplete: (result: ProcessingResult) => void
  onError: (message: string) => void
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
  const [scanIndex, setScanIndex] = useState(0)
  const [pollError, setPollError] = useState('')
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [pendingResult, setPendingResult] = useState<ProcessingResult | null>(null)
  const [uiPhase, setUiPhase] = useState<UiPhase>('uploading')
  const [successAnimDone, setSuccessAnimDone] = useState(false)
  const [elapsedSec, setElapsedSec] = useState(0)

  const messages = mode === 'hybrid' ? HYBRID_MESSAGES : FREE_MESSAGES
  const hygiene = progress?.hygiene
  const hygieneReady = Boolean(progress?.hygiene_complete && hygiene)
  const pageCount = hygiene?.page_count ?? 0
  const isLargePdf = pageCount >= 8

  // Reset on new job
  useEffect(() => {
    setProgress(null)
    setPendingResult(null)
    setPollError('')
    setSuccessAnimDone(false)
    setElapsedSec(0)
    setMessageIndex(0)
    setScanIndex(0)
    setUiPhase(jobId ? 'hygiene' : 'uploading')
  }, [jobId])

  // Phase machine: uploading → hygiene → success (~1s) → processing
  useEffect(() => {
    if (!jobId) {
      setUiPhase('uploading')
      return
    }
    if (!hygieneReady) {
      setUiPhase('hygiene')
      return
    }
    if (!successAnimDone) {
      setUiPhase('success')
      return
    }
    setUiPhase('processing')
  }, [jobId, hygieneReady, successAnimDone])

  // Hold green-tick briefly, then move to PDF processing
  useEffect(() => {
    if (!hygieneReady || successAnimDone) return
    const t = setTimeout(() => setSuccessAnimDone(true), 1000)
    return () => clearTimeout(t)
  }, [hygieneReady, successAnimDone])


  // Rotating scan copy during hygiene
  useEffect(() => {
    if (uiPhase !== 'hygiene' && uiPhase !== 'uploading') return
    const interval = setInterval(() => {
      setScanIndex((prev) => (prev + 1) % HYGIENE_SCAN_STEPS.length)
    }, 1400)
    return () => clearInterval(interval)
  }, [uiPhase])

  // Rotating process copy during PDF processing
  useEffect(() => {
    if (uiPhase !== 'processing') return
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length)
    }, 2800)
    return () => clearInterval(interval)
  }, [uiPhase, messages.length])

  // Elapsed timer while processing (reassures large PDFs)
  useEffect(() => {
    if (uiPhase !== 'processing') return
    const started = Date.now()
    const interval = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - started) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [uiPhase])

  // Poll job
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

  // Complete only after success animation (or grace if no hygiene)
  useEffect(() => {
    if (!pendingResult) return
    if (hygieneReady && !successAnimDone) return
    if (!hygieneReady) {
      const t = setTimeout(() => onComplete(pendingResult), 500)
      return () => clearTimeout(t)
    }
    // Prefer user sees processing phase briefly if job finished very fast
    if (uiPhase === 'success') return
    onComplete(pendingResult)
  }, [pendingResult, hygieneReady, successAnimDone, uiPhase, onComplete])

  const detailRows = useMemo(() => {
    if (!hygiene) return []
    return [
      { label: 'File', value: hygiene.file_name || fileName || '—' },
      { label: 'Bank', value: hygiene.bank_name || bankName || '—' },
      { label: 'Pages', value: String(hygiene.page_count ?? '—') },
      { label: 'Format', value: hygiene.format_id || '—' },
      { label: 'Txns (est.)', value: String(hygiene.transaction_count ?? '—') },
      {
        label: 'Dates',
        value:
          hygiene.start_date && hygiene.end_date
            ? `${hygiene.start_date} → ${hygiene.end_date}`
            : '—',
      },
    ]
  }, [hygiene, fileName, bankName])

  const processSteps = useMemo(() => {
    const stage = (progress?.stage || '').toLowerCase()
    return [
      {
        key: 'parse',
        label: 'Parse transactions',
        active: stage === 'parsing' || stage === 'hygiene_complete' || !stage,
        done: ['report', 'completed'].includes(stage),
      },
      {
        key: 'rules',
        label: mode === 'hybrid' ? 'Rules + AI classify' : 'Apply rule engine',
        active: stage === 'parsing',
        done: ['report', 'completed'].includes(stage),
      },
      {
        key: 'report',
        label: 'Generate Excel report',
        active: stage === 'report',
        done: stage === 'completed',
      },
    ]
  }, [progress?.stage, mode])

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60)
    const r = s % 60
    return m > 0 ? `${m}m ${r}s` : `${r}s`
  }

  return (
    <div className="animate-fade-in space-y-5 py-4">
      {/* Step rail */}
      <div className="mx-auto flex max-w-md items-center justify-center gap-2">
        <StepPill
          n={1}
          label="Hygiene"
          state={
            uiPhase === 'uploading' || uiPhase === 'hygiene'
              ? 'active'
              : 'done'
          }
        />
        <div className="h-px w-8 bg-neutral-200" />
        <StepPill
          n={2}
          label="Process PDF"
          state={
            uiPhase === 'processing'
              ? 'active'
              : uiPhase === 'success'
                ? 'pending'
                : uiPhase === 'hygiene' || uiPhase === 'uploading'
                  ? 'pending'
                  : 'done'
          }
        />
      </div>

      {/* ── PHASE: uploading / hygiene ── */}
      {(uiPhase === 'uploading' || uiPhase === 'hygiene') && (
        <div className="mx-auto max-w-lg animate-fade-in">
          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex flex-col items-center text-center">
              <div className="relative mb-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-neutral-50 ring-1 ring-neutral-200">
                  <ShieldCheck className="h-8 w-8 text-neutral-800" />
                </div>
                <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-black text-white shadow">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                </span>
              </div>
              <h3 className="text-base font-semibold tracking-tight text-black">
                {uiPhase === 'uploading' ? 'Uploading statement' : 'Running hygiene check'}
              </h3>
              <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-neutral-500">
                {uiPhase === 'uploading'
                  ? 'Securely uploading your PDF and preparing validation…'
                  : HYGIENE_SCAN_STEPS[scanIndex]}
              </p>
            </div>

            <div className="space-y-2.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-2.5 overflow-hidden rounded-full bg-neutral-100"
                  style={{ width: `${100 - i * 18}%` }}
                >
                  <div
                    className="h-full animate-pulse rounded-full bg-gradient-to-r from-neutral-200 via-neutral-300 to-neutral-200"
                    style={{ width: '55%', animationDelay: `${i * 120}ms` }}
                  />
                </div>
              ))}
            </div>

            <div className="mt-5 flex items-start gap-2 rounded-xl border border-neutral-100 bg-neutral-50 px-3 py-2.5">
              <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neutral-400" />
              <p className="text-[11px] leading-relaxed text-neutral-500">
                We validate pages, bank format, and structure before full extraction —
                so bad files fail fast.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── PHASE: green tick success ── */}
      {uiPhase === 'success' && (
        <div className="mx-auto max-w-lg animate-fade-in">
          <div className="rounded-2xl border border-emerald-200 bg-gradient-to-b from-emerald-50/80 to-white p-6 shadow-sm">
            <div className="mb-5 flex flex-col items-center text-center">
              <div className="relative mb-4 flex h-20 w-20 items-center justify-center">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-200 opacity-60" />
                <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 shadow-lg shadow-emerald-200">
                  <CheckCircle2 className="h-9 w-9 text-white" strokeWidth={2.25} />
                </div>
              </div>

              <h3 className="text-base font-semibold text-emerald-900">Hygiene check passed</h3>
              <p className="mt-1 text-xs text-emerald-700/80">
                Statement looks valid. Starting full PDF processing…
              </p>
            </div>

            {detailRows.length > 0 && (
              <div className="grid grid-cols-2 gap-2">
                {detailRows.map((row) => (
                  <div
                    key={row.label}
                    className="rounded-lg border border-emerald-100/80 bg-white/80 px-3 py-2"
                  >
                    <p className="text-[10px] font-medium uppercase tracking-wide text-emerald-600/70">
                      {row.label}
                    </p>
                    <p className="mt-0.5 truncate text-xs font-medium text-neutral-900" title={row.value}>
                      {row.value}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {!!hygiene?.warnings?.length && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase text-amber-800">
                  <AlertTriangle className="h-3 w-3" /> Warnings
                </p>
                <ul className="space-y-0.5">
                  {hygiene.warnings.map((w) => (
                    <li key={w} className="text-xs text-amber-900">
                      • {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── PHASE: PDF processing ── */}
      {uiPhase === 'processing' && (
        <div className="mx-auto max-w-lg animate-fade-in">
          <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex flex-col items-center text-center">
              <div className="relative mb-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-neutral-900 text-white shadow-md">
                  <Layers className="h-7 w-7 animate-pulse" />
                </div>
              </div>
              <h3 className="text-base font-semibold tracking-tight text-black">
                Processing your PDF
              </h3>
              <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-neutral-500">
                {progress?.message || messages[messageIndex]}
              </p>
              <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-0.5 text-[10px] font-medium text-neutral-600">
                  {mode === 'hybrid' ? 'System + AI' : 'Free mode'}
                </span>
                <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-0.5 text-[10px] font-medium tabular-nums text-neutral-600">
                  {formatElapsed(elapsedSec)}
                </span>
                {pageCount > 0 && (
                  <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-0.5 text-[10px] font-medium text-neutral-600">
                    {pageCount} page{pageCount === 1 ? '' : 's'}
                  </span>
                )}
              </div>
            </div>

            {/* Progress steps */}
            <div className="space-y-2.5">
              {processSteps.map((step, idx) => (
                <div
                  key={step.key}
                  className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors ${
                    step.done
                      ? 'border-emerald-200 bg-emerald-50/50'
                      : step.active
                        ? 'border-neutral-300 bg-neutral-50'
                        : 'border-neutral-100 bg-white'
                  }`}
                >
                  <div
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                      step.done
                        ? 'bg-emerald-500 text-white'
                        : step.active
                          ? 'bg-black text-white'
                          : 'bg-neutral-100 text-neutral-400'
                    }`}
                  >
                    {step.done ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : step.active ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      idx + 1
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-xs font-medium ${
                        step.done || step.active ? 'text-black' : 'text-neutral-400'
                      }`}
                    >
                      {step.label}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Large PDF notice */}
            <div
              className={`mt-4 flex items-start gap-2.5 rounded-xl border px-3 py-2.5 ${
                isLargePdf
                  ? 'border-amber-200 bg-amber-50'
                  : 'border-neutral-100 bg-neutral-50'
              }`}
            >
              <Sparkles
                className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                  isLargePdf ? 'text-amber-600' : 'text-neutral-400'
                }`}
              />
              <p
                className={`text-[11px] leading-relaxed ${
                  isLargePdf ? 'text-amber-900' : 'text-neutral-500'
                }`}
              >
                {isLargePdf
                  ? `This is a larger statement (${pageCount} pages). Extraction can take a minute or two — please keep this tab open.`
                  : 'Larger multi-page PDFs take longer. We extract every transaction carefully for accuracy.'}
              </p>
            </div>

            {/* Compact hygiene summary chip */}
            {hygiene && (
              <div className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>
                  Hygiene passed
                  {hygiene.bank_name ? ` · ${hygiene.bank_name}` : ''}
                  {hygiene.transaction_count != null
                    ? ` · ~${hygiene.transaction_count} txns`
                    : ''}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {(fileName || bankName) && (
        <div className="flex items-center justify-center gap-2 text-xs text-neutral-400">
          <FileText className="h-3.5 w-3.5" />
          <span className="truncate max-w-xs">
            {bankName ? `${bankName} · ` : ''}
            {fileName || 'Statement PDF'}
          </span>
        </div>
      )}

      {pollError && <p className="text-center text-xs text-red-600">{pollError}</p>}
    </div>
  )
}


function StepPill({
  n,
  label,
  state,
}: {
  n: number
  label: string
  state: 'pending' | 'active' | 'done'
}) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
        state === 'active'
          ? 'border-black bg-black text-white'
          : state === 'done'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : 'border-neutral-200 bg-white text-neutral-400'
      }`}
    >
      {state === 'done' ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <span
          className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold ${
            state === 'active' ? 'bg-white/20 text-white' : 'bg-neutral-100 text-neutral-400'
          }`}
        >
          {n}
        </span>
      )}
      {label}
    </div>
  )
}
