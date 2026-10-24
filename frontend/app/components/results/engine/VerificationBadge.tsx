import { ocrIncompleteness } from '@/lib/statementEngine'
import { StatementEngineBlock } from '@/types'

const check = (
  <svg viewBox="0 0 12 12" width="12" height="12" className="shrink-0" aria-hidden="true" focusable="false">
    <path d="M2 6l3 3 5-6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const warn = (
  <svg viewBox="0 0 12 12" width="12" height="12" className="shrink-0" aria-hidden="true" focusable="false">
    <path d="M6 1.2 11 10H1Z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    <path d="M6 4.4v2.8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    <circle cx="6" cy="8.6" r=".75" fill="currentColor" />
  </svg>
)

/**
 * Engine verdict badge. Plain-language only; nothing renders when the
 * statement_engine block is absent or when a plain legacy result carries
 * no advisory. FAILED is never shown as served v2 data.
 */
export default function VerificationBadge({
  engine,
  details,
}: {
  engine: StatementEngineBlock | null
  details?: string
}) {
  if (!engine) return null
  const suffix = details ? ` · ${details}` : ''

  if (engine.engine === 'universal') {
    // T3: REVIEW is the ceiling — never a verification claim.
    return (
      <span role="status" aria-label={`Read by general reader${suffix}`}
        className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-medium text-amber-800">
        {warn}Read by general reader
        <span className="font-normal text-amber-700">
          {"· This statement's layout was read with our general reader, so please check the figures against your statement."}
        </span>
      </span>
    )
  }

  if (engine.engine === 'ocr') {
    // T4: read from an image. The backend caps this at REVIEW, so the badge never makes a verification claim,
    // and when pages or rows are missing the badge says so rather than leaving it to the workbook.
    const missing = ocrIncompleteness(engine)
    return (
      <span role="status" aria-label={`Scanned statement, needs review${missing ? `. ${missing}` : ''}${suffix}`}
        className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-medium text-amber-800">
        {warn}{missing ? 'Scanned · incomplete · needs review' : 'Scanned · needs review'}
        <span className="font-normal text-amber-700">
          {missing
            ? `· ${missing}`
            : '· This statement was read from an image, so please check every figure against your statement.'}
        </span>
      </span>
    )
  }

  if (engine.engine === 'v2') {
    if (engine.verdict === 'VERIFIED') {
      const label = engine.anchored ? 'Verified · independently checked' : 'Verified'
      return (
        <span role="status" aria-label={`${label}${suffix}`}
          className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-medium text-emerald-800">
          {check}{label}{details && <span className="font-normal text-emerald-700">· {details}</span>}
        </span>
      )
    }
    if (engine.verdict === 'REVIEW' || engine.needs_review) {
      return (
        <span role="status" aria-label={`Needs review${suffix}`}
          className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-medium text-amber-800">
          {warn}Needs review{details && <span className="font-normal text-amber-700">· {details}</span>}
        </span>
      )
    }
    return (
      <span role="status" aria-label={`Unable to verify${suffix}`}
        className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-700">
        {warn}Unable to verify{details && <span className="font-normal text-slate-500">· {details}</span>}
      </span>
    )
  }

  if (engine.advisory) {
    const v = engine.advisory.verdict
    const label = v === 'VERIFIED'
      ? "Checked with your bank's usual parser — the independent check verified the extraction"
      : v === 'REVIEW'
        ? "Checked with your bank's usual parser — the independent check raised points to review"
        : "Checked with your bank's usual parser — the independent check could not verify the extraction"
    return (
      <span role="status" aria-label={`${label}${suffix}`}
        className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-600">
        {v === 'VERIFIED' ? check : warn}{label}{details && <span className="font-normal text-slate-500">· {details}</span>}
      </span>
    )
  }

  // T2 legacy, flag-on modes only: neutral "Processed" — no verification claim.
  // Mode off renders nothing (previous contract); flagged/advisory results keep
  // their own signals above.
  if (engine.mode !== 'off' && !engine.needs_review && !(engine.review_codes || []).length) {
    return (
      <span role="status" aria-label={`Processed${suffix}`}
        className="inline-flex max-w-full items-center gap-1.5 flex-wrap rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-600">
        {check}Processed{details && <span className="font-normal text-slate-500">· {details}</span>}
      </span>
    )
  }

  return null
}
