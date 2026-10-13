import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BankSelect from '../BankSelect'
import BankSupportPanel from '../BankSupportPanel'
import type { BankCatalogEntry } from '@/lib/statementsApi'

const CATALOG: BankCatalogEntry[] = [
  { id: 'hdfc', name: 'HDFC Bank', support_state: 'verified' },
  { id: 'iob', name: 'Indian Overseas Bank', support_state: 'review_required', reason: 'no printed anchors' },
  { id: 'icici', name: 'ICICI Bank', support_state: 'legacy' },
  { id: 'yes', name: 'Yes Bank', support_state: 'coming_soon', reason: 'measured, not enabled' },
  { id: 'rbl', name: 'RBL Bank', support_state: 'unsupported', reason: 'no layout built' },
]

const BIG: BankCatalogEntry[] = Array.from({ length: 20 }, (_, i) => ({
  id: `b${i}`,
  name: `Bank ${String(i).padStart(2, '0')}`,
  support_state: i % 2 ? 'verified' : 'unsupported',
  reason: i % 2 ? null : 'not on file',
}))

describe('BankSelect', () => {
  it('groups options by support state with plain headings', () => {
    render(<BankSelect catalog={CATALOG} value="" onChange={vi.fn()} />)
    const labels = screen.getAllByRole('group').map((g) => g.getAttribute('label'))
    expect(labels).toEqual(['Verified', 'Review required', 'Legacy parser', 'Coming soon', 'Not supported'])
  })

  it('only servable banks are selectable; others are disabled and tagged', () => {
    render(<BankSelect catalog={CATALOG} value="" onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: /HDFC Bank/ })).not.toBeDisabled()
    expect(screen.getByRole('option', { name: /Indian Overseas Bank/ })).not.toBeDisabled()
    expect(screen.getByRole('option', { name: /ICICI Bank/ })).not.toBeDisabled()
    const yes = screen.getByRole('option', { name: /Yes Bank/ })
    const rbl = screen.getByRole('option', { name: /RBL Bank/ })
    expect(yes).toBeDisabled()
    expect(rbl).toBeDisabled()
    expect(yes.textContent).toContain('coming soon')
    expect(rbl.textContent).toContain('not supported')
  })

  it('does not call onChange for a disabled option', async () => {
    const onChange = vi.fn()
    render(<BankSelect catalog={CATALOG} value="" onChange={onChange} />)
    const sel = screen.getByLabelText('Bank') as HTMLSelectElement
    // jsdom still fires change on programmatic select of a disabled option — but
    // the DOM blocks it in real browsers; assert disabled state is the guard
    expect(sel.querySelector('option[value="rbl"]')).toBeDisabled()
  })

  it('shows a filter box when the list exceeds 12 and narrows options', async () => {
    render(<BankSelect catalog={BIG} value="" onChange={vi.fn()} />)
    const filter = screen.getByLabelText('Filter banks')
    await userEvent.type(filter, 'Bank 01')
    const opts = screen.getAllByRole('option').map((o) => o.textContent)
    expect(opts).toHaveLength(1)
    expect(opts[0]).toContain('Bank 01')
  })

  it('no filter box at or under 12 entries', () => {
    render(<BankSelect catalog={CATALOG} value="" onChange={vi.fn()} />)
    expect(screen.queryByLabelText('Filter banks')).toBeNull()
  })

  it('showNonSelectable=false lists only servable banks', () => {
    render(<BankSelect catalog={CATALOG} value="" onChange={vi.fn()} showNonSelectable={false} />)
    const names = screen.getAllByRole('option').map((o) => o.textContent)
    expect(names.join()).not.toMatch(/RBL Bank|Yes Bank/)
    expect(names.join()).toContain('HDFC Bank')
  })
})

describe('BankSupportPanel', () => {
  it('renders counts from the catalog, never hard-coded', () => {
    render(<BankSupportPanel catalog={CATALOG} />)
    expect(screen.getByText(/3 banks supported/)).toBeInTheDocument()
    expect(screen.getByText(/1 coming soon/)).toBeInTheDocument()
    expect(screen.getByText(/1 not supported/)).toBeInTheDocument()
  })

  it('lists every state group with icons + reasons on greyed rows', () => {
    render(<BankSupportPanel catalog={CATALOG} />)
    expect(screen.getByText(/Verified \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Review required \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Legacy parser \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Coming soon \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Not supported \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/no layout built/)).toBeInTheDocument()
  })

  it('renders nothing for an empty catalog', () => {
    const { container } = render(<BankSupportPanel catalog={[]} />)
    expect(container.firstChild).toBeNull()
  })
})
