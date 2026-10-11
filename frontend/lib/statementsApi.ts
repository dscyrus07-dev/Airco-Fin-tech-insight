'use client'

import { getValidSessionAccessToken } from './sessionToken'

export type CoarseState = 'DETECTED' | 'REVIEW' | 'UNKNOWN' | 'UNSUPPORTED' | 'ERROR'
export type Confidence = 'VERY_HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'

export interface DetectedBank {
  id: string
  name: string
  confidence: Confidence
  score: number
  supported: boolean
}
export interface EvidenceItem {
  type: string
  kind: string
  label: string
  value: string
  weight?: number
}
export interface AnalyzedDocument {
  document_id: string
  filename: string
  size_bytes: number
  state: CoarseState
  detail_state: string
  message: string
  requires_password: boolean
  requires_confirmation: boolean
  bank: DetectedBank | null
  suggestion?: { id: string; name: string; confidence: Confidence } | null
  evidence: EvidenceItem[]
  layout: { id: string; confidence: Confidence; description: string; parser_family: string | null }
  workflow_status: 'AWAITING_CONFIRMATION' | 'CONFIRMED' | 'PROCESSING' | 'BLOCKED'
  effective_bank: { id: string; name: string } | null
  hint_conflict?: boolean
  job_id: string | null
}
export interface BankGroup {
  bank_id: string | null
  bank_name: string
  count: number
  confidence: Confidence | null
  document_ids: string[]
}
export interface AnalysisView {
  analysis_id: string
  expires_at: string
  documents: AnalyzedDocument[]
  summary: { total: number; by_state: Record<string, number>; groups: BankGroup[] }
}
export interface BankOption {
  id: string
  name: string
  pipeline_name?: string | null
  engines?: string[]
  v2_served?: boolean
}
export interface Decision {
  document_id: string
  action: 'CONFIRM' | 'OVERRIDE'
  bank_id?: string
}

export class StatementsApiError extends Error {
  status: number
  code?: string
  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function authHeaders(json: boolean): Promise<Record<string, string>> {
  const token = await getValidSessionAccessToken()
  if (!token) throw new StatementsApiError('Your session has expired. Please sign in again.', 401)
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (json) headers['Content-Type'] = 'application/json'
  return headers
}

async function parse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new StatementsApiError(data?.message || 'Request failed. Please try again.', response.status, data?.code)
  return data as T
}

export async function analyzeStatements(files: File[], passwords: Record<string, string> = {}): Promise<AnalysisView> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f, f.name))
  if (Object.keys(passwords).length) form.append('passwords', JSON.stringify(passwords))
  return parse(await fetch('/api/statements/analyze', { method: 'POST', body: form, headers: await authHeaders(false) }))
}

export async function listBanks(): Promise<BankOption[]> {
  const data = await parse<{ banks: BankOption[] }>(await fetch('/api/statements/banks', { headers: await authHeaders(false) }))
  return data.banks
}

export async function confirmDocuments(
  analysisId: string,
  decisions: Decision[],
  confirmAllDetected = false
): Promise<AnalysisView> {
  return parse(
    await fetch(`/api/statements/${encodeURIComponent(analysisId)}/confirm`, {
      method: 'POST',
      headers: await authHeaders(true),
      body: JSON.stringify({ documents: decisions, confirm_all_detected: confirmAllDetected }),
    })
  )
}

export async function unlockDocument(
  analysisId: string,
  documentId: string,
  password: string
): Promise<{ unlocked: boolean; document: AnalyzedDocument }> {
  return parse(
    await fetch(`/api/statements/${encodeURIComponent(analysisId)}/documents/${encodeURIComponent(documentId)}/unlock`, {
      method: 'POST',
      headers: await authHeaders(true),
      body: JSON.stringify({ password }),
    })
  )
}

export async function processConfirmed(
  analysisId: string
): Promise<{ started: { document_id: string; job_id: string }[]; skipped: { document_id: string; reason: string }[] }> {
  return parse(
    await fetch(`/api/statements/${encodeURIComponent(analysisId)}/process`, {
      method: 'POST',
      headers: await authHeaders(true),
      body: '{}',
    })
  )
}

export interface JobStatus {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message?: string | null
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return parse(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { headers: await authHeaders(false) }))
}

export async function downloadJobReport(jobId: string, filename: string): Promise<void> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/download`, { headers: await authHeaders(false) })
  if (!res.ok) throw new StatementsApiError('The report is not ready yet.', res.status)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename.replace(/\.pdf$/i, '')}_report.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}
