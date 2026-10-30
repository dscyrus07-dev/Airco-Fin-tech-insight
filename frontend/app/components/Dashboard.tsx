'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { buildUserHeadersFromToken, getValidSessionAccessToken } from '../../lib/sessionToken'
import Header from './layout/Header'
import StepForm from './layout/StepForm'
import UploadStep from './upload/UploadStep'
import ModeSelection from './upload/ModeSelection'
import ProcessingStep from './processing/ProcessingStep'
import ResultStep from './results/ResultStep'
import StatementWorkflow from './workflow/StatementWorkflow'
import { unifiedEntry } from '@/lib/flags'
import StatsStrip from './experience/StatsStrip'
import ProgressPanel from './experience/ProgressPanel'
import HelpCenter from './experience/HelpCenter'
import {
  EMPTY_LOCAL, computeXp, countBanks, dayKey, levelFor, readLocal, streakFrom, writeLocal,
} from '@/lib/gamification'
import type { LocalState, ProgressInput } from '@/lib/gamification'
import {
  FileText,
  FileSpreadsheet,
  Download,
  Trash2,
  UserCircle2,
} from 'lucide-react'
import { BankStatementFileItem, UserDetails, ProcessingResult, ProcessingMode, Step, JobSubmitted, ProfileHistoryResponse, UserUploadHistoryItem, UserReportHistoryItem, StatementTypeSelection, StatementEngineBlock } from '@/types'
import { SUPPORTED_BANK_OPTIONS } from '@/lib/banks'
import { listBanks } from '../../lib/statementsApi'
import { engineNeedsAttention, parseStatementEngine } from '@/lib/statementEngine'
import VerificationBadge from './results/engine/VerificationBadge'

type BatchResultItem = {
  id: string
  bankName: string
  fileName: string
  result: ProcessingResult
  errorMessage?: string
}

const formatBatchLabel = (batchId: string) => {
  if (!batchId) return 'Unknown batch'
  // Avoid showing raw batch-... IDs in the profile UI.
  if (batchId.startsWith('batch-')) return 'Uploaded statements'
  return batchId.length > 18 ? `${batchId.slice(0, 18)}…` : batchId
}

const normalizeUploadStatus = (status?: string | null): 'Processed' | 'Pending' | 'Processing' | 'Failed' => {
  const normalized = (status || '').toLowerCase()
  if (normalized === 'completed' || normalized === 'processed' || normalized === 'success') return 'Processed'
  if (normalized === 'running' || normalized === 'processing' || normalized === 'in_progress') return 'Processing'
  if (normalized === 'failed' || normalized === 'error') return 'Failed'
  return 'Pending'
}

const formatRetentionLabel = (
  status?: string | null,
  daysLeft?: number | null,
  deletedAt?: string | null,
) => {
  const normalizedStatus = (status || '').toLowerCase()
  if (normalizedStatus === 'deleted' || deletedAt) return 'Deleted'
  if (normalizedStatus === 'queued for deletion' || normalizedStatus === 'scheduled' || normalizedStatus === 'deleting') {
    return 'Queued for deletion'
  }
  if (daysLeft === 0) return 'Deletes today'
  if (daysLeft === 1) return '1 day left'
  if (typeof daysLeft === 'number' && daysLeft > 1) return `${daysLeft} days left`
  return status || 'Retention pending'
}

