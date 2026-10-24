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
export type OcrReading = 'thorough' | 'fast'

/** What the backend says about reading scanned statements (GET /api/statements/banks → `ocr`). */
export interface OcrCatalog {
  /** true only when scanned statements will actually be processed in this deployment */
  enabled: boolean
  reading_modes: OcrReading[]
  default_reading: OcrReading | null
  max_pages: number | null
}

const OCR_READINGS: readonly OcrReading[] = ['thorough', 'fast']

/** Defensive: anything malformed means OCR is off, so the UI never offers a reading that would fail. */
export function parseOcrCatalog(raw: unknown): OcrCatalog | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (o.enabled !== true) return { enabled: false, reading_modes: [], default_reading: null, max_pages: null }
  const modes = Array.isArray(o.reading_modes)
    ? o.reading_modes.filter((m): m is OcrReading => OCR_READINGS.includes(m as OcrReading))
    : []
  const reading_modes = modes.length ? modes : [...OCR_READINGS]
  const def = OCR_READINGS.includes(o.default_reading as OcrReading) ? (o.default_reading as OcrReading) : reading_modes[0]
  return {
    enabled: true,
    reading_modes,
    default_reading: def,
    max_pages: typeof o.max_pages === 'number' ? o.max_pages : null,
  }
}

/** A document with no text layer: only OCR can read it. */
export function isScanned(d: { capability?: { capability?: string } | null }): boolean {
  return d.capability?.capability === 'SCANNED'
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
  capability?: { capability?: string } | null
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
/** Additive `all_banks` entry + per-bank support state (docs/operations/UI_BANK_STATES.md). */
export type SupportState = 'verified' | 'review_required' | 'legacy' | 'coming_soon' | 'unsupported'

export interface BankCatalogEntry {
  id: string
  name: string
  support_state: SupportState
  reason?: string | null
}

export interface BankOption {
  id: string
  name: string
  pipeline_name?: string | null
  engines?: string[]
  v2_served?: boolean
  support_state?: SupportState | null
}

export interface BankCatalog {
  banks: BankOption[]
  all_banks: BankCatalogEntry[]
  ocr?: OcrCatalog | null
}
export interface Decision {
  document_id: string
  action: 'CONFIRM' | 'OVERRIDE'
  bank_id?: string
  account_type?: string
}

export interface ProcessOptions {
  fullName?: string
  perDocument?: Record<string, { account_type?: string; statement_label?: string; ocr_reading?: OcrReading }>
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

/** Full catalog: servable `banks` (unchanged contract) + every known bank with its support_state. */
export async function listBankCatalog(): Promise<BankCatalog> {
  const data = await parse<Partial<BankCatalog>>(await fetch('/api/statements/banks', { headers: await authHeaders(false) }))
  return { banks: data.banks ?? [], all_banks: data.all_banks ?? [], ocr: parseOcrCatalog(data.ocr) }
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
  analysisId: string,
  opts: ProcessOptions = {}
): Promise<{ started: { document_id: string; job_id: string }[]; skipped: { document_id: string; reason: string }[] }> {
  const payload: Record<string, unknown> = {}
  if (opts.fullName != null && opts.fullName !== '') payload.full_name = opts.fullName
  if (opts.perDocument && Object.keys(opts.perDocument).length) {
    payload.documents = Object.entries(opts.perDocument).map(([document_id, f]) => ({ document_id, ...f }))
  }
  return parse(
    await fetch(`/api/statements/${encodeURIComponent(analysisId)}/process`, {
      method: 'POST',
      headers: await authHeaders(true),
      body: JSON.stringify(payload),
    })
  )
}

export interface JobStatus {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message?: string | null
  result_data?: Record<string, unknown> | null
  bank_name?: string | null
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
