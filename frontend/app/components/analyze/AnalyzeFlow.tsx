'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AnalysisView,
  AnalyzedDocument,
  BankOption,
  analyzeStatements,
  confirmDocuments,
  downloadJobReport,
  getJob,
  listBanks,
  processConfirmed,
  unlockDocument,
  JobStatus,
} from '../../../lib/statementsApi'
import { FALLBACK_BANK_LIST } from '../../../lib/banks'

const STATE_STYLE: Record<string, string> = {
  DETECTED: 'bg-green-100 text-green-800',
  REVIEW: 'bg-yellow-100 text-yellow-800',
  UNKNOWN: 'bg-gray-200 text-gray-800',
  UNSUPPORTED: 'bg-orange-100 text-orange-800',
  ERROR: 'bg-red-100 text-red-800',
}

const MAX_FILES = 20

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong. Please try again.'
}

export default function AnalyzeFlow() {
  const [files, setFiles] = useState<File[]>([])
  const [analysis, setAnalysis] = useState<AnalysisView | null>(null)
  const [banks, setBanks] = useState<BankOption[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [passwords, setPasswords] = useState<Record<string, string>>({})
  const [jobs, setJobs] = useState<Record<string, JobStatus | null>>({})
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

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

  const onPick = (list: FileList | null) => {
    const picked = Array.from(list || []).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setFiles(picked.slice(0, MAX_FILES))
    setAnalysis(null)
    setJobs({})
    if ((list?.length || 0) > picked.length) setError('Only PDF files are accepted; other files were skipped.')
  }

  const analyze = () =>
    run('Analyzing statements…', async () => {
      setAnalysis(await analyzeStatements(files))
    })

  const confirmOne = (doc: AnalyzedDocument) =>
    run('Saving…', async () => {
      const bank = overrides[doc.document_id]
      if (!analysis) return
      const detectedId = doc.bank?.id
      const decision =
        bank && bank !== detectedId
          ? { document_id: doc.document_id, action: 'OVERRIDE' as const, bank_id: bank }
          : { document_id: doc.document_id, action: 'CONFIRM' as const }
      setAnalysis(await confirmDocuments(analysis.analysis_id, [decision]))
    })

  const confirmAll = () =>
    run('Confirming…', async () => {
      if (analysis) setAnalysis(await confirmDocuments(analysis.analysis_id, [], true))
    })

  const unlock = (doc: AnalyzedDocument) =>
    run('Unlocking…', async () => {
      if (!analysis) return
      const res = await unlockDocument(analysis.analysis_id, doc.document_id, passwords[doc.document_id] || '')
      setPasswords((p) => ({ ...p, [doc.document_id]: '' }))
      setAnalysis({
        ...analysis,
        documents: analysis.documents.map((d) => (d.document_id === doc.document_id ? res.document : d)),
      })
    })

  const poll = (ids: string[]) => {
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
      if (ids.every((id) => next[id] && ['completed', 'failed', 'cancelled'].includes(next[id]!.status))) {
        if (timer.current) clearInterval(timer.current)
      }
    }, 3000)
  }

  const process = () =>
    run('Starting processing…', async () => {
      if (!analysis) return
      const res = await processConfirmed(analysis.analysis_id)
      const ids = res.started.map((s) => s.job_id)
      const map: Record<string, string> = {}
      res.started.forEach((s) => (map[s.document_id] = s.job_id))
      setAnalysis({
        ...analysis,
        documents: analysis.documents.map((d) =>
          map[d.document_id] ? { ...d, job_id: map[d.document_id], workflow_status: 'PROCESSING' } : d
        ),
      })
      if (ids.length) poll(ids)
    })

  const docs = analysis?.documents ?? []
  const confirmedCount = docs.filter((d) => d.workflow_status === 'CONFIRMED').length
  const detectedPending = docs.filter(
    (d) => d.state === 'DETECTED' && d.workflow_status === 'AWAITING_CONFIRMATION' && !d.requires_password
  ).length

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold">Analyze statements</h1>
      <p className="mt-1 text-sm text-gray-600">
        Upload one or more bank statement PDFs. We detect the bank and layout first; nothing is processed until you confirm.
      </p>

      <div className="mt-6 rounded border p-4">
        <input
          type="file"
          accept="application/pdf,.pdf"
          multiple
          onChange={(e) => onPick(e.target.files)}
          aria-label="Select PDF statements"
        />
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={analyze}
            disabled={!files.length || !!busy}
            className="rounded bg-black px-4 py-2 text-white disabled:opacity-40"
          >
            Analyze {files.length ? `(${files.length})` : ''}
          </button>
          {busy && <span className="text-sm text-gray-600">{busy}</span>}
        </div>
        {banks.length > 0 && (
          <p className="mt-3 text-xs text-gray-500">
            Supported banks: {banks.map((b) => b.name).join(', ')}. Other banks stay unprocessed — you can still pick a
            bank manually if one was detected incorrectly.
          </p>
        )}
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {analysis && (
        <div className="mt-6">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {analysis.summary.groups.map((g) => (
              <span key={g.bank_id ?? g.bank_name} className="rounded-full bg-gray-100 px-3 py-1">
                {g.bank_name}: {g.count}
              </span>
            ))}
          </div>

          <div className="mt-4 flex gap-3">
            <button
              onClick={confirmAll}
              disabled={!detectedPending || !!busy}
              className="rounded border border-black px-4 py-2 disabled:opacity-40"
            >
              Confirm all detected ({detectedPending})
            </button>
            <button
              onClick={process}
              disabled={!confirmedCount || !!busy}
              className="rounded bg-black px-4 py-2 text-white disabled:opacity-40"
            >
              Process confirmed ({confirmedCount})
            </button>
          </div>

          <ul className="mt-4 space-y-3">
            {docs.map((d) => {
              const job = d.job_id ? jobs[d.job_id] : null
              const selectable = d.state !== 'ERROR' && d.state !== 'UNSUPPORTED' && !d.requires_password && d.workflow_status === 'AWAITING_CONFIRMATION'
              const detectedListed = Boolean(
                d.bank && d.bank.supported && banks.some((b) => b.id === d.bank!.id)
              )
              const detectedValue = detectedListed ? d.bank!.id : ''
              const selectedBank = overrides[d.document_id] ?? detectedValue
              const manualPick = Boolean(overrides[d.document_id] && overrides[d.document_id] !== detectedValue)
              const canPickBank = selectable && (d.state === 'UNKNOWN' || d.state === 'REVIEW')
              return (
                <li key={d.document_id} className="rounded border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="font-medium">{d.filename}</div>
                      <div className="text-xs text-gray-500">{(d.size_bytes / 1024).toFixed(0)} KB</div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATE_STYLE[d.state] || ''}`}>
                      {d.state}
                    </span>
                  </div>

                  <p className="mt-2 text-sm">{d.message}</p>
                  {d.bank && (
                    <p className="mt-1 text-sm">
                      Bank: <b>{d.bank.name}</b> ({d.bank.confidence.replace('_', ' ').toLowerCase()})
                      {d.layout?.id && d.layout.id !== 'UNKNOWN' && <> · Layout: {d.layout.description}</>}
                    </p>
                  )}
                  {d.hint_conflict && (
                    <p className="mt-1 text-xs text-yellow-800">The selected hint differs from what the PDF shows.</p>
                  )}

                  {d.evidence.length > 0 && (
                    <div className="mt-2 text-sm">
                      <div className="font-medium text-gray-700">Why we think so</div>
                      <ul className="mt-1 list-disc pl-5 text-gray-700">
                        {d.evidence.map((e, i) => (
                          <li key={i}>
                            {e.label || e.kind}
                            {e.value ? <>: <span className="font-mono text-xs">{e.value}</span></> : null}
                            {typeof e.weight === 'number' ? <span className="text-gray-400"> (+{e.weight})</span> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {d.requires_password && (
                    <div className="mt-3 flex gap-2">
                      <input
                        type="password"
                        autoComplete="off"
                        placeholder="PDF password"
                        value={passwords[d.document_id] || ''}
                        onChange={(e) => setPasswords((p) => ({ ...p, [d.document_id]: e.target.value }))}
                        className="rounded border px-2 py-1 text-sm"
                      />
                      <button
                        onClick={() => unlock(d)}
                        disabled={!passwords[d.document_id] || !!busy}
                        className="rounded border px-3 py-1 text-sm disabled:opacity-40"
                      >
                        Unlock
                      </button>
                    </div>
                  )}

                  {d.state === 'UNSUPPORTED' && d.detail_state === 'UNSUPPORTED_SCANNED_PDF' && (
                    <p className="mt-2 rounded bg-orange-50 p-2 text-sm text-orange-900">
                      This statement appears to be scanned or image-based. AirCo currently supports text-based PDF
                      statements, so nothing will be run on it.
                    </p>
                  )}

                  {d.state === 'UNSUPPORTED' && d.detail_state !== 'UNSUPPORTED_SCANNED_PDF' && (
                    <p className="mt-2 rounded bg-orange-50 p-2 text-sm text-orange-900">
                      {d.message || "This bank isn't fully supported yet."}
                    </p>
                  )}

                  {d.state === 'UNKNOWN' && (
                    <p className="mt-2 rounded bg-gray-50 p-2 text-sm text-gray-800">
                      We could not tell which bank issued this statement.
                      {selectable
                        ? ' If you know it, pick the bank below — otherwise this file stays unprocessed.'
                        : ' Nothing will be run on it.'}
                    </p>
                  )}

                  {selectable && manualPick && (
                    <p className="mt-2 rounded bg-yellow-50 p-2 text-sm text-yellow-900">
                      {d.bank
                        ? `You are overriding the automatic detection (${d.bank.name}).`
                        : 'You are selecting a bank manually.'}{' '}
                      If the PDF is not actually from the selected bank, processing may fail validation.
                    </p>
                  )}

                  {selectable && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {canPickBank && (
                        <select
                          value={selectedBank}
                          onChange={(e) => setOverrides((o) => ({ ...o, [d.document_id]: e.target.value }))}
                          className="rounded border px-2 py-1 text-sm"
                          aria-label="Bank"
                        >
                          {!detectedValue && <option value="">Select bank…</option>}
                          {banks.map((b) => (
                            <option key={b.id} value={b.id}>
                              {b.name}{b.v2_served ? ' · verified engine' : ''}
                            </option>
                          ))}
                        </select>
                      )}
                      <button
                        onClick={() => confirmOne(d)}
                        disabled={!!busy || !selectedBank || (d.bank?.supported === false && !manualPick)}
                        className="rounded bg-black px-3 py-1 text-sm text-white disabled:opacity-40"
                      >
                        {manualPick ? 'Use selected bank' : 'Confirm'}
                      </button>
                    </div>
                  )}

                  {d.workflow_status === 'CONFIRMED' && (
                    <p className="mt-2 text-sm text-green-800">Confirmed as {d.effective_bank?.name}. Ready to process.</p>
                  )}
                  {d.workflow_status === 'PROCESSING' && (
                    <div className="mt-2 text-sm">
                      Status: {job?.status ?? 'queued'}
                      {job?.status === 'failed' && <span className="text-red-700"> — {job.error_message || 'failed'}</span>}
                      {job?.status === 'completed' && d.job_id && (
                        <button
                          className="ml-3 underline"
                          onClick={() => run('Downloading…', () => downloadJobReport(d.job_id!, d.filename))}
                        >
                          Download Excel
                        </button>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
