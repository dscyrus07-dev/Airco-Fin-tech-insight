'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AnalysisView,
  AnalyzedDocument,
  BankOption,
  Decision,
  JobStatus,
  StatementsApiError,
  analyzeStatements,
  confirmDocuments,
  getJob,
  listBanks,
  processConfirmed,
  unlockDocument,
} from '@/lib/statementsApi'
import { FALLBACK_BANK_LIST } from '@/lib/banks'

export type WorkflowStep = 'upload' | 'review' | 'processing' | 'report'

export interface WorkflowDoc {
  document: AnalyzedDocument
  job: JobStatus | null
  accountType: string
  statementLabel: string
  override: string
}

export interface StatementWorkflowState {
  step: WorkflowStep
  docs: WorkflowDoc[]
  banks: BankOption[]
  busy: string | null
  error: string | null
  allDone: boolean
  anyFailed: boolean
  pickFiles: (list: FileList | null) => void
  fileCount: number
  analyze: () => Promise<void>
  setOverride: (documentId: string, bankId: string) => void
  setAccountType: (documentId: string, value: string) => void
  setStatementLabel: (documentId: string, value: string) => void
  setPassword: (documentId: string, value: string) => void
  passwords: Record<string, string>
  confirmOne: (doc: AnalyzedDocument, accountType?: string) => Promise<void>
  confirmAllDetected: () => Promise<void>
  unlock: (doc: AnalyzedDocument) => Promise<void>
  process: (opts?: { fullName?: string }) => Promise<void>
  reset: () => void
  reload: () => void
}

const MAX_FILES = 20
const TERMINAL = ['completed', 'failed', 'cancelled']

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong. Please try again.'
}

