import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  REVIEW_REASON_LABELS,
  engineBadgeLabel,
  engineNeedsAttention,
  parseStatementEngine,
  reviewReasonLabel,
} from '@/lib/statementEngine'
import VerificationBadge from '../VerificationBadge'
import ReviewReasons from '../ReviewReasons'
import EngineDetails from '../EngineDetails'
import { StatementEngineBlock } from '@/types'

// Real block shapes produced by backend/app/services/statement_engine/serve.py
// (engine_block / minimal_block), per docs/slice3/V2_API_CONTRACT.md §3.
const V2_VERIFIED = {
  engine: 'v2',
  mode: 'serve',
  layout_id: 'hdfc_v1',
  verdict: 'VERIFIED',
  needs_review: false,
  review_codes: [],
  anchored: true,
  detected_bank: { key: 'hdfc', name: 'HDFC Bank', confidence: 'HIGH', source: 'detector' },
  advisory: null,
}

const V2_REVIEW = {
  engine: 'v2',
  mode: 'serve',
  layout_id: 'hdfc_v1',
  verdict: 'REVIEW',
  needs_review: true,
  review_codes: ['NO_INDEPENDENT_ANCHOR'],
  anchored: false,
  detected_bank: { key: 'hdfc', name: 'HDFC Bank', confidence: 'HIGH', source: 'detector' },
  advisory: null,
}

// FAILED is never served as v2 data: serve.py returns engine=legacy + advisory.
const V2_FAILED_AS_LEGACY = {
  engine: 'legacy',
  mode: 'serve',
  layout_id: null,
  verdict: null,
  needs_review: false,
  review_codes: [],
  anchored: false,
  detected_bank: { key: 'hdfc', name: 'HDFC Bank', confidence: 'HIGH', source: 'detector' },
  advisory: { verdict: 'FAILED', review_codes: ['CHAIN_BREAK'], layout_id: 'hdfc_v1' },
}

const LEGACY_WITH_ADVISORY = {
  engine: 'legacy',
  mode: 'serve',
  layout_id: null,
  verdict: null,
  needs_review: false,
  review_codes: [],
  anchored: false,
  detected_bank: null,
  advisory: { verdict: 'REVIEW', review_codes: ['NO_INDEPENDENT_ANCHOR'], layout_id: 'kotak_v2' },
}

const MODE_OFF = {
  engine: 'legacy',
  mode: 'off',
  layout_id: null,
  verdict: null,
  needs_review: false,
  review_codes: [],
  anchored: false,
  detected_bank: null,
  advisory: null,
}

const asBlock = (raw: unknown): StatementEngineBlock | null => parseStatementEngine(raw)

describe('parseStatementEngine', () => {
  it('returns null when the block is absent or malformed', () => {
    expect(parseStatementEngine(undefined)).toBeNull()
    expect(parseStatementEngine(null)).toBeNull()
    expect(parseStatementEngine('v2')).toBeNull()
    expect(parseStatementEngine(42)).toBeNull()
  })

  it('parses a real v2 VERIFIED block', () => {
    const b = parseStatementEngine(V2_VERIFIED)
    expect(b?.engine).toBe('v2')
    expect(b?.verdict).toBe('VERIFIED')
    expect(b?.anchored).toBe(true)
    expect(b?.detected_bank?.key).toBe('hdfc')
  })

  it('tolerates missing/extra fields and bad types', () => {
    const b = parseStatementEngine({ engine: 'v2', verdict: 'BOGUS', review_codes: 'x', extra: 1 })
    expect(b?.engine).toBe('v2')
    expect(b?.verdict).toBeNull()
    expect(b?.review_codes).toEqual([])
    expect(b?.needs_review).toBe(false)
    expect(b?.advisory).toBeNull()
  })

  it('parses a legacy block carrying an advisory', () => {
    const b = parseStatementEngine(LEGACY_WITH_ADVISORY)
    expect(b?.engine).toBe('legacy')
    expect(b?.advisory?.verdict).toBe('REVIEW')
    expect(b?.advisory?.review_codes).toEqual(['NO_INDEPENDENT_ANCHOR'])
  })
})

describe('wording table', () => {
  it('covers every stable review code', () => {
    for (const code of [
      'NO_INDEPENDENT_ANCHOR',
      'REFERENCE_MISMATCH',
      'CHAIN_BREAK',
      'SIDE_MISMATCH',
      'TOTALS_MISMATCH',
      'DATE_ORDER',
      'DATE_OUTLIER',
      'OUTSIDE_PERIOD',
      'SCHEMA_ERRORS',
      'EXTRACTION_WARNINGS',
      'BANK_MISMATCH',
    ]) {
      expect(REVIEW_REASON_LABELS[code]).toBeTruthy()
    }
  })

  it('maps NO_INDEPENDENT_ANCHOR to the exact plain-language wording', () => {
    expect(reviewReasonLabel('NO_INDEPENDENT_ANCHOR')).toBe(
      'No printed opening/closing summary to verify against'
    )
  })

  it('humanizes unknown codes instead of leaking raw SNAKE_CASE', () => {
    expect(reviewReasonLabel('SOME_NEW_CODE')).toBe('some new code')
  })
})

