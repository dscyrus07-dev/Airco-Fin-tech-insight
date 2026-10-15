import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ReviewTable from '../ReviewTable'
import type { WorkflowDoc } from '@/app/hooks/useStatementWorkflow'
import type { AnalyzedDocument, BankCatalogEntry, BankOption } from '@/lib/statementsApi'

const BANKS: BankOption[] = [
  { id: 'hdfc', name: 'HDFC Bank', engines: ['legacy', 'v2'], v2_served: true, support_state: 'verified' },
  { id: 'icici', name: 'ICICI Bank', engines: ['legacy'], v2_served: false, support_state: 'legacy' },
  { id: 'scb', name: 'Standard Chartered Bank', engines: ['v2'], v2_served: true, support_state: 'verified' },
]

const CATALOG: BankCatalogEntry[] = [
  { id: 'hdfc', name: 'HDFC Bank', support_state: 'verified' },
  { id: 'icici', name: 'ICICI Bank', support_state: 'legacy' },
  { id: 'scb', name: 'Standard Chartered Bank', support_state: 'verified' },
  { id: 'iob', name: 'Indian Overseas Bank', support_state: 'review_required', reason: 'No printed anchors.' },
  { id: 'yes', name: 'Yes Bank', support_state: 'coming_soon', reason: 'Measured, not enabled.' },
  { id: 'rbl', name: 'RBL Bank', support_state: 'unsupported', reason: 'No layout built for RBL.' },
]

function doc(over: Partial<AnalyzedDocument>): AnalyzedDocument {
  return {
    document_id: 'd1',
    filename: 'a.pdf',
    size_bytes: 1024,
    state: 'DETECTED',
    detail_state: 'DETECTED',
    message: '',
    requires_password: false,
    requires_confirmation: false,
    bank: null,
    evidence: [],
    layout: { id: 'UNKNOWN', confidence: 'UNKNOWN', description: '', parser_family: null },
    workflow_status: 'AWAITING_CONFIRMATION',
    effective_bank: null,
    job_id: null,
    ...over,
  }
}

function wf(over: Partial<AnalyzedDocument>): WorkflowDoc {
  return { document: doc(over), job: null, accountType: '', statementLabel: '', override: '' }
}

const NOOP = () => {}
const PROPS = {
  busy: null,
  passwords: {},
  onOverride: NOOP,
  onAccountType: NOOP,
  onStatementLabel: NOOP,
  onPassword: NOOP,
  onConfirmOne: vi.fn(async () => {}),
  onConfirmAll: vi.fn(async () => {}),
  onUnlock: vi.fn(async () => {}),
  onProcess: vi.fn(async () => {}),
}

function renderRow(d: WorkflowDoc, catalog?: BankCatalogEntry[]) {
  return render(<ReviewTable docs={[d]} banks={BANKS} catalog={catalog} {...PROPS} />)
}

