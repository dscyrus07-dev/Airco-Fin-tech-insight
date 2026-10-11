import { StatementEngineBlock } from '@/types'
import ReviewReasons from './ReviewReasons'

/**
 * Expandable "How this was checked" panel. Native <details>/<summary>
 * gives keyboard support for free: Tab focuses it, Enter toggles it.
 * Shows plain-language reasons, the internal layout id (metadata, not
 * statement data) and any detected-bank mismatch.
 */
export default function EngineDetails({ engine }: { engine: StatementEngineBlock | null }) {
  if (!engine) return null
  const advCodes = engine.advisory?.review_codes ?? []
  const allCodes = [...new Set([...engine.review_codes, ...advCodes])]
  const mismatch = engine.review_codes.includes('BANK_MISMATCH')
  const advVerdict = engine.advisory?.verdict
  const attention =
    engine.needs_review || engine.verdict === 'REVIEW' || advVerdict === 'REVIEW' || advVerdict === 'FAILED'

  const heading =
    engine.verdict === 'REVIEW' || engine.needs_review
      ? 'The independent check flagged points to review'
      : advVerdict === 'REVIEW'
        ? 'The independent check raised points to review'
        : advVerdict === 'FAILED'
          ? 'The independent check could not verify the extraction'
          : 'How this was checked'

  return (
    <details
      className={`mt-3 w-full max-w-full rounded-xl border px-4 py-3 text-left ${
        attention ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-slate-50'
      }`}
    >
      <summary
        className={`cursor-pointer list-none text-[11px] font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 ${
          attention ? 'text-amber-900' : 'text-slate-700'
        }`}
      >
        {heading}
      </summary>
      <div className={`mt-2 space-y-1.5 text-[11px] ${attention ? 'text-amber-900' : 'text-slate-600'}`}>
        {mismatch && engine.detected_bank && (
          <p className="font-medium text-amber-800">
            This looks like a {engine.detected_bank.name} statement — please check the bank you selected.
          </p>
        )}
        <ReviewReasons codes={allCodes} />
        {(engine.verdict === 'FAILED' || advVerdict === 'FAILED') && (
          <p>The independent check failed safely; your existing parser results are shown.</p>
        )}
        {engine.verdict === 'VERIFIED' && !engine.anchored && (
          <p>Verified without a printed opening/closing summary.</p>
        )}
        {(engine.needs_review || engine.verdict === 'REVIEW' || advVerdict === 'REVIEW') && (
          <p>
            This file is marked <span className="font-medium">needs review</span> — totals are served but should be
            checked against the PDF. A <span className="font-medium">Statement Check</span> sheet is appended to the
            workbook.
          </p>
        )}
        {engine.layout_id && (
          <p className={attention ? 'text-amber-700' : 'text-slate-500'}>
            Layout: <span className="font-mono">{engine.layout_id}</span>
          </p>
        )}
      </div>
    </details>
  )
}
