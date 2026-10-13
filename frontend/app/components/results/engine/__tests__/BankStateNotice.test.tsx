import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import BankStateNotice from '../BankStateNotice'
import type { BankCatalogEntry } from '@/lib/statementsApi'

const CATALOG: BankCatalogEntry[] = [
  { id: 'hdfc', name: 'HDFC Bank', support_state: 'verified' },
  { id: 'iob', name: 'Indian Overseas Bank', support_state: 'review_required', reason: 'No printed balance anchors.' },
  { id: 'yes', name: 'Yes Bank', support_state: 'coming_soon', reason: 'not enabled' },
]

describe('BankStateNotice', () => {
  it('shows a persistent needs-review notice for review_required banks', () => {
    render(<BankStateNotice catalog={CATALOG} bankKey="iob" />)
    const el = screen.getByRole('status')
    expect(el.textContent).toContain('Indian Overseas Bank reports always need review')
    expect(el.textContent).toContain('No printed balance anchors.')
  })

  it('renders nothing for verified / coming_soon / unknown banks', () => {
    const { container } = render(<BankStateNotice catalog={CATALOG} bankKey="hdfc" />)
    expect(container.firstChild).toBeNull()
    const c2 = render(<BankStateNotice catalog={CATALOG} bankKey="yes" />)
    expect(c2.container.firstChild).toBeNull()
    const c3 = render(<BankStateNotice catalog={CATALOG} bankKey="nope" />)
    expect(c3.container.firstChild).toBeNull()
    const c4 = render(<BankStateNotice catalog={CATALOG} bankKey={null} />)
    expect(c4.container.firstChild).toBeNull()
  })
})
