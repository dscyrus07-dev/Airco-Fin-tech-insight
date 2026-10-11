import {
  StatementEngineBlock,
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
  BANK_MISMATCH: 'Detected bank differs from the selected bank',
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
  return {
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

/** True when the block carries anything the user should notice. */
export function engineNeedsAttention(b: StatementEngineBlock | null): boolean {
  return !!b && (b.needs_review || !!b.advisory?.verdict || b.review_codes.includes('BANK_MISMATCH'))
}

/** Short badge label for a job/result; null when nothing should be shown. */
export function engineBadgeLabel(b: StatementEngineBlock | null): string | null {
  if (!b || b.engine !== 'v2') return null
  if (b.verdict === 'VERIFIED') return b.anchored ? 'Verified · independently checked' : 'Verified'
  if (b.verdict === 'REVIEW' || b.needs_review) return 'Needs review'
  return null
}