describe('helpers', () => {
  it('engineBadgeLabel only labels v2 results', () => {
    expect(engineBadgeLabel(asBlock(V2_VERIFIED))).toBe('Verified · independently checked')
    expect(engineBadgeLabel(asBlock(V2_REVIEW))).toBe('Needs review')
    expect(engineBadgeLabel(asBlock(V2_FAILED_AS_LEGACY))).toBeNull()
    expect(engineBadgeLabel(asBlock(MODE_OFF))).toBeNull()
    expect(engineBadgeLabel(null)).toBeNull()
  })

  it('engineNeedsAttention flags review/advisory states only', () => {
    expect(engineNeedsAttention(asBlock(V2_VERIFIED))).toBe(false)
    expect(engineNeedsAttention(asBlock(V2_REVIEW))).toBe(true)
    expect(engineNeedsAttention(asBlock(V2_FAILED_AS_LEGACY))).toBe(true)
    expect(engineNeedsAttention(asBlock(LEGACY_WITH_ADVISORY))).toBe(true)
    expect(engineNeedsAttention(asBlock(MODE_OFF))).toBe(false)
    expect(engineNeedsAttention(null)).toBe(false)
  })
})

describe('VerificationBadge', () => {
  it('renders nothing when the block is absent', () => {
    const { container } = render(<VerificationBadge engine={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for plain mode-off legacy blocks', () => {
    const { container } = render(<VerificationBadge engine={asBlock(MODE_OFF)} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows Verified for v2 VERIFIED', () => {
    render(<VerificationBadge engine={asBlock(V2_VERIFIED)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Verified · independently checked')
  })

  it('shows Needs review for v2 REVIEW', () => {
    render(<VerificationBadge engine={asBlock(V2_REVIEW)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Needs review')
  })

  it('never presents v2 FAILED as served data — shows the legacy+advisory message', () => {
    render(<VerificationBadge engine={asBlock(V2_FAILED_AS_LEGACY)} />)
    const badge = screen.getByRole('status')
    expect(badge).toHaveTextContent("usual parser")
    expect(badge).toHaveTextContent('could not verify')
    expect(badge).not.toHaveTextContent('Verified ·')
  })

  it('describes a legacy advisory in plain language', () => {
    render(<VerificationBadge engine={asBlock(LEGACY_WITH_ADVISORY)} />)
    expect(screen.getByRole('status')).toHaveTextContent('raised points to review')
  })

  it.each([
    ['v2 VERIFIED', V2_VERIFIED],
    ['v2 REVIEW', V2_REVIEW],
    ['v2 FAILED (served as legacy+advisory)', V2_FAILED_AS_LEGACY],
    ['legacy with advisory', LEGACY_WITH_ADVISORY],
  ])('renders the %s backend block', (_label, raw) => {
    const { container } = render(
      <>
        <VerificationBadge engine={asBlock(raw)} />
        <EngineDetails engine={asBlock(raw)} />
      </>
    )
    expect(container).toMatchSnapshot()
  })
})

describe('ReviewReasons', () => {
  it('renders plain-language reasons, not raw codes', () => {
    render(<ReviewReasons codes={['NO_INDEPENDENT_ANCHOR', 'CHAIN_BREAK']} />)
    expect(screen.getByText('No printed opening/closing summary to verify against')).toBeInTheDocument()
    expect(screen.getByText('Running-balance chain does not reconcile')).toBeInTheDocument()
    expect(screen.queryByText('NO_INDEPENDENT_ANCHOR')).not.toBeInTheDocument()
  })

  it('renders nothing for an empty list', () => {
    const { container } = render(<ReviewReasons codes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('EngineDetails', () => {
  it('renders nothing when the block is absent', () => {
    const { container } = render(<EngineDetails engine={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('is keyboard reachable and expands via summary', async () => {
    render(<EngineDetails engine={asBlock(V2_REVIEW)} />)
    const summary = screen.getByText('The independent check flagged points to review')
    const details = summary.closest('details')!
    expect(details).not.toHaveAttribute('open')
    summary.focus()
    await userEvent.click(summary)
    expect(details).toHaveAttribute('open')
    expect(screen.getByText('No printed opening/closing summary to verify against')).toBeVisible()
  })

  it('explains FAILED safely', () => {
    render(<EngineDetails engine={asBlock(V2_FAILED_AS_LEGACY)} />)
    expect(screen.getByText(/failed safely/)).toBeInTheDocument()
  })

  it('surfaces a detected-bank mismatch in plain language', () => {
    const mismatch = { ...V2_REVIEW, review_codes: ['BANK_MISMATCH'] }
    render(<EngineDetails engine={asBlock(mismatch)} />)
    expect(screen.getByText(/looks like a HDFC Bank statement/)).toBeInTheDocument()
  })
})
