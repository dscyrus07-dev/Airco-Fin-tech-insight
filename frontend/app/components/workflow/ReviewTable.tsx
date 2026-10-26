'use client'

import { AnalyzedDocument, BankCatalogEntry, BankOption, OcrCatalog, OcrReading, isScanned } from '@/lib/statementsApi'
import { catalogFromBanks, findCatalogEntry, isSelectable } from '@/lib/bankSupport'
import BankSelect from '@/app/components/bank/BankSelect'
import type { WorkflowDoc } from '@/app/hooks/useStatementWorkflow'

const STATE_STYLE: Record<string, string> = {
  DETECTED: 'bg-green-100 text-green-800',
  REVIEW: 'bg-yellow-100 text-yellow-800',
  UNKNOWN: 'bg-gray-200 text-gray-800',
  UNSUPPORTED: 'bg-orange-100 text-orange-800',
  ERROR: 'bg-red-100 text-red-800',
}

// Measured on synthetic scans (docs/ocr/R11_DEVIN_REPORT.md): both readings put every amount on the right
// side; they differ in speed, in rotated/skewed pages, and in whether a second reader checks the amounts.
const READING_COPY: Record<OcrReading, { title: string; body: string }> = {
  thorough: {
    title: 'Thorough',
    body: 'Reads rotated and skewed pages, and a second reader checks every amount. About 6 seconds a page.',
  },
  fast: {
    title: 'Fast',
    body: 'About 1 second a page. No second check on the amounts, and rotated or skewed pages may not be read.',
  },
}

function OcrReadingChoice({
  doc,
  value,
  ocr,
  disabled,
  onChange,
}: {
  doc: AnalyzedDocument
  value: OcrReading | ''
  ocr: OcrCatalog
  disabled: boolean
  onChange: (documentId: string, value: OcrReading) => void
}) {
  const modes: OcrReading[] = ocr.reading_modes.length ? ocr.reading_modes : ['thorough', 'fast']
  const current: OcrReading = value || ocr.default_reading || modes[0]
  return (
    <fieldset className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3" disabled={disabled}>
      <legend className="px-1 text-xs font-semibold text-amber-900">Scanned statement: read with OCR</legend>
      <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label={`OCR reading for ${doc.filename}`}>
        {modes.map((m) => (
          <label
            key={m}
            className={`flex min-w-0 cursor-pointer items-start gap-2 rounded border bg-white p-2 text-sm ${
              current === m ? 'border-amber-500 ring-1 ring-amber-400' : 'border-slate-200'
            }`}
          >
            <input
              type="radio"
              name={`ocr-reading-${doc.document_id}`}
              value={m}
              checked={current === m}
              onChange={() => onChange(doc.document_id, m)}
              className="mt-1 shrink-0"
            />
            <span className="min-w-0">
              <span className="font-medium text-slate-900">
                {READING_COPY[m].title}
                {m === ocr.default_reading ? ' (default)' : ''}
              </span>
              <span className="block text-xs text-slate-600">{READING_COPY[m].body}</span>
            </span>
          </label>
        ))}
      </div>
      <p className="mt-2 text-xs text-amber-900">
        Figures read from a scan are always marked for review, so check them against the statement.
        {ocr.max_pages ? ` Scans can be up to ${ocr.max_pages} pages.` : ''}
      </p>
    </fieldset>
  )
}

const ACCOUNT_TYPES = [
  { value: '', label: 'Auto-detect' },
  { value: 'salaried', label: 'Salaried' },
  { value: 'business', label: 'Business' },
]

interface ReviewTableProps {
  docs: WorkflowDoc[]
  banks: BankOption[]
  /** Full bank catalog (all support states); falls back to `banks` when absent. */
  catalog?: BankCatalogEntry[]
  busy: string | null
  passwords: Record<string, string>
  onOverride: (documentId: string, bankId: string) => void
  onAccountType: (documentId: string, value: string) => void
  onStatementLabel: (documentId: string, value: string) => void
  /** present only when the backend reads scanned statements */
  ocr?: OcrCatalog | null
  onOcrReading?: (documentId: string, value: OcrReading) => void
  onPassword: (documentId: string, value: string) => void
  onConfirmOne: (doc: AnalyzedDocument, accountType?: string) => Promise<void>
  onConfirmAll: () => Promise<void>
  onUnlock: (doc: AnalyzedDocument) => Promise<void>
  onProcess: () => Promise<void>
}