describe('ReviewTable bank selection', () => {
  it('UNSUPPORTED row: no bank dropdown, no Confirm, no unrelated default', () => {
    // detected-but-not-servable bank must NOT prefill the select (bug: showed HDFC)
    renderRow(
      wf({
        state: 'UNSUPPORTED',
        detail_state: 'UNSUPPORTED_BANK',
        bank: { id: 'rbl', name: 'RBL Bank', confidence: 'HIGH', score: 1, supported: false },
        requires_confirmation: false,
      })
    )
    expect(screen.queryByLabelText('Bank')).toBeNull()
    expect(screen.queryByText('Confirm')).toBeNull()
    expect(screen.queryByDisplayValue('HDFC Bank')).toBeNull()
  })

  it('UNKNOWN row: empty dropdown of servable banks, no premature Confirm', () => {
    renderRow(wf({ state: 'UNKNOWN', detail_state: 'UNKNOWN_BANK', requires_confirmation: true }))
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    expect(sel.value).toBe('')
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveProperty('disabled', true)
    // only servable options are offered
    const labels = Array.from(sel.options).map((o) => o.textContent)
    expect(labels.join()).toContain('HDFC Bank')
    expect(labels.join()).not.toContain('RBL Bank')
  })

  it('DETECTED row: Confirm offered, detected bank shown, no manual picker', () => {
    renderRow(
      wf({
        state: 'DETECTED',
        bank: { id: 'hdfc', name: 'HDFC Bank', confidence: 'VERY_HIGH', score: 1, supported: true },
      })
    )
    expect(screen.queryByLabelText('Bank')).toBeNull()
    const btn = screen.getByRole('button', { name: 'Confirm' }) as HTMLButtonElement
    expect(btn.disabled).toBe(false)
  })

  it('REVIEW row with unlisted detected bank: placeholder, no Confirm for it', () => {
    // bank detected & flagged supported but not in the servable bank list ->
    // must not prefill and must not offer Confirm on the unservable bank
    renderRow(
      wf({
        state: 'REVIEW',
        detail_state: 'AWAITING_CONFIRMATION',
        bank: { id: 'rbl', name: 'RBL Bank', confidence: 'HIGH', score: 1, supported: false },
        requires_confirmation: true,
      })
    )
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    expect(sel.value).toBe('')
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveProperty('disabled', true)
  })

  it('REVIEW row with servable detected bank defaults to it', () => {
    renderRow(
      wf({
        state: 'REVIEW',
        detail_state: 'AWAITING_CONFIRMATION',
        bank: { id: 'scb', name: 'Standard Chartered Bank', confidence: 'HIGH', score: 1, supported: true },
        requires_confirmation: true,
      }),
      CATALOG
    )
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    expect(sel.value).toBe('scb')
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveProperty('disabled', false)
    expect(sel.textContent).toContain('verified engine')
  })

  it('UNSUPPORTED row names the bank and gives the support-state reason', () => {
    renderRow(
      wf({
        state: 'UNSUPPORTED',
        detail_state: 'UNSUPPORTED_BANK',
        bank: { id: 'rbl', name: 'RBL Bank', confidence: 'HIGH', score: 1, supported: false },
      }),
      CATALOG
    )
    const note = screen.getByText(/RBL Bank is not enabled yet/)
    expect(note.textContent).toContain('No layout built for RBL.')
    expect(screen.queryByLabelText('Bank')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
  })

  it('picker groups by state; coming_soon/unsupported rows are greyed and disabled', () => {
    renderRow(wf({ state: 'UNKNOWN', detail_state: 'UNKNOWN_BANK' }), CATALOG)
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    const groups = Array.from(sel.querySelectorAll('optgroup')).map((g) => g.getAttribute('label'))
    expect(groups).toEqual(
      expect.arrayContaining(['Verified', 'Review required', 'Legacy parser', 'Coming soon', 'Not supported'])
    )
    expect(sel.querySelector('option[value="yes"]')).toBeDisabled()
    expect(sel.querySelector('option[value="rbl"]')).toBeDisabled()
    expect(sel.querySelector('option[value="iob"]')).not.toBeDisabled()
    expect(sel.textContent).toContain('always needs review')
  })

  it('works without a catalog (older backend): servable banks stay selectable', () => {
    renderRow(wf({ state: 'UNKNOWN', detail_state: 'UNKNOWN_BANK' }))
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    expect(sel.querySelector('option[value="hdfc"]')).not.toBeDisabled()
    expect(sel.textContent).not.toContain('RBL Bank')
  })

  it('statement-label input carries an accessible name (a11y)', () => {
    renderRow(
      wf({
        state: 'DETECTED',
        bank: { id: 'hdfc', name: 'HDFC Bank', confidence: 'VERY_HIGH', score: 1, supported: true },
      })
    )
    expect(screen.getByLabelText('Statement label for a.pdf')).toBeTruthy()
  })
})
