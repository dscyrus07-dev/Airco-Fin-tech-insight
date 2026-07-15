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
import {
  FileText,
  FileSpreadsheet,
  Download,
  Trash2,
  UserCircle2,
} from 'lucide-react'
import { BankStatementFileItem, UserDetails, ProcessingResult, ProcessingMode, Step, JobSubmitted, ProfileHistoryResponse, UserUploadHistoryItem, UserReportHistoryItem, StatementTypeSelection } from '@/types'
import { SUPPORTED_BANK_OPTIONS } from '@/lib/banks'

type BatchResultItem = {
  id: string
  bankName: string
  fileName: string
  result: ProcessingResult
  errorMessage?: string
}

const formatBatchLabel = (batchId: string) => {
  if (!batchId) return 'Unknown batch'
  return batchId.length > 18 ? `${batchId.slice(0, 18)}…` : batchId
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

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [step, setStep] = useState<Step>(1)
  const [filesTab, setFilesTab] = useState<'uploaded' | 'reports'>('uploaded')
  const [isProfilePanelOpen, setIsProfilePanelOpen] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set())
  const [userDetails, setUserDetails] = useState<UserDetails>({
    fullName: '',
    accountType: '',
    bankName: '',
    selectedBanks: [],
  })
  const [filesByBank, setFilesByBank] = useState<Record<string, BankStatementFileItem[]>>({})
  const [batchId, setBatchId] = useState<string>(createBatchId())
  const [batchQueue, setBatchQueue] = useState<BankStatementFileItem[]>([])
  const [batchResults, setBatchResults] = useState<BatchResultItem[]>([])
  const [currentBatchIndex, setCurrentBatchIndex] = useState(0)
  const [activeBatchFile, setActiveBatchFile] = useState<BankStatementFileItem | null>(null)
  const [mode, setMode] = useState<ProcessingMode>('free')
  const [apiKey, setApiKey] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [historySummary, setHistorySummary] = useState<ProfileHistoryResponse['summary']>({
    total_uploads: 0,
    processed_files: 0,
    generated_reports: 0,
    total_batches: 0,
    latest_account_type: null,
  })
  const [historyUser, setHistoryUser] = useState<ProfileHistoryResponse['user'] | null>(null)
  const [historyBatches, setHistoryBatches] = useState<NonNullable<ProfileHistoryResponse['batches']>>([])

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
  }>>([])

  useEffect(() => {
    const savedData = localStorage.getItem('airco-form-data')
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData)
        const restoredDetails = parsed.userDetails || {}
        setUserDetails({
          fullName: restoredDetails.fullName || '',
          accountType: restoredDetails.accountType || '',
          bankName: restoredDetails.bankName || '',
          selectedBanks: Array.isArray(restoredDetails.selectedBanks)
            ? restoredDetails.selectedBanks
            : restoredDetails.bankName
              ? [restoredDetails.bankName]
              : [],
        })
        setFilesByBank({})
        setMode(parsed.mode || 'free')
        setApiKey(parsed.apiKey || '')
        const restoredStep = parsed.step || 1
        setStep(restoredStep === 4 ? 3 : restoredStep)
      } catch (e) {
        console.error('Failed to load saved form data:', e)
      }
    }
  }, [])

  useEffect(() => {
    const dataToSave = {
      userDetails,
      mode,
      apiKey,
      step,
      timestamp: Date.now(),
    }
    localStorage.setItem('airco-form-data', JSON.stringify(dataToSave))
  }, [userDetails, mode, apiKey, step])

  const loadProfileHistory = useCallback(async () => {
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
          status:
            item.status === 'completed'
              ? 'Processed'
              : item.status === 'running'
                ? 'Processing'
                : item.status === 'failed'
                  ? 'Failed'
                  : 'Pending',
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
        }))
      )
    } catch (fetchError) {
      console.error('Failed to load profile history:', fetchError)
    }
  }, [])

  useEffect(() => {
    loadProfileHistory()
  }, [loadProfileHistory])

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
      prev.map((f) => (f.status === 'Processing' ? { ...f, status: 'Processed' } : f))
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

  useEffect(() => {
    if (step === 4 && !jobId && !isProcessing) {
      setStep(3)
    }
  }, [step, jobId, isProcessing])

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

  const renderHistoryRow = (
    item: UserUploadHistoryItem | UserReportHistoryItem,
    tab: 'uploaded' | 'reports',
  ) => {
    const isUpload = tab === 'uploaded'
    const itemId = item.job_id
    const createdLabel = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Unknown date'
    const retentionLabel = formatRetentionLabel(item.retention_status, item.retention_days_left, item.deleted_at)
    const retentionTone = (item.deletion_status || '').toLowerCase() === 'deleted'
      ? 'border-red-200 bg-red-50 text-red-700'
      : (item.deletion_status || '').toLowerCase() === 'queued for deletion' || (item.deletion_status || '').toLowerCase() === 'deleting' || (item.deletion_status || '').toLowerCase() === 'scheduled'
        ? 'border-amber-200 bg-amber-50 text-amber-700'
        : 'border-neutral-200 bg-neutral-50 text-neutral-600'

    const statementMetadata = (item as any).statement_metadata

    const renderStatementMetadataChips = () => {
      if (!statementMetadata) return null

      return (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {statementMetadata.has_salary && (
            <span className="rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700">
              Salary: ₹{Number(statementMetadata.salary_amount || 0).toLocaleString()}
            </span>
          )}
          {statementMetadata.has_loan_repayment && (
            <span className="rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[10px] font-medium text-orange-700">
              Loan: ₹{Number(statementMetadata.loan_repayment_amount || 0).toLocaleString()}
            </span>
          )}
          <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
            Credits: {statementMetadata.total_credits ?? 0}
          </span>
          <span className="rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700">
            Debits: {statementMetadata.total_debits ?? 0}
          </span>
        </div>
      )
    }

    return (
      <div
        key={itemId}
        className="group flex items-start gap-3 rounded-xl px-3 py-3 transition hover:bg-neutral-50"
      >
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
          className="h-4 w-4 rounded border-neutral-300 text-black focus:ring-black"
        />
        <div className={`flex h-8 w-8 items-center justify-center rounded ${isUpload ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'}`}>
          {isUpload ? <FileText className="h-4 w-4" /> : <FileSpreadsheet className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-black">{item.display_name || item.name}</p>
              <p className="text-xs text-neutral-500">{createdLabel}</p>
            </div>
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${retentionTone}`}>
                {retentionLabel}
              </span>
              {item.retention_expires_at && (
                <span className="text-[10px] text-neutral-400">
                  Deletes on {new Date(item.retention_expires_at).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
          {renderStatementMetadataChips()}
        </div>
        {isUpload ? (
          <div className="flex items-center gap-2">
            <div
              className={`h-3 w-3 rounded-full ring-2 ring-offset-1 ${
                (item as UserUploadHistoryItem).status === 'Processed' ? 'bg-green-500 ring-green-200' :
                (item as UserUploadHistoryItem).status === 'Processing' ? 'bg-amber-500 ring-amber-200 animate-pulse' :
                (item as UserUploadHistoryItem).status === 'Failed' ? 'bg-red-500 ring-red-200' :
                'bg-neutral-300 ring-neutral-200'
              }`}
            />
            <span className={`text-xs font-medium ${
              (item as UserUploadHistoryItem).status === 'Processed' ? 'text-green-700' :
              (item as UserUploadHistoryItem).status === 'Processing' ? 'text-amber-700' :
              (item as UserUploadHistoryItem).status === 'Failed' ? 'text-red-700' :
              'text-neutral-500'
            }`}>
              {(item as UserUploadHistoryItem).status}
            </span>
          </div>
        ) : (
          <a
            href={`/api/jobs/${itemId}/download`}
            download
            className="p-1 rounded text-neutral-400 hover:text-black transition"
          >
            <Download className="h-4 w-4" />
          </a>
        )}
        <div className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1">
          <button
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
            className="p-1 rounded text-neutral-400 hover:text-red-600 transition"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-[1440px] px-4 pb-10 pt-6 sm:px-6 lg:px-8">
        <Header onProfileClick={() => setIsProfilePanelOpen(true)} />

        <div className="max-w-3xl mx-auto">
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
              {step === 4 && jobId && (
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
                    jobId={jobId}
                    mode={mode}
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
                No data is stored. Processing happens in real time.
              </p>

              <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                {SUPPORTED_BANK_OPTIONS.map(({ name, available }) => (
                  <span
                    key={name}
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] ${
                      available
                        ? 'border-neutral-200 bg-neutral-50 text-neutral-500'
                        : 'border-dashed border-neutral-200 bg-white text-neutral-300'
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${available ? 'bg-green-400' : 'bg-neutral-300'}`} />
                    {name}
                    {!available && <span className="ml-0.5 text-[9px] text-neutral-300">soon</span>}
                  </span>
                ))}
              </div>

              <p className="mx-auto max-w-md text-[10px] leading-relaxed text-neutral-300">
                Airco Insights does not provide financial advice, predictions, or recommendations.
                The system only categorizes and structures transaction data.
              </p>
            </footer>
          </section>
        </div>
      </div>

      {isProfilePanelOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/20 z-40 transition-opacity"
            onClick={() => setIsProfilePanelOpen(false)}
          />

          <div className="fixed top-0 right-0 h-full w-[520px] bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-in-out translate-x-0">
            <div className="h-full overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-neutral-100 p-4 z-10">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-black">Profile</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition hover:border-neutral-300 hover:bg-neutral-50 shadow-sm">
                      <UserCircle2 className="h-4 w-4" />
                      Profile
                    </button>
                    <button
                      onClick={() => setIsProfilePanelOpen(false)}
                      className="rounded-full p-2 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 transition"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 6-12 12"/><path d="m6 6 12 12"/></svg>
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-6 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 80px)' }}>
                <div className="rounded-2xl border border-neutral-100 bg-neutral-50/80 p-4 shadow-sm">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-neutral-400 shadow-sm ring-1 ring-neutral-200">
                      <UserCircle2 className="h-8 w-8" />
                    </div>
                    <div className="flex-1">
                      <p className="text-base font-semibold text-black">{profileName}</p>
                      <p className="text-sm text-neutral-500">{profileEmail}</p>
                    </div>
                  </div>

                  <div className="mt-6 space-y-3">
                    <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-neutral-100">
                      <span className="text-sm text-neutral-600">Account Type</span>
                      <span className="text-sm font-medium text-black">{accountTypeLabel}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <div className="rounded-xl bg-white px-3 py-3 text-center shadow-sm ring-1 ring-neutral-100">
                        <p className="text-lg font-semibold text-black">{historySummary.total_uploads}</p>
                        <p className="text-[11px] text-neutral-500">Uploads</p>
                      </div>
                      <div className="rounded-xl bg-white px-3 py-3 text-center shadow-sm ring-1 ring-neutral-100">
                        <p className="text-lg font-semibold text-black">{historySummary.processed_files}</p>
                        <p className="text-[11px] text-neutral-500">Processed</p>
                      </div>
                      <div className="rounded-xl bg-white px-3 py-3 text-center shadow-sm ring-1 ring-neutral-100">
                        <p className="text-lg font-semibold text-black">{historySummary.generated_reports}</p>
                        <p className="text-[11px] text-neutral-500">Reports</p>
                      </div>
                      <div className="rounded-xl bg-white px-3 py-3 text-center shadow-sm ring-1 ring-neutral-100">
                        <p className="text-lg font-semibold text-black">{profileBatchCount}</p>
                        <p className="text-[11px] text-neutral-500">Batches</p>
                      </div>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="w-full rounded-lg bg-red-50 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-100"
                    >
                      Sign Out
                    </button>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-black">Files</h3>
                    <div className="inline-flex rounded-full bg-neutral-100 p-0.5 text-xs font-medium text-neutral-500">
                      <button
                        type="button"
                        onClick={() => { setFilesTab('uploaded'); setSelectedFiles(new Set()) }}
                        className={`rounded-full px-3 py-1 transition ${filesTab === 'uploaded' ? 'bg-white text-black shadow-sm' : ''}`}
                      >
                        Uploaded Statements
                      </button>
                      <button
                        type="button"
                        onClick={() => { setFilesTab('reports'); setSelectedFiles(new Set()) }}
                        className={`rounded-full px-3 py-1 transition ${filesTab === 'reports' ? 'bg-white text-black shadow-sm' : ''}`}
                      >
                        Generated Reports
                      </button>
                    </div>
                  </div>

                  {selectedFiles.size > 0 && (
                    <div className="flex items-center justify-between rounded-lg bg-neutral-50 px-3 py-2">
                      <div className="flex items-center gap-3">
                        <span className="text-sm text-neutral-600">{selectedFiles.size} selected</span>
                        <button
                          onClick={() => {
                            setSelectedFiles(new Set(getVisibleHistoryIds(filesTab)))
                          }}
                          className="text-sm text-black hover:text-neutral-700 transition"
                        >
                          Select All
                        </button>
                        <button
                          onClick={() => setSelectedFiles(new Set())}
                          className="text-sm text-black hover:text-neutral-700 transition"
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

                            // Delete selected items from backend
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

                            // Update local state
                            if (filesTab === 'uploaded') {
                              setUploadedStatements(prev => prev.filter(f => !selectedFiles.has(f.id)))
                            } else {
                              setGeneratedReports(prev => prev.filter(f => !selectedFiles.has(f.id)))
                            }
                            setSelectedFiles(new Set())
                            
                            // Reload history to sync with backend
                            loadProfileHistory()
                          } catch (error) {
                            console.error('Failed to delete items:', error)
                            alert('Failed to delete some items. Please try again.')
                          }
                        }}
                        className="text-sm text-red-600 hover:text-red-700 transition"
                      >
                        Delete
                      </button>
                    </div>
                  )}

                  <div className="space-y-1">
                    {historyBatches.length > 0 ? (
                      <div className="space-y-3">
                        {historyBatches.map((batch, batchIndex) => {
                          return (
                            <details
                              key={batch.batch_id}
                              open={batchIndex === 0}
                              className="rounded-xl border border-neutral-200 bg-white shadow-sm"
                            >
                              <summary className="cursor-pointer list-none px-4 py-3">
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-semibold text-black">
                                      {batch.display_name || formatBatchLabel(batch.batch_id)}
                                    </p>
                                    <p className="mt-1 text-xs text-neutral-500">
                                      {batch.statement_count} statement(s) • {batch.processed_count} processed • {batch.failed_count} failed
                                    </p>
                                  </div>
                                  <div className="flex flex-wrap justify-end gap-1.5">
                                    {batch.bank_names.map((bankName) => (
                                      <span key={bankName} className="rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] text-neutral-500">
                                        {bankName}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              </summary>
                              <div className="border-t border-neutral-100 p-3 space-y-3">
                                {(batch.bank_groups || []).map((bankGroup, bankIndex) => {
                                  const bankItems = filesTab === 'uploaded' ? bankGroup.uploads : bankGroup.reports
                                  return (
                                    <details
                                      key={bankGroup.bank_name}
                                      open={batchIndex === 0 && bankIndex === 0}
                                      className="rounded-lg border border-neutral-100 bg-neutral-50"
                                    >
                                      <summary className="cursor-pointer list-none px-3 py-2">
                                        <div className="flex items-center justify-between gap-3">
                                          <div>
                                            <p className="text-sm font-medium text-black">{bankGroup.bank_name}</p>
                                            <p className="text-[11px] text-neutral-500">
                                              {bankGroup.statement_count} statement(s) • {bankGroup.processed_count} processed
                                            </p>
                                          </div>
                                          <span className="text-[10px] uppercase tracking-wide text-neutral-400">
                                            {bankItems.length} visible
                                          </span>
                                        </div>
                                      </summary>
                                      <div className="border-t border-neutral-200 px-2 py-2 space-y-1">
                                        {bankItems.length > 0 ? (
                                          bankItems.map((item) => renderHistoryRow(item, filesTab))
                                        ) : (
                                          <div className="flex items-center justify-center py-6 text-center">
                                            <span className="text-sm text-neutral-400">
                                              No {filesTab === 'uploaded' ? 'uploads' : 'reports'} in this bank section
                                            </span>
                                          </div>
                                        )}
                                      </div>
                                    </details>
                                  )
                                })}
                              </div>
                            </details>
                          )
                        })}
                      </div>
                    ) : filesTab === 'uploaded' ? (
                      uploadedStatements.length > 0 ? (
                        uploadedStatements.map((item) => (
                          <div
                            key={item.id}
                            className="group flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-neutral-50"
                          >
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
                              className="h-4 w-4 rounded border-neutral-300 text-black focus:ring-black"
                            />
                            <div className="flex h-8 w-8 items-center justify-center rounded bg-red-50 text-red-500">
                              <FileText className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-medium text-black">{item.displayName || item.name}</p>
                                  <p className="text-xs text-neutral-500">{item.date}</p>
                                </div>
                                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${item.status === 'Processed' ? 'border-green-200 bg-green-50 text-green-700' : item.status === 'Processing' ? 'border-amber-200 bg-amber-50 text-amber-700' : item.status === 'Failed' ? 'border-red-200 bg-red-50 text-red-700' : 'border-neutral-200 bg-neutral-50 text-neutral-600'}`}>
                                  {item.status}
                                </span>
                              </div>
                              {(item as any).statement_metadata && (
                                <div className="mt-2 flex flex-wrap gap-2">
                                  <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                    Credits: {(item as any).statement_metadata.total_credits}
                                  </span>
                                  <span className="rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700">
                                    Debits: {(item as any).statement_metadata.total_debits}
                                  </span>
                                </div>
                              )}
                            </div>
                            <div className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1">
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
                                className="p-1 rounded text-neutral-400 hover:text-red-600 transition"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-center">
                          <FileText className="h-8 w-8 text-neutral-300" />
                          <p className="mt-2 text-sm text-neutral-500">No files yet</p>
                        </div>
                      )
                    ) : (
                      generatedReports.length > 0 ? (
                        generatedReports.map((item) => (
                          <div
                            key={item.id}
                            className="group flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-neutral-50"
                          >
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
                              className="h-4 w-4 rounded border-neutral-300 text-black focus:ring-black"
                            />
                            <div className="flex h-8 w-8 items-center justify-center rounded bg-green-50 text-green-600">
                              <FileSpreadsheet className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-medium text-black">{item.displayName || item.name}</p>
                                  <p className="text-xs text-neutral-500">{item.date}</p>
                                </div>
                                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${item.retentionStatus === 'Deleted' || item.deletedAt ? 'border-red-200 bg-red-50 text-red-700' : 'border-neutral-200 bg-neutral-50 text-neutral-600'}`}>
                                  {formatRetentionLabel(item.retentionStatus, item.retentionDaysLeft, item.deletedAt)}
                                </span>
                              </div>
                              {(item as any).statement_metadata && (
                                <div className="mt-2 flex flex-wrap gap-2">
                                  <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                    Credits: {(item as any).statement_metadata.total_credits}
                                  </span>
                                  <span className="rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700">
                                    Debits: {(item as any).statement_metadata.total_debits}
                                  </span>
                                </div>
                              )}
                            </div>
                            <div className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1">
                              <a
                                href={item.downloadUrl}
                                download
                                className="p-1 rounded text-neutral-400 hover:text-black transition"
                              >
                                <Download className="h-4 w-4" />
                              </a>
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
                                className="p-1 rounded text-neutral-400 hover:text-red-600 transition"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-center">
                          <FileSpreadsheet className="h-8 w-8 text-neutral-300" />
                          <p className="mt-2 text-sm text-neutral-500">No files yet</p>
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
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