export default function ReviewTable({
  docs,
  banks,
  catalog,
  busy,
  passwords,
  onOverride,
  onAccountType,
  onStatementLabel,
  ocr,
  onOcrReading,
  onPassword,
  onConfirmOne,
  onConfirmAll,
  onUnlock,
  onProcess,
}: ReviewTableProps) {
  const effectiveCatalog = catalog?.length ? catalog : catalogFromBanks(banks)
  const confirmedCount = docs.filter((d) => d.document.workflow_status === 'CONFIRMED').length
  const detectedPending = docs.filter(
    (d) => d.document.state === 'DETECTED' && d.document.workflow_status === 'AWAITING_CONFIRMATION' && !d.document.requires_password
  ).length

  return (
    <div className="w-full min-w-0">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {summaryGroups(docs).map((g) => (
          <span key={g.key} className="rounded-full border border-[#A1B2CE]/40 bg-[#01275C]/5 px-3.5 py-1 text-xs font-semibold text-[#01275C] dark:border-blue-400/30 dark:bg-blue-950/60 dark:text-blue-200">
            {g.name}: {g.count}
          </span>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          onClick={() => void onConfirmAll()}
          disabled={!detectedPending || !!busy}
          className="rounded-xl border border-[#01275C] px-4 py-2 text-sm font-semibold text-[#01275C] transition hover:bg-[#01275C]/5 disabled:opacity-40 dark:border-blue-400 dark:text-blue-300"
        >
          Confirm all detected ({detectedPending})
        </button>
        <button
          onClick={() => void onProcess()}
          disabled={!confirmedCount || !!busy}
          className="btn-primary rounded-xl px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Process confirmed ({confirmedCount})
        </button>
      </div>

      <ul className="mt-4 space-y-3">
        {docs.map(({ document: d, override, accountType, statementLabel, ocrReading }) => {
          const selectable = d.state !== 'ERROR' && d.state !== 'UNSUPPORTED' && !d.requires_password && d.workflow_status === 'AWAITING_CONFIRMATION'
          const detectedListed = Boolean(
            d.bank && d.bank.supported && banks.some((b) => b.id === d.bank!.id)
          )
          const detectedValue = detectedListed ? d.bank!.id : ''
          const selectedBank = override || detectedValue
          const manualPick = Boolean(override && override !== detectedValue)
          const canPickBank = selectable && (d.state === 'UNKNOWN' || d.state === 'REVIEW')
          const bankEntry = findCatalogEntry(effectiveCatalog, d.bank?.id)
          const bankState = bankEntry?.support_state
          return (
            <li key={d.document_id} className="rounded-xl border border-slate-200/90 bg-slate-50/40 p-4 dark:border-slate-700/80 dark:bg-[#08152B]/60">
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
                  {d.bank
                    ? `${d.bank.name} is not enabled yet`
                    : "This bank isn't fully supported yet."}
                  {bankState && bankState !== 'verified' && bankState !== 'legacy' && bankEntry?.reason
                    ? ` — ${bankEntry.reason}`
                    : ''}
                  {d.message ? ` ${d.message}` : ''}
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
                      <BankSelect
                        catalog={effectiveCatalog}
                        value={selectedBank}
                        onChange={(id) => onOverride(d.document_id, id)}
                        ariaLabel="Bank"
                        showPlaceholder={!detectedValue}
                      />
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
                      className="btn-primary min-w-0 rounded-lg px-3.5 py-1.5 text-sm font-medium text-white disabled:opacity-40"
                    >
                      {manualPick ? 'Use selected bank' : 'Confirm'}
                    </button>
                  </div>
                  <input
                    value={statementLabel}
                    onChange={(e) => onStatementLabel(d.document_id, e.target.value)}
                    aria-label={`Statement label for ${d.filename}`}
                    maxLength={120}
                    placeholder="Statement label (optional)"
                    className="mt-2 w-full min-w-0 rounded border px-2 py-1 text-sm"
                  />
                </>
              )}

              {d.workflow_status === 'CONFIRMED' && (
                <p className="mt-2 text-sm text-green-800">Confirmed as {d.effective_bank?.name}. Ready to process.</p>
              )}

              {ocr?.enabled &&
                onOcrReading &&
                isScanned(d) &&
                (d.workflow_status === 'AWAITING_CONFIRMATION' || d.workflow_status === 'CONFIRMED') && (
                  <OcrReadingChoice
                    doc={d}
                    value={ocrReading || ''}
                    ocr={ocr}
                    disabled={!!busy}
                    onChange={onOcrReading}
                  />
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
