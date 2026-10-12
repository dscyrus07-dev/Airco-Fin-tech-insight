'use client'

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/sessionToken', () => ({
  getValidSessionAccessToken: async () => 'test-token',
}))
import { useStatementWorkflow } from '../useStatementWorkflow'

// minimal fetch mock: routes by URL pattern
type Handler = (url: string, init?: RequestInit) => Promise<Response> | Response
let handlers: Record<string, Handler> = {}
const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
  for (const [pat, h] of Object.entries(handlers)) {
    if (url.includes(pat)) return await h(url, init)
  }
  throw new Error(`unmocked fetch ${url}`)
})

function jsonResponse(data: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => data } as unknown as Response
}

const DOC = {
  document_id: 'doc-1',
  filename: 'hdfc.pdf',
  size_bytes: 1024,
  state: 'DETECTED',
  detail_state: 'DETECTED',
  message: 'HDFC Bank.',
  requires_password: false,
  requires_confirmation: true,
  bank: { id: 'hdfc', name: 'HDFC Bank', confidence: 'HIGH', score: 58, supported: true },
  suggestion: null,
  evidence: [],
  layout: { id: 'hdfc_x', confidence: 'HIGH', description: 'HDFC', parser_family: 'hdfc' },
  workflow_status: 'AWAITING_CONFIRMATION',
  effective_bank: null,
  hint_conflict: false,
  job_id: null,
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  handlers = {
    '/api/statements/banks': () => jsonResponse({ banks: [{ id: 'hdfc', name: 'HDFC Bank' }] }),
    '/api/statements/analyze': () =>
      jsonResponse({
        analysis_id: 'a-1',
        expires_at: '2026-10-13T00:00:00Z',
        documents: [DOC],
        summary: { total: 1, by_state: { DETECTED: 1 }, groups: [{ bank_id: 'hdfc', bank_name: 'HDFC Bank', count: 1, confidence: 'HIGH', document_ids: ['doc-1'] }] },
      }),
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function renderWorkflow() {
  return renderHook(() => useStatementWorkflow())
}

describe('useStatementWorkflow', () => {
  it('uploads and reaches review', async () => {
    const { result } = renderWorkflow()
    await act(async () => {
      result.current.analyze()
    })
    await waitFor(() => expect(result.current.step).toBe('review'))
    expect(result.current.docs[0].document.bank?.id).toBe('hdfc')
  })

  it('returns to upload with a message when the analysis expired (404/410)', async () => {
    handlers['/api/statements/analyze'] = () => jsonResponse({ code: 'ANALYSIS_EXPIRED' }, 410)
    const { result } = renderWorkflow()
    await act(async () => {
      result.current.analyze()
    })
    await waitFor(() => expect(result.current.step).toBe('upload'))
    expect(result.current.error).toMatch(/expired/i)
  })

  it('override sends OVERRIDE with the chosen bank', async () => {
    const confirmCalls: { documents: { action: string; bank_id: string }[] }[] = []
    handlers['/api/statements/a-1/confirm'] = (_u, init) => {
      confirmCalls.push(JSON.parse(String(init?.body)))
      return jsonResponse({ analysis_id: 'a-1', documents: [{ ...DOC, workflow_status: 'CONFIRMED', effective_bank: { id: 'sbi', name: 'SBI' } }], summary: { total: 1, by_state: {}, groups: [] } })
    }
    const { result } = renderWorkflow()
    await act(async () => {
      result.current.analyze()
    })
    await waitFor(() => expect(result.current.step).toBe('review'))
    act(() => result.current.setOverride('doc-1', 'sbi'))
    await act(async () => {
      await result.current.confirmOne(DOC as never)
    })
    expect(confirmCalls[0].documents[0]).toMatchObject({ action: 'OVERRIDE', bank_id: 'sbi' })
  })

  it('unlock posts the password and refreshes the document', async () => {
    const unlockCalls: unknown[] = []
    handlers['/api/statements/a-1/documents/doc-1/unlock'] = (_u, init) => {
      unlockCalls.push(JSON.parse(String(init?.body)))
      return jsonResponse({ unlocked: true, document: { ...DOC, requires_password: false, state: 'DETECTED' } })
    }
    handlers['/api/statements/analyze'] = () =>
      jsonResponse({ analysis_id: 'a-1', expires_at: 'x', documents: [{ ...DOC, requires_password: true, state: 'REVIEW' }], summary: { total: 1, by_state: {}, groups: [] } })
    const { result } = renderWorkflow()
    await act(async () => {
      result.current.analyze()
    })
    await waitFor(() => expect(result.current.step).toBe('review'))
    act(() => result.current.setPassword('doc-1', 'secret'))
    await act(async () => {
      await result.current.unlock(DOC as never)
    })
    expect(unlockCalls[0]).toEqual({ password: 'secret' })
    expect(result.current.docs[0].document.requires_password).toBe(false)
  })

  it('process starts jobs, polls, and reports partial failure', async () => {
    handlers['/api/statements/a-1/process'] = () =>
      jsonResponse({
        started: [{ document_id: 'doc-1', job_id: 'job-1' }],
        skipped: [{ document_id: 'doc-2', reason: 'NOT_CONFIRMED' }],
      })
    let jobStatus = 'running'
    handlers['/api/jobs/job-1'] = () => jsonResponse({ id: 'job-1', status: jobStatus, result_data: null })
    const { result } = renderWorkflow()
    await act(async () => {
      result.current.analyze()
    })
    await waitFor(() => expect(result.current.step).toBe('review'))
    await act(async () => {
      await result.current.process()
    })
    expect(result.current.step).toBe('processing')
    jobStatus = 'completed'
    await waitFor(() => expect(result.current.step).toBe('report'), { timeout: 4000 })
    expect(result.current.allDone).toBe(true)
    expect(result.current.anyFailed).toBe(false)
  }, 10000)
})
