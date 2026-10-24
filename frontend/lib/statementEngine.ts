import {
  StatementEngineBlock,
  StatementEngineOcr,
  StatementEngineVerdict,
} from '@/types'

/**
 * Plain-language wording for each stable review code (contract §4).
 * The API returns only codes; this table is the single source of UI wording.
 */
export const REVIEW_REASON_LABELS: Record<string, string> = {
  NO_INDEPENDENT_ANCHOR: 'No printed opening/closing summary to verify against',
  REFERENCE_MISMATCH: 'Extracted totals differ from the printed summary',
  CHAIN_BREAK: 'Running-balance chain does not reconcile',
  SIDE_MISMATCH: 'Debit/credit side mismatch',
  TOTALS_MISMATCH: 'Computed totals differ from printed totals',
  DATE_ORDER: 'Transactions out of date order',
  DATE_OUTLIER: 'Transaction date outside the statement period',
  OUTSIDE_PERIOD: 'Data outside the statement period',
  SCHEMA_ERRORS: 'Row schema errors',
  EXTRACTION_WARNINGS: 'Extraction warnings were raised',
  NO_RUNNING_BALANCE: 'No running balance column — verified against completeness and printed totals only',
  CHECKPOINT_MISMATCH: 'Printed carried-forward balance does not match the extracted rows',
  BALANCE_DELTA_MISMATCH: 'Printed opening-to-closing movement disagrees with extracted totals',
  SEGMENT_COUNT_MISMATCH: 'A printed per-account transaction count was not reproduced',
  SAME_DATE_DISORDER: 'Same-date rows print out of balance order — a reorder reconciles the chain',
  SECTION_DATE_MISSING: 'Transactions printed before any section date — the date each row belongs to is unprovable',
  BANK_MISMATCH: 'Detected bank differs from the selected bank',
  GENERAL_READER: 'Layout read by the general reader — check the figures',
  // OCR tier: a scanned statement is read from an image and is never a verification claim
  OCR_READER: 'Read from a scanned image — every figure must be checked against the statement',
  OCR_PARTIAL_PAGES: 'Some pages could not be read — transactions from them are missing',
  OCR_TABLE_ROWS_DROPPED: 'Some rows were read in a broken shape and could not be placed in a column',
  OCR_FUSED_AMOUNTS: 'Two amounts were read as one — the split between them is estimated',
  OCR_UNCONFIRMED_AMOUNTS: 'The second reader did not confirm every amount',
  OCR_VERIFIER_NOT_RUN: 'No second reader ran on this statement',
  OCR_AMOUNT_UNCONFIRMED: 'An amount was not confirmed by the second reader',
  OCR_AMOUNT_LOW_CONFIDENCE: 'An amount was read with low confidence',
}

export function reviewReasonLabel(code: string): string {
  return REVIEW_REASON_LABELS[code] || code.replace(/_/g, ' ').toLowerCase()
}

const VERDICTS: readonly StatementEngineVerdict[] = ['VERIFIED', 'REVIEW', 'FAILED']

function asVerdict(v: unknown): StatementEngineVerdict | null {
  return VERDICTS.includes(v as StatementEngineVerdict) ? (v as StatementEngineVerdict) : null
}

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

/**
 * Defensive parser for the additive `statement_engine` block.
 * Tolerates a missing block, missing/renamed fields, and both contract
 * shapes; returns null only when there is no block at all.
 * Rule: when the block is absent, the UI shows nothing.
 */
export function parseStatementEngine(raw: unknown): StatementEngineBlock | null {
  if (!raw || typeof raw !== 'object') return null
  const b = raw as Record<string, unknown>
  const adv = (b.advisory && typeof b.advisory === 'object' ? b.advisory : null) as
    | Record<string, unknown>
    | null
  const det = (b.detected_bank && typeof b.detected_bank === 'object' ? b.detected_bank : null) as
    | Record<string, unknown>
    | null
  const o = (b.ocr && typeof b.ocr === 'object' ? b.ocr : null) as Record<string, unknown> | null
  return {
    ocr: o
      ? {
          pages_total: typeof o.pages_total === 'number' ? o.pages_total : 0,
          pages_ok: Array.isArray(o.pages_ok) ? o.pages_ok.filter((x): x is number => typeof x === 'number') : [],
          failed_pages:
            o.failed_pages && typeof o.failed_pages === 'object'
              ? (o.failed_pages as Record<string, string>)
              : {},
          rows_dropped_total: typeof o.rows_dropped_total === 'number' ? o.rows_dropped_total : 0,
          verification_status:
            o.verification && typeof o.verification === 'object'
              ? String((o.verification as Record<string, unknown>).status ?? '')
              : null,
        }
      : null,
    engine: typeof b.engine === 'string' ? b.engine : 'legacy',
    mode: typeof b.mode === 'string' ? b.mode : 'off',
    layout_id: typeof b.layout_id === 'string' ? b.layout_id : null,
    verdict: asVerdict(b.verdict),
    needs_review: b.needs_review === true,
    review_codes: asStringArray(b.review_codes),
    anchored: b.anchored === true,
    detected_bank: det
      ? {
          key: typeof det.key === 'string' ? det.key : null,
          name: typeof det.name === 'string' ? det.name : null,
          confidence: typeof det.confidence === 'string' ? det.confidence : null,
          source: det.source === 'detector' || det.source === 'user' ? det.source : String(det.source ?? ''),
        }
      : null,
    advisory: adv
      ? {
          verdict: asVerdict(adv.verdict),
          review_codes: asStringArray(adv.review_codes),
          layout_id: typeof adv.layout_id === 'string' ? adv.layout_id : null,
        }
      : null,
  }
}

/** True when the block carries anything the user should notice. A scanned statement always does. */
export function engineNeedsAttention(b: StatementEngineBlock | null): boolean {
  return (
    !!b &&
    (b.engine === 'ocr' || b.needs_review || !!b.advisory?.verdict || b.review_codes.includes('BANK_MISMATCH'))
  )
}

/**
 * What is missing from a scanned statement, in one sentence, or null when nothing is.
 * The workbook's Statement Check sheet says this too, but a user who never opens it must still be told.
 */
export function ocrIncompleteness(b: StatementEngineBlock | null): string | null {
  const o: StatementEngineOcr | null | undefined = b && b.engine === 'ocr' ? b.ocr : null
  if (!o) return null
  const failed = Object.keys(o.failed_pages || {})
  const parts: string[] = []
  if (failed.length) {
    parts.push(`${failed.length === 1 ? 'Page' : 'Pages'} ${failed.join(', ')} could not be read`)
  }
  if (o.rows_dropped_total > 0) {
    parts.push(`${o.rows_dropped_total} row${o.rows_dropped_total === 1 ? '' : 's'} could not be placed`)
  }
  if (!parts.length) return null
  return `${parts.join('; ')} — transactions from ${failed.length ? 'those pages' : 'those rows'} are NOT in this report.`
}

/** Short badge label for a job/result; null when nothing should be shown. */
export function engineBadgeLabel(b: StatementEngineBlock | null): string | null {
  if (!b) return null
  if (b.engine === 'universal') return 'Read by general reader'
  // A scanned statement is capped at REVIEW by the backend and must never read as a verification claim.
  if (b.engine === 'ocr') return ocrIncompleteness(b) ? 'Scanned · incomplete · needs review' : 'Scanned · needs review'
  if (b.engine !== 'v2') return null
  if (b.verdict === 'VERIFIED') return b.anchored ? 'Verified · independently checked' : 'Verified'
  if (b.verdict === 'REVIEW' || b.needs_review) return 'Needs review'
  return null
}
