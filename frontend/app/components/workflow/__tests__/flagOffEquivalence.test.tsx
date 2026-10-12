import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Dashboard from '../../Dashboard'

vi.mock('@/lib/sessionToken', () => ({
  getValidSessionAccessToken: async () => 'test-token',
}))
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { name: 'Test User', email: 't@example.com' }, logout: async () => {} }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

/**
 * Flag-off equivalence: /dashboard must render the legacy stepper
 * (Details / Upload / Mode / Processing / Report) and the Analyze link,
 * exactly as before the unified-entry work.
 */
describe('Dashboard with NEXT_PUBLIC_UNIFIED_ENTRY off', () => {
  it('renders the legacy 5-step structure and Analyze link', () => {
    render(<Dashboard />)
    const text = document.body.textContent || ''
    expect(text).toContain('Details')
    expect(text).toContain('Full Name')
    expect(text).toContain('Bank Name')
    expect(screen.getByText('Analyze')).toBeTruthy()
    // legacy stepper labels present
    expect(text).toContain('Mode')
    expect(text).toContain('Processing')
    expect(text).toContain('Report')
    // unified workflow must NOT be present
    expect(text).not.toContain('Drop up to 20 PDF statements here')
  })
})

describe('Dashboard with NEXT_PUBLIC_UNIFIED_ENTRY on', () => {
  it('renders the unified workflow instead of the legacy stepper', () => {
    const prev = process.env.NEXT_PUBLIC_UNIFIED_ENTRY
    process.env.NEXT_PUBLIC_UNIFIED_ENTRY = 'on'
    try {
      render(<Dashboard />)
      const text = document.body.textContent || ''
      expect(text).toContain('Drop up to 20 PDF statements here')
      expect(text).toContain('Analyze statements')
      // legacy Details/Mode steps must not be reachable
      expect(text).not.toContain('Add Another Bank')
      expect(text).not.toContain("You'll choose the bank statement type")
    } finally {
      process.env.NEXT_PUBLIC_UNIFIED_ENTRY = prev
    }
  })
})
