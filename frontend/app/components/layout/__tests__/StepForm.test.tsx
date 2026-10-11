import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import * as statementsApi from '@/lib/statementsApi'
import StepForm from '../StepForm'
import { SUPPORTED_BANK_OPTIONS } from '@/lib/banks'

describe('StepForm bank list', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('sources banks from GET /api/statements/banks when available', async () => {
    const spy = vi.spyOn(statementsApi, 'listBanks').mockResolvedValue([
      { id: 'hdfc', name: 'HDFC Bank', engines: ['legacy', 'v2'], v2_served: true },
      { id: 'rbl', name: 'RBL Bank', engines: ['v2'], v2_served: true },
    ])
    render(<StepForm onSubmit={() => undefined} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'RBL Bank' })).toBeInTheDocument())
    expect(spy).toHaveBeenCalled()
    // engine names must never appear in the dropdown
    expect(screen.queryByText(/v2|legacy/i)).not.toBeInTheDocument()
  })

  it('falls back to the bundled list when the API fails', async () => {
    vi.spyOn(statementsApi, 'listBanks').mockRejectedValue(new Error('network down'))
    render(<StepForm onSubmit={() => undefined} />)
    await waitFor(() => expect(statementsApi.listBanks).toHaveBeenCalled())
    const options = screen.getAllByRole('option').map((o) => o.textContent)
    for (const { name, available } of SUPPORTED_BANK_OPTIONS) {
      if (available) expect(options).toContain(name)
    }
  })
})