const createBatchId = () => `batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const PASSWORD_ERROR_CODES = new Set(['PDF_PASSWORD_REQUIRED', 'PDF_PASSWORD_INVALID'])

const getUploadErrorCode = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') return undefined
  const typedError = error as { code?: string; cause?: { code?: string } }
  return typedError.code || typedError.cause?.code
}

const APP_API_BASE = '/api'

type SavedFormState = {
  userDetails?: Partial<UserDetails>
  mode?: ProcessingMode
  apiKey?: string
  step?: number
}

function readSavedFormState(): SavedFormState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem('airco-form-data')
    return raw ? (JSON.parse(raw) as SavedFormState) : null
  } catch (e) {
    console.error('Failed to load saved form data:', e)
    return null
  }
}

/** Download a report with the user's bearer token (plain links cannot send it). */
async function downloadWithAuth(url: string, fallbackName: string): Promise<void> {
  const token = await getValidSessionAccessToken()
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : undefined })
  if (!res.ok) {
    window.alert('The report could not be downloaded. It may have expired.')
    return
  }
  const match = /filename="?([^";]+)"?/i.exec(res.headers.get('content-disposition') || '')
  const blobUrl = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = match?.[1] || fallbackName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(blobUrl)
}

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [bankNames, setBankNames] = useState<string[]>(SUPPORTED_BANK_OPTIONS.map((b) => b.name))
  useEffect(() => {
    let cancelled = false
    listBanks()
      .then((banks) => {
        if (!cancelled && banks?.length) setBankNames(banks.filter((b) => b.id !== 'other').map((b) => b.name))
      })
      .catch(() => undefined) // keep the documented fallback list
    return () => { cancelled = true }
  }, [])

  const [savedForm] = useState<SavedFormState | null>(readSavedFormState)
  const savedDetails = savedForm?.userDetails || {}
  const savedStep = savedForm?.step || 1
  const [step, setStep] = useState<Step>((savedStep === 4 ? 3 : savedStep) as Step)
  const [filesTab, setFilesTab] = useState<'uploaded' | 'reports'>('uploaded')
  const [isProfilePanelOpen, setIsProfilePanelOpen] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set())
  const [userDetails, setUserDetails] = useState<UserDetails>({
    fullName: savedDetails.fullName || '',
    accountType: savedDetails.accountType || '',
    bankName: savedDetails.bankName || '',
    selectedBanks: Array.isArray(savedDetails.selectedBanks)
      ? savedDetails.selectedBanks
      : savedDetails.bankName
        ? [savedDetails.bankName]
        : [],
  })
  const [filesByBank, setFilesByBank] = useState<Record<string, BankStatementFileItem[]>>({})
  const [batchId, setBatchId] = useState<string>(createBatchId())
  const [batchQueue, setBatchQueue] = useState<BankStatementFileItem[]>([])
  const [batchResults, setBatchResults] = useState<BatchResultItem[]>([])
  const [currentBatchIndex, setCurrentBatchIndex] = useState(0)
  const [activeBatchFile, setActiveBatchFile] = useState<BankStatementFileItem | null>(null)
  const [mode, setMode] = useState<ProcessingMode>(savedForm?.mode || 'free')
  const [apiKey, setApiKey] = useState('') // never restored from storage: API keys stay in memory only
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [historyReloadKey, setHistoryReloadKey] = useState(0)
  const [historySummary, setHistorySummary] = useState<ProfileHistoryResponse['summary']>({
    total_uploads: 0,
    processed_files: 0,
    generated_reports: 0,
    total_batches: 0,
    latest_account_type: null,
  })
  const [historyUser, setHistoryUser] = useState<ProfileHistoryResponse['user'] | null>(null)
  const [historyBatches, setHistoryBatches] = useState<NonNullable<ProfileHistoryResponse['batches']>>([])

  const [local, setLocal] = useState<LocalState>(EMPTY_LOCAL)
  useEffect(() => {
    const l = readLocal()
    const today = dayKey()
    const next = l.visitDays.includes(today) ? l : { ...l, visitDays: [...l.visitDays, today].slice(-30) }
    setLocal(next)
    if (next !== l) writeLocal(next)
  }, [])
  const updateLocal = useCallback((patch: Partial<LocalState>) => {
    setLocal((prev) => {
      const next = { ...prev, ...patch }
      writeLocal(next)
      return next
    })
  }, [])

  const handleLogout = useCallback(async () => {
    const confirmed = window.confirm(
      'Are you sure you want to sign out? You will be redirected to the login page.'
    )

    if (!confirmed) return

    await logout()
    setIsProfilePanelOpen(false)
  }, [logout])

  const [uploadedStatements, setUploadedStatements] = useState<Array<{
    id: string
    name: string
    displayName?: string
    bank: string
    date: string
    batchId?: string | null
    statementLabel?: string | null
    accountType?: string | null
    status: 'Processed' | 'Pending' | 'Processing' | 'Failed'
    retentionStatus?: string | null
    retentionDaysLeft?: number | null
    retentionExpiresAt?: string | null
    deletedAt?: string | null
    statement_engine?: StatementEngineBlock | null
  }>>([])

  const [generatedReports, setGeneratedReports] = useState<Array<{
    id: string
    name: string
    displayName?: string
    bank: string
    date: string
    batchId?: string | null
    statementLabel?: string | null
    accountType?: string | null
    downloadUrl: string
    retentionStatus?: string | null
    retentionDaysLeft?: number | null
    retentionExpiresAt?: string | null
    deletedAt?: string | null
    statement_engine?: StatementEngineBlock | null
  }>>([])

  const [needsReviewOnly, setNeedsReviewOnly] = useState(false)

  // Form state restores from localStorage via lazy useState initializers
  // (readSavedFormState above) — no mount effect needed.

  useEffect(() => {
    const dataToSave = {
      userDetails,
      mode,
      step,
      timestamp: Date.now(),
    }
    localStorage.setItem('airco-form-data', JSON.stringify(dataToSave))
  }, [userDetails, mode, step])

  // Named function expression so the retry path can safely reference itself.
  const loadProfileHistory = useCallback(async function loadProfileHistory(isRetried = false) {
    const token = await getValidSessionAccessToken()
    if (!token) return

    try {
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
      Object.assign(headers, buildUserHeadersFromToken(token))
      const response = await fetch(`${APP_API_BASE}/profile/history`, {
        headers,
      })
      const data = await response.json().catch(() => null)
      if (!response.ok || !data) {
        return
      }

      setHistoryUser(data.user)
      setHistorySummary(data.summary)
      setHistoryBatches(data.batches || [])
      setUploadedStatements(
        (data.uploads || []).map((item: any) => ({
          id: item.job_id,
          name: item.name,
          displayName: item.display_name || item.name,
          bank: item.bank_name || 'Unknown',
          date: item.created_at ? new Date(item.created_at).toISOString().split('T')[0] : '',
          batchId: item.batch_id || null,
          statementLabel: item.statement_label || null,
          retentionStatus: item.retention_status || null,
          retentionDaysLeft: typeof item.retention_days_left === 'number' ? item.retention_days_left : null,
          retentionExpiresAt: item.retention_expires_at || null,
          deletedAt: item.deleted_at || null,
          status: normalizeUploadStatus(item.status),
          statement_engine: item.statement_engine || null,
        }))
      )
      setGeneratedReports(
        (data.reports || []).map((item: any) => ({
          id: item.job_id,
          name: item.name,
          displayName: item.display_name || item.name,
          bank: item.bank_name || 'Unknown',
          date: item.created_at ? new Date(item.created_at).toISOString().split('T')[0] : '',
          batchId: item.batch_id || null,
          statementLabel: item.statement_label || null,
          downloadUrl: `/api/jobs/${item.job_id}/download`,
          retentionStatus: item.retention_status || null,
          retentionDaysLeft: typeof item.retention_days_left === 'number' ? item.retention_days_left : null,
          retentionExpiresAt: item.retention_expires_at || null,
          deletedAt: item.deleted_at || null,
          statement_engine: item.statement_engine || null,
        }))
      )
    } catch (fetchError) {
      if (isRetried || !(fetchError instanceof TypeError)) {
        console.warn('Failed to load profile history:', fetchError)
        return
      }
      window.setTimeout(() => void loadProfileHistory(true), 1000)
    }
  }, [])

  useEffect(() => {
    loadProfileHistory()
  }, [loadProfileHistory, historyReloadKey])

  const handleUserDetails = (details: UserDetails) => {
    setUserDetails(details)
    setFilesByBank((prev) => {
      const next: Record<string, BankStatementFileItem[]> = {}
      details.selectedBanks.forEach((bank) => {
        next[bank] = prev[bank] || []
      })
      return next
    })
    setStep(2)
  }

  const handleFilesChange = (nextFilesByBank: Record<string, BankStatementFileItem[]>) => {
    setFilesByBank(nextFilesByBank)
  }

  const handleUploadContinue = useCallback(() => {
    const queue = userDetails.selectedBanks.flatMap((bankName) => filesByBank[bankName] || [])

    const missingTypeFile = queue.find((item) => !item.accountType)
    if (missingTypeFile) {
      setError(`Please select a bank statement type for ${missingTypeFile.file.name} before continuing.`)
      return
    }

    if (queue.length === 0) {
      setError('Please upload at least one PDF statement before continuing.')
      return
    }

    setBatchId(createBatchId())
    setBatchQueue(queue)
    setBatchResults([])
    setCurrentBatchIndex(0)
    setActiveBatchFile(null)
    setResult(null)
    setJobId(null)
    setError(null)
    setStep(3)
  }, [filesByBank, userDetails.selectedBanks])

  const submitBatchItem = useCallback(async (item: BankStatementFileItem, selectedMode: ProcessingMode, key?: string) => {
    setActiveBatchFile(item)
    setIsProcessing(true)
    setError(null)

    const uploadDate = new Date().toISOString().split('T')[0]
    const uploadId = `${item.id}-${Date.now()}`

    setUploadedStatements((prev) => [...prev, {
      id: uploadId,
      name: item.file.name,
      bank: item.bankName,
      date: uploadDate,
      accountType: item.accountType,
      status: 'Processing',
    }])

    let currentPassword = item.pdfPassword

    const recordBatchFailure = (message: string) => {
      const failedResult: ProcessingResult = {
        status: 'error',
        mode: selectedMode || 'free',
        excel_url: '',
        pdf_url: '',
      }

      setBatchResults((prev) => [...prev, {
        id: item.id,
        bankName: item.bankName,
        fileName: item.file.name,
        result: failedResult,
        errorMessage: message,
      }])
    }

    while (true) {
      try {
        const data = await uploadStatement({
          file: item.file,
          userDetails,
          mode: selectedMode,
          apiKey: key,
          pdfPassword: currentPassword,
          batchId,
          statementLabel: item.statementLabel,
          bankName: item.bankName,
          accountType: item.accountType,
        })
        setJobId(data.job_id)
        return
      } catch (err) {
        const code = getUploadErrorCode(err)
        if (code && PASSWORD_ERROR_CODES.has(code)) {
          const enteredPassword = window.prompt(
            `${item.file.name} is password-protected. Enter the PDF password to continue:`,
            currentPassword || ''
          )

          if (!enteredPassword) {
            const message = 'A password is required to process this PDF.'
            setError(message)
            setUploadedStatements((prev) =>
              prev.map((f) => (f.id === uploadId ? { ...f, status: 'Failed' } : f))
            )
            recordBatchFailure(message)
            setStep(3)
            setIsProcessing(false)
            setJobId(null)
            return
          }

          currentPassword = enteredPassword
          setActiveBatchFile({ ...item, pdfPassword: enteredPassword })
          continue
        }

        const message = err instanceof Error ? err.message : 'Something went wrong. Please try again.'
        setError(message)
        setUploadedStatements((prev) =>
          prev.map((f) => (f.id === uploadId ? { ...f, status: 'Failed' } : f))
        )
        recordBatchFailure(message)
        setStep(3)
        setIsProcessing(false)
        setJobId(null)
        return
      }
    }
  }, [batchId, userDetails])

  const handleProcessingComplete = useCallback((data: ProcessingResult) => {
    const uploadDate = new Date().toISOString().split('T')[0]

    setResult(data)
    setJobId(null)
    setUploadedStatements((prev) =>
      prev.map((f) => (f.status === 'Processing' ? { ...f, status: 'Processed', statement_engine: data.statement_engine || null } : f))
    )

    if (data.excel_url && activeBatchFile) {
      const excelBase =
        (data.excel_url.split('/').pop() || '').replace(/\.xlsx$/i, '') ||
        `${activeBatchFile.bankName}_${activeBatchFile.file.name.replace(/\.pdf$/i, '')}`
      setGeneratedReports((prev) => [...prev, {
        id: `${Date.now()}_report`,
        name: excelBase.endsWith('.xlsx') ? excelBase : `${excelBase}.xlsx`,
        displayName: excelBase.endsWith('.xlsx') ? excelBase : `${excelBase}.xlsx`,
        bank: activeBatchFile.bankName,
        date: uploadDate,
        accountType: activeBatchFile.accountType,
        downloadUrl: data.excel_url,
        statement_engine: data.statement_engine || null,
      }])
      setBatchResults((prev) => [...prev, {
        id: activeBatchFile.id,
        bankName: activeBatchFile.bankName,
        fileName: activeBatchFile.file.name,
        result: data,
      }])
    }

    const nextIndex = currentBatchIndex + 1
    if (nextIndex < batchQueue.length) {
      setCurrentBatchIndex(nextIndex)
      void submitBatchItem(batchQueue[nextIndex], mode, apiKey || undefined)
      return
    }

    setStep(5)
    setIsProcessing(false)
    setActiveBatchFile(null)
    loadProfileHistory()
  }, [activeBatchFile, apiKey, batchQueue, currentBatchIndex, loadProfileHistory, mode, submitBatchItem])

  const handleProcessingError = useCallback((message: string) => {
    // Mark current file as failed but continue with batch
    setError(message)
    setJobId(null)
    setUploadedStatements(prev =>
      prev.map((f) => (f.status === 'Processing' ? { ...f, status: 'Failed' } : f))
    )
    
    // Add failed result to batch results for tracking
    if (activeBatchFile) {
      const failedResult: ProcessingResult = {
        status: 'error',
        mode: mode || 'free',
        excel_url: '',
        pdf_url: '',
      }
      setBatchResults((prev) => [...prev, {
        id: activeBatchFile.id,
        bankName: activeBatchFile.bankName,
        fileName: activeBatchFile.file.name,
        result: failedResult,
        errorMessage: message,
      }])
    }
    
    // Continue with next file in batch
    const nextIndex = currentBatchIndex + 1
    if (nextIndex < batchQueue.length) {
      setCurrentBatchIndex(nextIndex)
      void submitBatchItem(batchQueue[nextIndex], mode, apiKey || undefined)
      return
    }
    
    // All files processed (some may have failed)
    setIsProcessing(false)
    setActiveBatchFile(null)
    setStep(5) // Go to results page to show partial results
    loadProfileHistory()
  }, [activeBatchFile, apiKey, batchQueue, currentBatchIndex, loadProfileHistory, mode, submitBatchItem])

  const handleModeSelect = async (selectedMode: ProcessingMode, key?: string) => {
    if (batchQueue.length === 0) return

    setMode(selectedMode)
    if (key) setApiKey(key)
    setIsProcessing(true)
    setError(null)
    setStep(4)
    setCurrentBatchIndex(0)
    setBatchResults([])
    await submitBatchItem(batchQueue[0], selectedMode, key)
  }

  const handleBack = () => {
    if (step === 2) setStep(1)
    else if (step === 3) setStep(2)
    else if (step === 5) setStep(3)
  }

  const handleReset = () => {
    setStep(1)
    setUserDetails({ fullName: '', accountType: '', bankName: '', selectedBanks: [] })
    setFilesByBank({})
    setBatchId(createBatchId())
    setBatchQueue([])
    setBatchResults([])
    setCurrentBatchIndex(0)
    setActiveBatchFile(null)
    setMode('free')
    setApiKey('')
    setJobId(null)
    setResult(null)
    setError(null)
    setIsProcessing(false)
    setSelectedFiles(new Set())
    setUploadedStatements([])
    setGeneratedReports([])
    localStorage.removeItem('airco-form-data')
  }

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsProfilePanelOpen(false)
    }
    if (isProfilePanelOpen) {
      document.addEventListener('keydown', handleEsc)
      return () => document.removeEventListener('keydown', handleEsc)
    }
  }, [isProfilePanelOpen])

  // Render-time correction (React-documented "adjusting state" pattern):
  // step 4 requires an in-flight job; converge by stepping back to 3.
  if (step === 4 && !jobId && !isProcessing) {
    setStep(3)
  }

  const stepLabels = ['Details', 'Upload', 'Mode', 'Processing', 'Report']
  const effectiveUser = historyUser || user
  const profileName =
    effectiveUser?.name
    || [effectiveUser?.given_name, effectiveUser?.family_name].filter(Boolean).join(' ')
    || userDetails.fullName.trim()
    || 'Your Workspace'
  const profileEmail = effectiveUser?.email || 'No email available'
  const accountTypeLabel = historySummary.latest_account_type
    || (userDetails.accountType
      ? userDetails.accountType.charAt(0).toUpperCase() + userDetails.accountType.slice(1)
      : 'Not set')
  const profileBatchCount = useMemo(
    () => historySummary.total_batches ?? historyBatches.length,
    [historySummary.total_batches, historyBatches.length]
  )

  const progress = useMemo(() => {
    const input: ProgressInput = {
      uploads: historySummary.total_uploads ?? 0,
      processed: historySummary.processed_files ?? 0,
      reports: historySummary.generated_reports ?? 0,
      batches: profileBatchCount ?? 0,
      banksUsed: countBanks(historyBatches.flatMap((b) => b.bank_names ?? [])),
      verifiedReports: 0,
      guideOpened: local.guideOpened,
      limitsOpened: local.limitsOpened,
      streakDays: streakFrom(local.visitDays),
    }
    const lv = levelFor(computeXp(input))
    return { input, levelLabel: `Lv ${lv.level.index} \u00b7 ${lv.level.name}` }
  }, [historySummary, profileBatchCount, historyBatches, local])

  const getVisibleHistoryIds = useCallback((tab: 'uploaded' | 'reports') => {
    if (historyBatches.length > 0) {
      if (tab === 'uploaded') {
        return historyBatches.flatMap((batch) => batch.uploads.map((item) => item.job_id))
      }

      return historyBatches.flatMap((batch) => batch.reports.map((item) => item.job_id))
    }

    return tab === 'uploaded'
      ? uploadedStatements.map((item) => item.id)
      : generatedReports.map((item) => item.id)
  }, [generatedReports, historyBatches, uploadedStatements])

  const itemNeedsReview = (item: unknown) =>
    engineNeedsAttention(parseStatementEngine((item as { statement_engine?: unknown })?.statement_engine))

  const renderHistoryRow = (
    item: UserUploadHistoryItem | UserReportHistoryItem,
    tab: 'uploaded' | 'reports',
  ) => {
    const isUpload = tab === 'uploaded'
    const itemId = item.job_id
    const createdLabel = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Unknown date'
    const retentionLabel = formatRetentionLabel(item.retention_status, item.retention_days_left, item.deleted_at)
    const retentionTone = (item.deletion_status || '').toLowerCase() === 'deleted'
      ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800/60 dark:bg-red-950/50 dark:text-red-300'
      : (item.deletion_status || '').toLowerCase() === 'queued for deletion' || (item.deletion_status || '').toLowerCase() === 'deleting' || (item.deletion_status || '').toLowerCase() === 'scheduled'
        ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/50 dark:text-amber-300'
        : 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
    const uploadStatus = isUpload
      ? normalizeUploadStatus((item as UserUploadHistoryItem).status)
      : null
    const title = item.display_name || item.name
    const itemEngine = parseStatementEngine((item as any).statement_engine)

    const statementMetadata = (item as any).statement_metadata

    const renderStatementMetadataChips = () => {
      if (!statementMetadata) return null

      return (
        <div className="flex flex-wrap items-center gap-1.5">
          {statementMetadata.has_salary && (
            <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/50 dark:text-emerald-300">
              Salary: ₹{Number(statementMetadata.salary_amount || 0).toLocaleString()}
            </span>
          )}
          {statementMetadata.has_loan_repayment && (
            <span className="rounded-md border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11px] font-medium text-orange-700 dark:border-orange-800/60 dark:bg-orange-950/50 dark:text-orange-300">
              Loan: ₹{Number(statementMetadata.loan_repayment_amount || 0).toLocaleString()}
            </span>
          )}
          <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:border-blue-800/60 dark:bg-blue-950/50 dark:text-blue-300">
            Credits: {statementMetadata.total_credits ?? 0}
          </span>
          <span className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:border-indigo-800/60 dark:bg-indigo-950/50 dark:text-indigo-300">
            Debits: {statementMetadata.total_debits ?? 0}
          </span>
        </div>
      )
    }

    const rawStatus = isUpload ? (item as UserUploadHistoryItem).status : null
    const statusDotClass =
      uploadStatus === 'Processed'
        ? 'bg-emerald-500'
        : uploadStatus === 'Processing'
          ? 'bg-amber-500 animate-pulse'
          : uploadStatus === 'Failed'
            ? 'bg-red-500'
            : 'bg-slate-400'
    const statusBadgeClass =
      uploadStatus === 'Processed'
        ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/50 dark:text-emerald-300'
        : uploadStatus === 'Processing'
          ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/50 dark:text-amber-300'
          : uploadStatus === 'Failed'
            ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800/60 dark:bg-red-950/50 dark:text-red-300'
            : 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'

    return (
      <div
        key={itemId}
        className="group rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-2xs transition hover:border-[#01275C]/30 dark:border-slate-700/80 dark:bg-[#0F2342] dark:hover:border-blue-400/40"
      >
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={selectedFiles.has(itemId)}
            onChange={(e) => {
              const newSelected = new Set(selectedFiles)
              if (e.target.checked) {
                newSelected.add(itemId)
              } else {
                newSelected.delete(itemId)
              }
              setSelectedFiles(newSelected)
            }}
            className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-[#01275C] focus:ring-[#01275C] dark:border-slate-600"
          />
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
              isUpload
                ? 'bg-[#01275C]/10 text-[#01275C] dark:bg-blue-500/20 dark:text-blue-300'
                : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400'
            }`}
          >
            {isUpload ? <FileText className="h-4 w-4" /> : <FileSpreadsheet className="h-4 w-4" />}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p
                  title={title}
                  className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100"
                >
                  {title}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                  <span>{createdLabel}</span>
                  {(item.source === 'api' || Boolean(item.api_key_id)) && (
                    <span className="rounded-md border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
                      API
                    </span>
                  )}
                  <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${retentionTone}`}>
                    {retentionLabel}
                  </span>
                  {item.retention_expires_at && (
                    <span className="text-[11px] text-slate-400 dark:text-slate-500">
                      Deletes {new Date(item.retention_expires_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                {isUpload ? (
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${statusBadgeClass}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${statusDotClass}`} />
                    {rawStatus}
                  </span>
                ) : (
                  <button
                    type="button"
                    aria-label="Download report"
                    onClick={() => void downloadWithAuth(`/api/jobs/${itemId}/download`, 'report.xlsx')}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:border-[#01275C]/40 hover:bg-[#01275C] hover:text-white dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-blue-600"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Excel</span>
                  </button>
                )}
                <button
                  type="button"
                  aria-label={`Delete ${title}`}
                  onClick={async () => {
                    const confirmed = window.confirm(
                      `Are you sure you want to delete "${item.display_name || item.name}"?`
                    )
                    if (!confirmed) return

                    try {
                      const token = await getValidSessionAccessToken()
                      const headers: Record<string, string> = token
                        ? { Authorization: `Bearer ${token}`, ...buildUserHeadersFromToken(token) }
                        : {}

                      const response = await fetch(`${APP_API_BASE}/profile/files/${itemId}`, {
                        method: 'DELETE',
                        headers,
                      })

                      if (response.ok) {
                        setSelectedFiles((prev) => {
                          const next = new Set(prev)
                          next.delete(itemId)
                          return next
                        })
                        loadProfileHistory()
                      } else {
                        alert(`Failed to delete ${isUpload ? 'file' : 'report'}. Please try again.`)
                      }
                    } catch (deleteError) {
                      console.error(`Failed to delete ${isUpload ? 'file' : 'report'}:`, deleteError)
                      alert(`Failed to delete ${isUpload ? 'file' : 'report'}. Please try again.`)
                    }
                  }}
                  className="rounded-lg p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50 dark:hover:text-red-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            {(itemEngine || statementMetadata) && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2 dark:border-slate-800">
                <VerificationBadge engine={itemEngine} />
                {renderStatementMetadataChips()}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <main className="bg-app min-h-screen">
      <Header onProfileClick={() => setIsProfilePanelOpen(true)} levelLabel={progress.levelLabel} />

      <div className="mx-auto w-full px-4 pb-16 sm:px-6 lg:px-10 xl:px-12">
        {unifiedEntry() && (
          <div className="mb-6">
            <StatsStrip
              uploads={historySummary.total_uploads}
              processed={historySummary.processed_files}
              reports={historySummary.generated_reports}
              batches={profileBatchCount}
            />
          </div>
        )}

        <div className={unifiedEntry() ? 'grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px] xl:gap-8' : ''}>
        <div className={unifiedEntry() ? 'min-w-0' : 'max-w-4xl mx-auto'}>
          {unifiedEntry() ? (
            <StatementWorkflow
              profileName={profileName}
              onJobsSettled={() => setHistoryReloadKey((k) => k + 1)}
            />
          ) : (
          <section>
            <div className="mb-8 flex items-center justify-center gap-1.5">
              {[1, 2, 3, 4, 5].map((s) => (
                <div key={s} className="flex items-center gap-1.5">
                  <div className="flex flex-col items-center">
                    <div
                      className={`h-1 w-10 rounded-full transition-colors ${
                        s <= step ? 'bg-black' : 'bg-neutral-200'
                      }`}
                    />
                    <span
                      className={`mt-1 text-[9px] ${
                        s <= step ? 'text-neutral-600' : 'text-neutral-300'
                      }`}
                    >
                      {stepLabels[s - 1]}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-border p-6 shadow-sm sm:p-8 lg:p-10">
              {error && step !== 4 && (
                <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {step === 1 && <StepForm onSubmit={handleUserDetails} initialDetails={userDetails} />}
              {step === 2 && (
                <UploadStep
                  selectedBanks={userDetails.selectedBanks}
                  filesByBank={filesByBank}
                  onFilesChange={handleFilesChange}
                  onContinue={handleUploadContinue}
                  isProcessing={false}
                />
              )}
              {step === 3 && <ModeSelection onSelect={handleModeSelect} isProcessing={isProcessing} />}
              {step === 4 && (
                <div className="space-y-4">
                  {batchQueue.length > 1 && activeBatchFile && (
                    <div className="rounded-lg border border-neutral-200 bg-neutral-50 px-4 py-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                        Batch progress
                      </p>
                      <p className="mt-1 text-sm text-black">
                        Processing {currentBatchIndex + 1} of {batchQueue.length}: {activeBatchFile.statementLabel}
                      </p>
                    </div>
                  )}
                  <ProcessingStep
                    key={jobId ?? 'no-job'}
                    jobId={jobId}
                    mode={mode}
                    fileName={activeBatchFile?.file?.name || null}
                    bankName={activeBatchFile?.bankName || null}
                    onComplete={handleProcessingComplete}
                    onError={handleProcessingError}
                  />
                </div>
              )}

              {step === 5 && result && <ResultStep result={result} batchResults={batchResults} />}

              {step !== 4 && (
                <div className="mt-6 flex items-center justify-between border-t border-neutral-100 pt-4">
                  {step > 1 ? (
                    <button
                      onClick={handleBack}
                      className="flex items-center gap-1 text-sm text-neutral-500 transition-colors hover:text-black"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
                      Back
                    </button>
                  ) : <div />}
                  {step === 5 ? (
                    <button
                      onClick={handleReset}
                      className="flex items-center gap-1 rounded-md bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-800"
                    >
                      New Statement
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
                    </button>
                  ) : <div />}
                </div>
              )}
            </div>

            <footer className="mt-12 space-y-3 text-center">
              <p className="text-xs font-medium text-neutral-400">
                Airco Insights - Financial Categorization Engine
              </p>
              <p className="mx-auto max-w-lg text-[11px] leading-relaxed text-neutral-400">
                Upload one or more bank statement PDFs and get fully categorized, structured Excel reports -
                with monthly summaries, category breakdowns, recurring transaction detection, and weekly analysis.
                Files are deleted automatically after 7 days.
              </p>

              <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                {bankNames.slice(0, 14).map((name) => (
                  <span
                    key={name}
                    className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] text-neutral-500"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                    {name}
                  </span>
                ))}
                {bankNames.length > 14 && (
                  <span className="inline-flex items-center rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] text-neutral-500">
                    and {bankNames.length - 14} more
                  </span>
                )}
              </div>

              <p className="mx-auto max-w-md text-[10px] leading-relaxed text-neutral-300">
                Airco Insights does not provide financial advice, predictions, or recommendations.
                The system only categorizes and structures transaction data.
              </p>
            </footer>
          </section>
          )}
        </div>
        {unifiedEntry() && (
          <div className="lg:sticky lg:top-24">
            <ProgressPanel
              input={progress.input}
              seenBadges={local.seenBadges}
              baselined={local.baselined}
              onSeen={(ids) => updateLocal({ seenBadges: ids, baselined: true })}
              onQuestClick={(t) => {
                if (t === 'guide' || t === 'limits') document.getElementById('help-center')?.scrollIntoView({ behavior: 'smooth' })
              }}
            />
          </div>
        )}
        </div>

        <div className="mt-8 w-full">
          <HelpCenter
            onGuideOpened={() => updateLocal({ guideOpened: true })}
            onLimitsOpened={() => updateLocal({ limitsOpened: true })}
          />
          <p className="mt-8 text-center text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            Airco Insights organises transaction data. It does not provide financial advice. Uploaded files are deleted automatically after 7 days.
          </p>
        </div>
      </div>

      {isProfilePanelOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-xs transition-opacity"
            onClick={() => setIsProfilePanelOpen(false)}
          />

          <aside
            aria-label="Profile and file history"
            className="fixed top-0 right-0 z-50 flex h-full w-full max-w-[580px] flex-col border-l border-slate-200/80 bg-white shadow-2xl transition-transform duration-300 ease-in-out dark:border-slate-800 dark:bg-[#08152B]"
          >
            <div className="flex items-center justify-between border-b border-slate-200/80 bg-white/95 px-6 py-4 backdrop-blur dark:border-slate-800 dark:bg-[#08152B]/95">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#01275C] text-white shadow-xs dark:bg-blue-600">
                  <UserCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">Profile</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Account summary & statement history</p>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close profile panel"
                onClick={() => setIsProfilePanelOpen(false)}
                className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 6-12 12"/><path d="m6 6 12 12"/></svg>
              </button>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
              <div className="rounded-2xl border border-slate-200/90 bg-slate-50/70 p-5 shadow-xs dark:border-slate-800 dark:bg-[#0B1B36]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3.5">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#01275C] to-[#0D3B82] text-base font-bold text-white shadow-sm ring-2 ring-[#A1B2CE]/40 dark:from-blue-600 dark:to-[#0D3B82]">
                      {(profileName || 'U').trim().charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-base font-bold text-slate-900 dark:text-white">{profileName}</p>
                      <p className="truncate text-xs text-slate-500 dark:text-slate-400">{profileEmail}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-2xs dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                      Account Type: <strong className="font-semibold text-[#01275C] dark:text-blue-300">{accountTypeLabel}</strong>
                    </span>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-4 gap-2.5">
                  <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-2.5 text-center shadow-2xs dark:border-slate-700/70 dark:bg-[#0F2342]">
                    <p className="text-lg font-bold text-[#01275C] dark:text-white">{historySummary.total_uploads}</p>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Uploads</p>
                  </div>
                  <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-2.5 text-center shadow-2xs dark:border-slate-700/70 dark:bg-[#0F2342]">
                    <p className="text-lg font-bold text-[#01275C] dark:text-white">{historySummary.processed_files}</p>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Processed</p>
                  </div>
                  <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-2.5 text-center shadow-2xs dark:border-slate-700/70 dark:bg-[#0F2342]">
                    <p className="text-lg font-bold text-[#01275C] dark:text-white">{historySummary.generated_reports}</p>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Reports</p>
                  </div>
                  <div className="rounded-xl border border-slate-200/70 bg-white px-3 py-2.5 text-center shadow-2xs dark:border-slate-700/70 dark:bg-[#0F2342]">
                    <p className="text-lg font-bold text-[#01275C] dark:text-white">{profileBatchCount}</p>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Batches</p>
                  </div>
                </div>

                <button
                  onClick={handleLogout}
                  className="mt-4 w-full rounded-xl border border-red-200/80 bg-red-50/90 px-4 py-2.5 text-xs font-semibold text-red-600 transition hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/50 dark:text-red-300 dark:hover:bg-red-950/80"
                >
                  Sign Out
                </button>
              </div>

              <div className="space-y-3.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">Files</h3>
                  <button
                    type="button"
                    onClick={() => setNeedsReviewOnly((v) => !v)}
                    aria-pressed={needsReviewOnly}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                      needsReviewOnly
                        ? 'border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-600 dark:bg-amber-950/70 dark:text-amber-200'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-[#0B1B36] dark:text-slate-300'
                    }`}
                  >
                    Needs review
                  </button>
                </div>

                <div className="grid grid-cols-2 rounded-xl border border-slate-200/80 bg-slate-100/90 p-1 text-xs font-semibold text-slate-600 dark:border-slate-800 dark:bg-[#0B1B36] dark:text-slate-400">
                  <button
                    type="button"
                    onClick={() => { setFilesTab('uploaded'); setSelectedFiles(new Set()) }}
                    className={`rounded-lg py-2 transition ${
                      filesTab === 'uploaded'
                        ? 'bg-[#01275C] text-white shadow-xs dark:bg-blue-600 dark:text-white'
                        : 'hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    Uploaded Statements
                  </button>
                  <button
                    type="button"
                    onClick={() => { setFilesTab('reports'); setSelectedFiles(new Set()) }}
                    className={`rounded-lg py-2 transition ${
                      filesTab === 'reports'
                        ? 'bg-[#01275C] text-white shadow-xs dark:bg-blue-600 dark:text-white'
                        : 'hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    Generated Reports
                  </button>
                </div>

                {selectedFiles.size > 0 && (
                  <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 dark:border-slate-700 dark:bg-[#0B1B36]">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{selectedFiles.size} selected</span>
                      <button
                        onClick={() => {
                          setSelectedFiles(new Set(getVisibleHistoryIds(filesTab)))
                        }}
                        className="text-xs font-medium text-[#01275C] hover:underline dark:text-blue-400"
                      >
                        Select All
                      </button>
                      <button
                        onClick={() => setSelectedFiles(new Set())}
                        className="text-xs font-medium text-slate-500 hover:underline dark:text-slate-400"
                      >
                        Clear Selection
                      </button>
                    </div>
                    <button
                      onClick={async () => {
                        const confirmed = window.confirm(
                          `Are you sure you want to delete ${selectedFiles.size} selected ${filesTab === 'uploaded' ? 'file(s)' : 'report(s)'}?`
                        )
                        if (!confirmed) return

                        try {
                          const token = await getValidSessionAccessToken()
                          const headers: Record<string, string> = token
                            ? { Authorization: `Bearer ${token}`, ...buildUserHeadersFromToken(token) }
                            : {}

                          const deletePromises = Array.from(selectedFiles).map(async (id) => {
                            const response = await fetch(`${APP_API_BASE}/profile/files/${id}`, {
                              method: 'DELETE',
                              headers,
                            })
                            if (!response.ok) {
                              console.warn(`Failed to delete item ${id}`)
                            }
                            return response
                          })

                          await Promise.all(deletePromises)

                          if (filesTab === 'uploaded') {
                            setUploadedStatements(prev => prev.filter(f => !selectedFiles.has(f.id)))
                          } else {
                            setGeneratedReports(prev => prev.filter(f => !selectedFiles.has(f.id)))
                          }
                          setSelectedFiles(new Set())
                          loadProfileHistory()
                        } catch (error) {
                          console.error('Failed to delete items:', error)
                          alert('Failed to delete some items. Please try again.')
                        }
                      }}
                      className="text-xs font-semibold text-red-600 hover:text-red-700 dark:text-red-400"
                    >
                      Delete
                    </button>
                  </div>
                )}

                <div className="space-y-2.5">
                  {historyBatches.length > 0 ? (
                    <div className="space-y-3">
                      {historyBatches.map((batch, batchIndex) => {
                        const batchTitle =
                          batch.display_name
                          || (batch.uploads?.[0]?.display_name || batch.uploads?.[0]?.name)
                          || (batch.bank_names?.length ? batch.bank_names.join(', ') : formatBatchLabel(batch.batch_id))
                        return (
                          <details
                            key={batch.batch_id}
                            open={batchIndex === 0}
                            className="group/batch overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-xs dark:border-slate-800 dark:bg-[#0B1B36]"
                          >
                            <summary className="cursor-pointer list-none px-4 py-3.5 transition hover:bg-slate-50/80 dark:hover:bg-slate-800/40">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                  <p
                                    title={batchTitle}
                                    className="truncate text-sm font-bold text-slate-900 dark:text-white"
                                  >
                                    {batchTitle}
                                  </p>
                                  <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">
                                    {(batch.bank_names || []).join(', ') || 'Unknown bank'}
                                    {' • '}
                                    {batch.statement_count} statement(s) • {batch.processed_count} processed • {batch.failed_count} failed
                                  </p>
                                </div>
                                <div className="flex shrink-0 flex-wrap justify-end gap-1">
                                  {batch.bank_names.slice(0, 2).map((bankName) => (
                                    <span
                                      key={bankName}
                                      className="max-w-[140px] truncate rounded-full border border-[#01275C]/20 bg-[#01275C]/5 px-2.5 py-0.5 text-[10px] font-semibold text-[#01275C] dark:border-blue-400/30 dark:bg-blue-950/60 dark:text-blue-300"
                                    >
                                      {bankName}
                                    </span>
                                  ))}
                                  {batch.bank_names.length > 2 && (
                                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                                      +{batch.bank_names.length - 2}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </summary>
                            <div className="space-y-3 border-t border-slate-100 bg-slate-50/50 p-3 dark:border-slate-800 dark:bg-[#08152B]/60">
                              {(() => {
                                const visibleBankGroups = (batch.bank_groups || []).filter((g) => {
                                  const items = filesTab === 'uploaded' ? g.uploads : g.reports
                                  return !needsReviewOnly || (items || []).some(itemNeedsReview)
                                })
                                if (visibleBankGroups.length === 0) {
                                  return (
                                    <div className="flex items-center justify-center py-5 text-center">
                                      <span className="text-xs text-slate-400">
                                        {needsReviewOnly ? 'Nothing needs review in this batch' : 'No bank sections'}
                                      </span>
                                    </div>
                                  )
                                }
                                return visibleBankGroups.map((bankGroup, bankIndex) => {
                                const allBankItems = filesTab === 'uploaded' ? bankGroup.uploads : bankGroup.reports
                                const bankItems = needsReviewOnly ? allBankItems.filter(itemNeedsReview) : allBankItems
                                return (
                                  <details
                                    key={bankGroup.bank_name}
                                    open={batchIndex === 0 && bankIndex === 0}
                                    className="overflow-hidden rounded-xl border border-slate-200/80 bg-slate-50/90 dark:border-slate-800 dark:bg-[#0B1B36]/80"
                                  >
                                    <summary className="cursor-pointer list-none px-3.5 py-2.5">
                                      <div className="flex items-center justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                          <p className="truncate text-xs font-bold uppercase tracking-wide text-[#01275C] dark:text-blue-300">
                                            {bankGroup.bank_name}
                                          </p>
                                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                            {bankGroup.statement_count} statement(s) • {bankGroup.processed_count} processed
                                          </p>
                                        </div>
                                        <span className="shrink-0 rounded-md bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 ring-1 ring-slate-200/80 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700">
                                          {bankItems.length} visible
                                        </span>
                                      </div>
                                    </summary>
                                    <div className="space-y-2 border-t border-slate-200/70 p-2.5 dark:border-slate-800">
                                      {bankItems.length > 0 ? (
                                        bankItems.map((item) => renderHistoryRow(item, filesTab))
                                      ) : (
                                        <div className="flex items-center justify-center py-6 text-center">
                                          <span className="text-xs text-slate-400">
                                            No {filesTab === 'uploaded' ? 'uploads' : 'reports'} in this bank section
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  </details>
                                )
                              })
                              })()}
                            </div>
                          </details>
                        )
                      })}
                    </div>
                  ) : filesTab === 'uploaded' ? (
                    uploadedStatements.length > 0 ? (
                      uploadedStatements.filter((item) => !needsReviewOnly || itemNeedsReview(item)).map((item) => (
                        <div
                          key={item.id}
                          className="group rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-2xs transition hover:border-[#01275C]/30 dark:border-slate-700/80 dark:bg-[#0F2342]"
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={selectedFiles.has(item.id)}
                              onChange={(e) => {
                                const newSelected = new Set(selectedFiles)
                                if (e.target.checked) {
                                  newSelected.add(item.id)
                                } else {
                                  newSelected.delete(item.id)
                                }
                                setSelectedFiles(newSelected)
                              }}
                              className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-[#01275C] focus:ring-[#01275C]"
                            />
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#01275C]/10 text-[#01275C] dark:bg-blue-500/20 dark:text-blue-300">
                              <FileText className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                                    {item.displayName || item.name}
                                  </p>
                                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.date}</p>
                                </div>
                                <div className="flex shrink-0 items-center gap-1.5">
                                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${item.status === 'Processed' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : item.status === 'Processing' ? 'border-amber-200 bg-amber-50 text-amber-700' : item.status === 'Failed' ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                                    {item.status}
                                  </span>
                                  <button
                                    onClick={async () => {
                                      const confirmed = window.confirm(
                                        `Are you sure you want to delete "${item.displayName || item.name}"?`
                                      )
                                      if (!confirmed) return

                                      try {
                                        const token = await getValidSessionAccessToken()
                                        const headers: Record<string, string> = token
                                          ? { Authorization: `Bearer ${token}`, ...buildUserHeadersFromToken(token) }
                                          : {}

                                        const response = await fetch(`${APP_API_BASE}/profile/files/${item.id}`, {
                                          method: 'DELETE',
                                          headers,
                                        })

                                        if (response.ok) {
                                          setUploadedStatements(prev => prev.filter((f) => f.id !== item.id))
                                          loadProfileHistory()
                                        } else {
                                          alert('Failed to delete file. Please try again.')
                                        }
                                      } catch (error) {
                                        console.error('Failed to delete file:', error)
                                        alert('Failed to delete file. Please try again.')
                                      }
                                    }}
                                    className="rounded-lg p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </div>
                              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                <VerificationBadge engine={parseStatementEngine(item.statement_engine)} />
                                {(item as any).statement_metadata && (
                                  <>
                                    <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                      Credits: {(item as any).statement_metadata.total_credits}
                                    </span>
                                    <span className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                                      Debits: {(item as any).statement_metadata.total_debits}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 py-10 text-center dark:border-slate-800">
                        <FileText className="h-8 w-8 text-slate-300 dark:text-slate-600" />
                        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No files yet</p>
                      </div>
                    )
                  ) : (
                    generatedReports.length > 0 ? (
                      generatedReports.filter((item) => !needsReviewOnly || itemNeedsReview(item)).map((item) => (
                        <div
                          key={item.id}
                          className="group rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-2xs transition hover:border-[#01275C]/30 dark:border-slate-700/80 dark:bg-[#0F2342]"
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={selectedFiles.has(item.id)}
                              onChange={(e) => {
                                const newSelected = new Set(selectedFiles)
                                if (e.target.checked) {
                                  newSelected.add(item.id)
                                } else {
                                  newSelected.delete(item.id)
                                }
                                setSelectedFiles(newSelected)
                              }}
                              className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-[#01275C] focus:ring-[#01275C]"
                            />
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
                              <FileSpreadsheet className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                                    {item.displayName || item.name}
                                  </p>
                                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.date}</p>
                                </div>
                                <div className="flex shrink-0 items-center gap-1.5">
                                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${item.retentionStatus === 'Deleted' || item.deletedAt ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'}`}>
                                    {formatRetentionLabel(item.retentionStatus, item.retentionDaysLeft, item.deletedAt)}
                                  </span>
                                  <button
                                    type="button"
                                    aria-label="Download report"
                                    onClick={() => void downloadWithAuth(item.downloadUrl, 'report.xlsx')}
                                    className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-[#01275C] dark:text-slate-300 dark:hover:bg-slate-800"
                                  >
                                    <Download className="h-4 w-4" />
                                  </button>
                                  <button
                                    onClick={async () => {
                                      const confirmed = window.confirm(
                                        `Are you sure you want to delete "${item.displayName || item.name}"?`
                                      )
                                      if (!confirmed) return

                                      try {
                                        const token = await getValidSessionAccessToken()
                                        const headers: Record<string, string> = token
                                          ? { Authorization: `Bearer ${token}`, ...buildUserHeadersFromToken(token) }
                                          : {}

                                        const response = await fetch(`${APP_API_BASE}/profile/files/${item.id}`, {
                                          method: 'DELETE',
                                          headers,
                                        })

                                        if (response.ok) {
                                          setGeneratedReports(prev => prev.filter((r) => r.id !== item.id))
                                          loadProfileHistory()
                                        } else {
                                          alert('Failed to delete report. Please try again.')
                                        }
                                      } catch (error) {
                                        console.error('Failed to delete report:', error)
                                        alert('Failed to delete report. Please try again.')
                                      }
                                    }}
                                    className="rounded-lg p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </div>
                              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                <VerificationBadge engine={parseStatementEngine(item.statement_engine)} />
                                {(item as any).statement_metadata && (
                                  <>
                                    <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                      Credits: {(item as any).statement_metadata.total_credits}
                                    </span>
                                    <span className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                                      Debits: {(item as any).statement_metadata.total_debits}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 py-10 text-center dark:border-slate-800">
                        <FileSpreadsheet className="h-8 w-8 text-slate-300 dark:text-slate-600" />
                        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No files yet</p>
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          </aside>
        </>
      )}
    </main>
  )
}

async function uploadStatement({
  file,
  userDetails,
  mode,
  apiKey,
  pdfPassword,
  batchId,
  statementLabel,
  bankName,
  accountType,
}: {
  file: File
  userDetails: UserDetails
  mode: ProcessingMode
  apiKey?: string
  pdfPassword?: string
  batchId?: string
  statementLabel?: string
  bankName?: string
  accountType?: StatementTypeSelection
}): Promise<JobSubmitted> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('full_name', userDetails.fullName || '')
  formData.append('account_type', accountType || userDetails.accountType || '')
  formData.append('bank_name', bankName || userDetails.bankName || '')
  formData.append('mode', mode)
  if (batchId) formData.append('batch_id', batchId)
  if (statementLabel) formData.append('statement_label', statementLabel)
  if (apiKey) formData.append('api_key', apiKey)
  if (pdfPassword) formData.append('pdf_password', pdfPassword)

  const token = await getValidSessionAccessToken()
  const headers: Record<string, string> | undefined = token
    ? { Authorization: `Bearer ${token}`, ...buildUserHeadersFromToken(token) }
    : undefined
  const resp = await fetch(`${APP_API_BASE}/upload`, {
    method: 'POST',
    body: formData,
    headers,
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const raw = data?.detail ?? data
    const message =
      typeof raw === 'string'
        ? raw
        : raw?.error || raw?.message || data?.message || 'Upload failed. Please try again.'
    const error = new Error(message) as Error & { code?: string; needs_password?: boolean }
    error.code = typeof raw === 'object' && raw ? raw.code || data?.code : data?.code
    error.needs_password = Boolean(
      typeof raw === 'object' && raw && (raw.requires_password || raw.code === 'PDF_PASSWORD_REQUIRED' || raw.code === 'PDF_PASSWORD_INVALID')
    )
    throw error
  }
  return data as JobSubmitted
}

