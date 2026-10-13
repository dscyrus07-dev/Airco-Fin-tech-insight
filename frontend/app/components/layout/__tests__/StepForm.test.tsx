import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import * as statementsApi from '@/lib/statementsApi'
import StepForm from '../StepForm'
import { SUPPORTED_BANK_OPTIONS } from '@/lib/banks'

describe('StepForm bank list', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('sources banks from GET /api/statements/banks when available', async () => {
    const spy = vi.spyOn(statementsApi, 'listBankCatalog').mockResolvedValue({
      banks: [
        { id: 'hdfc', name: 'HDFC Bank', engines: ['legacy', 'v2'], v2_served: true, support_state: 'verified' },
        { id: 'rbl', name: 'RBL Bank', engines: ['v2'], v2_served: true, support_state: 'verified' },
      ],
      all_banks: [],
    })
    render(<StepForm onSubmit={() => undefined} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'RBL Bank' })).toBeInTheDocument())
    expect(spy).toHaveBeenCalled()
    // engine names must never appear in the dropdown
    expect(screen.queryByText(/v2|legacy/i)).not.toBeInTheDocument()
  })

  it('falls back to the bundled list when the API fails', async () => {
    vi.spyOn(statementsApi, 'listBankCatalog').mockRejectedValue(new Error('network down'))
    render(<StepForm onSubmit={() => undefined} />)
    await waitFor(() => expect(statementsApi.listBankCatalog).toHaveBeenCalled())
    const options = screen.getAllByRole('option').map((o) => o.textContent)
    for (const { name, available } of SUPPORTED_BANK_OPTIONS) {
      if (available) expect(options).toContain(name)
    }
  })

  it('groups catalog banks by support state and disables non-servable ones', async () => {
    vi.spyOn(statementsApi, 'listBankCatalog').mockResolvedValue({
      banks: [{ id: 'hdfc', name: 'HDFC Bank', v2_served: true, support_state: 'verified' }],
      all_banks: [
        { id: 'hdfc', name: 'HDFC Bank', support_state: 'verified' },
        { id: 'iob', name: 'Indian Overseas Bank', support_state: 'review_required', reason: 'no anchors' },
        { id: 'icici', name: 'ICICI Bank', support_state: 'legacy' },
        { id: 'yes', name: 'Yes Bank', support_state: 'coming_soon', reason: 'measured, not enabled' },
        { id: 'rbl', name: 'RBL Bank', support_state: 'unsupported', reason: 'no layout' },
      ],
    })
    render(<StepForm onSubmit={() => undefined} />)
    await waitFor(() => expect(screen.getByRole('option', { name: /Yes Bank/ })).toBeInTheDocument())

    // group headings present (optgroup labels)
    const groups = screen.getAllByRole('group').map((g) => g.getAttribute('label'))
    expect(groups).toEqual(
      expect.arrayContaining(['Verified', 'Review required', 'Legacy parser', 'Coming soon', 'Not supported'])
    )
    // servable selectable; non-servable disabled
    expect(screen.getByRole('option', { name: /HDFC Bank/ })).not.toBeDisabled()
    expect(screen.getByRole('option', { name: /Indian Overseas Bank/ })).not.toBeDisabled()
    expect(screen.getByRole('option', { name: /Yes Bank/ })).toBeDisabled()
    expect(screen.getByRole('option', { name: /RBL Bank/ })).toBeDisabled()
    // greyed rows carry a one-line explanation in text, not colour alone
    expect(screen.getByRole('option', { name: /Yes Bank/ }).textContent).toContain('coming soon')
    expect(screen.getByRole('option', { name: /RBL Bank/ }).textContent).toContain('not supported')
  })
})
