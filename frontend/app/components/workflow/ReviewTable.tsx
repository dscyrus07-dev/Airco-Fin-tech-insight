'use client'

import { AnalyzedDocument, BankOption } from '@/lib/statementsApi'
import type { WorkflowDoc } from '@/app/hooks/useStatementWorkflow'

const STATE_STYLE: Record<string, string> = {
  DETECTED: 'bg-green-100 text-green-800',
  REVIEW: 'bg-yellow-100 text-yellow-800',
  UNKNOWN: 'bg-gray-200 text-gray-800',
  UNSUPPORTED: 'bg-orange-100 text-orange-800',
  ERROR: 'bg-red-100 text-red-800',
}

const ACCOUNT_TYPES = [
  { value: '', label: 'Auto-detect' },
  { value: 'salaried', label: 'Salaried' },
  { value: 'business', label: 'Business' },
]

interface ReviewTableProps {
  docs: WorkflowDoc[]
  banks: BankOption[]
  busy: string | null
  passwords: Record<string, string>
  onOverride: (documentId: string, bankId: string) => void
  onAccountType: (documentId: string, value: string) => void
  onStatementLabel: (documentId: string, value: string) => void
  onPassword: (documentId: string, value: string) => void
  onConfirmOne: (doc: AnalyzedDocument, accountType?: string) => Promise<void>
  onConfirmAll: () => Promise<void>
  onUnlock: (doc: AnalyzedDocument) => Promise<void>
  onProcess: () => Promise<void>
}

export default function ReviewTable({
  docs,
  banks,
  busy,
  passwords,
  onOverride,
  onAccountType,
  onStatementLabel,
  onPassword,
  onConfirmOne,
  onConfirmAll,
  onUnlock,
  onProcess,
}: ReviewTableProps) {
  const confirmedCount = docs.filter((d) => d.document.workflow_status === 'CONFIRMED').length
  const detectedPending = docs.filter(
    (d) => d.document.state === 'DETECTED' && d.document.workflow_status === 'AWAITING_CONFIRMATION' && !d.document.requires_password
  ).length

  return (
    <div className="w-full min-w-0">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {summaryGroups(docs).map((g) => (
          <span key={g.key} className="rounded-full bg-gray-100 px-3 py-1">
            {g.name}: {g.count}
          </span>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          onClick={() => void onConfirmAll()}
          disabled={!detectedPending || !!busy}
          className="rounded border border-black px-4 py-2 text-sm disabled:opacity-40"
        >
          Confirm all detected ({detectedPending})
        </button>
        <button
          onClick={() => void onProcess()}
          disabled={!confirmedCount || !!busy}
          className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-40"
        >
          Process confirmed ({confirmedCount})
        </button>
      </div>

      <ul className="mt-4 space-y-3">
        {docs.map(({ document: d, override, accountType, statementLabel }) => {
          const selectable = d.state !== 'ERROR' && d.state !== 'UNSUPPORTED' && !d.requires_password && d.workflow_status === 'AWAITING_CONFIRMATION'
          const detectedListed = Boolean(
            d.bank && d.bank.supported && banks.some((b) => b.id === d.bank!.id)
          )
          const detectedValue = detectedListed ? d.bank!.id : ''
          const selectedBank = override || detectedValue
          const manualPick = Boolean(override && override !== detectedValue)
          const canPickBank = selectable && (d.state === 'UNKNOWN' || d.state === 'REVIEW')
          return (
            <li key={d.document_id} className="rounded border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-medium">{d.filename}</div>
                  <div className="text-xs text-gray-500">{(d.size_bytes / 1024).toFixed(0)} KB</div>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATE_STYLE[d.state] || ''}`}>
                  {d.state}
                </span>
              </div>

              <p className="mt-2 break-words text-sm">{d.message}</p>
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
                <details className="mt-2 text-sm">
                  <summary className="cursor-pointer font-medium text-gray-700">Why we think so</summary>
                  <ul className="mt-1 list-disc pl-5 text-gray-700">
                    {d.evidence.map((e, i) => (
                      <li key={i}>
                        {e.label || e.kind}
                        {e.value ? <>: <span className="font-mono text-xs">{e.value}</span></> : null}
                        {typeof e.weight === 'number' ? <span className="text-gray-400"> (+{e.weight})</span> : null}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {d.requires_password && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <input
                    type="password"
                    autoComplete="off"
                    placeholder="PDF password"
                    value={passwords[d.document_id] || ''}
                    onChange={(e) => onPassword(d.document_id, e.target.value)}
                    className="min-w-0 rounded border px-2 py-1 text-sm"
                    aria-label={`Password for ${d.filename}`}
                  />
                  <button
                    onClick={() => void onUnlock(d)}
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
                <>
                  <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,10rem)_auto]">
                    {canPickBank && (
                      <select
                        value={selectedBank}
                        onChange={(e) => onOverride(d.document_id, e.target.value)}
                        className="min-w-0 rounded border px-2 py-1 text-sm"
                        aria-label="Bank"
                      >
                        {!detectedValue && <option value="">Select bank…</option>}
                        {banks.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.name}
                            {b.v2_served ? ' · verified engine' : ''}
                          </option>
                        ))}
                      </select>
                    )}
                    <select
                      value={accountType}
                      onChange={(e) => onAccountType(d.document_id, e.target.value)}
                      className="min-w-0 rounded border px-2 py-1 text-sm"
                      aria-label="Statement type"
                    >
                      {ACCOUNT_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => void onConfirmOne(d, accountType || undefined)}
                      disabled={!!busy || !selectedBank || (d.bank?.supported === false && !manualPick)}
                      className="min-w-0 rounded bg-black px-3 py-1 text-sm text-white disabled:opacity-40"
                    >
                      {manualPick ? 'Use selected bank' : 'Confirm'}
                    </button>
                  </div>
                  <input
                    value={statementLabel}
                    onChange={(e) => onStatementLabel(d.document_id, e.target.value)}
                    maxLength={120}
                    placeholder="Statement label (optional)"
                    className="mt-2 w-full min-w-0 rounded border px-2 py-1 text-sm"
                    aria-label={`Statement label for ${d.filename}`}
                  />
                </>
              )}

              {d.workflow_status === 'CONFIRMED' && (
                <p className="mt-2 text-sm text-green-800">Confirmed as {d.effective_bank?.name}. Ready to process.</p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function summaryGroups(docs: WorkflowDoc[]) {
  const by: Record<string, { key: string; name: string; count: number }> = {}
  docs.forEach(({ document: d }) => {
    const name = d.effective_bank?.name || d.bank?.name || 'Unknown'
    const key = d.effective_bank?.id || d.bank?.id || 'unknown'
    by[key] = by[key] || { key, name, count: 0 }
    by[key].count += 1
  })
  return Object.values(by)
}