export function useStatementWorkflow(onJobsSettled?: () => void): StatementWorkflowState {
  const [step, setStep] = useState<WorkflowStep>('upload')
  const [analysis, setAnalysis] = useState<AnalysisView | null>(null)
  const [banks, setBanks] = useState<BankOption[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [accountTypes, setAccountTypes] = useState<Record<string, string>>({})
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [passwords, setPasswords] = useState<Record<string, string>>({})
  const [jobs, setJobs] = useState<Record<string, JobStatus | null>>({})
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const settledCb = useRef(onJobsSettled)
  useEffect(() => {
    settledCb.current = onJobsSettled
  }, [onJobsSettled])

  useEffect(() => {
    listBanks()
      .then((list) => setBanks(list?.length ? list : FALLBACK_BANK_LIST))
      .catch(() => setBanks(FALLBACK_BANK_LIST))
    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [])

  const run = useCallback(async (label: string, fn: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setBusy(null)
    }
  }, [])

  const pickFiles = useCallback((list: FileList | null) => {
    const picked = Array.from(list || []).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setFiles(picked.slice(0, MAX_FILES))
    setAnalysis(null)
    setJobs({})
    setStep('upload')
    if ((list?.length || 0) > picked.length) setError('Only PDF files are accepted; other files were skipped.')
  }, [])

  const analyze = useCallback(
    () =>
      run('Analyzing statements…', async () => {
        try {
          setAnalysis(await analyzeStatements(files))
          setStep('review')
        } catch (e) {
          // expired/unknown analysis ids come back 404/410 — back to upload with a message
          if (e instanceof StatementsApiError && (e.status === 404 || e.status === 410)) {
            setStep('upload')
            setError('This analysis session expired. Please start again.')
            return
          }
          throw e
        }
      }),
    [run, files]
  )

  const docs = analysis?.documents ?? []

  const confirmOne = useCallback(
    (doc: AnalyzedDocument, accountType?: string) =>
      run('Saving…', async () => {
        if (!analysis) return
        const bank = overrides[doc.document_id]
        const detectedId = doc.bank?.id
        const decision: Decision =
          bank && bank !== detectedId
            ? { document_id: doc.document_id, action: 'OVERRIDE', bank_id: bank }
            : { document_id: doc.document_id, action: 'CONFIRM' }
        const at = accountType ?? accountTypes[doc.document_id]
        if (at) decision.account_type = at
        setAnalysis(await confirmDocuments(analysis.analysis_id, [decision]))
      }),
    [run, analysis, overrides, accountTypes]
  )

  const confirmAllDetected = useCallback(
    () =>
      run('Confirming…', async () => {
        if (!analysis) return
        setAnalysis(await confirmDocuments(analysis.analysis_id, [], true))
      }),
    [run, analysis]
  )

  const unlock = useCallback(
    (doc: AnalyzedDocument) =>
      run('Unlocking…', async () => {
        if (!analysis) return
        const res = await unlockDocument(analysis.analysis_id, doc.document_id, passwords[doc.document_id] || '')
        setPasswords((p) => ({ ...p, [doc.document_id]: '' }))
        setAnalysis({
          ...analysis,
          documents: analysis.documents.map((d) => (d.document_id === doc.document_id ? res.document : d)),
        })
      }),
    [run, analysis, passwords]
  )

  const poll = useCallback((ids: string[]) => {
    if (timer.current) clearInterval(timer.current)
    timer.current = setInterval(async () => {
      const next: Record<string, JobStatus | null> = {}
      await Promise.all(
        ids.map(async (id) => {
          try {
            next[id] = await getJob(id)
          } catch {
            next[id] = null
          }
        })
      )
      setJobs((j) => ({ ...j, ...next }))
      const done = ids.every((id) => next[id] && TERMINAL.includes(next[id]!.status))
      if (done) {
        if (timer.current) clearInterval(timer.current)
        setStep((st) => (st === 'processing' ? 'report' : st))
        settledCb.current?.()
      }
    }, 2500)
  }, [])

  const process = useCallback(
    (opts?: { fullName?: string }) =>
      run('Starting processing…', async () => {
        if (!analysis) return
        const confirmed = analysis.documents.filter((d) => d.workflow_status === 'CONFIRMED')
        const perDocument: Record<string, { account_type?: string; statement_label?: string }> = {}
        confirmed.forEach((d) => {
          const at = accountTypes[d.document_id]
          const lb = labels[d.document_id]
          if (at || lb) perDocument[d.document_id] = { ...(at ? { account_type: at } : {}), ...(lb ? { statement_label: lb } : {}) }
        })
        const res = await processConfirmed(analysis.analysis_id, {
          fullName: opts?.fullName,
          perDocument,
        })
        const map: Record<string, string> = {}
        res.started.forEach((s) => (map[s.document_id] = s.job_id))
        setAnalysis({
          ...analysis,
          documents: analysis.documents.map((d) =>
            map[d.document_id] ? { ...d, job_id: map[d.document_id], workflow_status: 'PROCESSING' } : d
          ),
        })
        if (res.started.length) {
          setStep('processing')
          poll(res.started.map((s) => s.job_id))
        }
      }),
    [run, analysis, accountTypes, labels, poll]
  )

  const allDone = docs.length > 0 && docs.every((d) => !d.job_id || TERMINAL.includes(jobs[d.job_id]?.status || ''))
  const anyFailed = docs.some((d) => d.job_id && jobs[d.job_id]?.status === 'failed')

  const reset = useCallback(() => {
    if (timer.current) clearInterval(timer.current)
    setFiles([])
    setAnalysis(null)
    setJobs({})
    setOverrides({})
    setAccountTypes({})
    setLabels({})
    setPasswords({})
    setError(null)
    setStep('upload')
  }, [])

  const wfDocs: WorkflowDoc[] = docs.map((d) => ({
    document: d,
    job: d.job_id ? jobs[d.job_id] ?? null : null,
    accountType: accountTypes[d.document_id] || '',
    statementLabel: labels[d.document_id] || '',
    override: overrides[d.document_id] || '',
  }))

  return {
    step,
    docs: wfDocs,
    banks,
    busy,
    error,
    allDone,
    anyFailed,
    pickFiles,
    fileCount: files.length,
    analyze,
    setOverride: (id, bankId) => setOverrides((o) => ({ ...o, [id]: bankId })),
    setAccountType: (id, v) => setAccountTypes((a) => ({ ...a, [id]: v })),
    setStatementLabel: (id, v) => setLabels((l) => ({ ...l, [id]: v })),
    setPassword: (id, v) => setPasswords((p) => ({ ...p, [id]: v })),
    passwords,
    confirmOne,
    confirmAllDetected,
    unlock,
    process,
    reset,
    reload: () => settledCb.current?.(),
  }
}
