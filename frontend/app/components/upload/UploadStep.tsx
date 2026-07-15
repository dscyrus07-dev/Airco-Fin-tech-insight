'use client'

import { useMemo, useRef, DragEvent } from 'react'
import { Upload, FileText, X } from 'lucide-react'
import { BankStatementFileItem, BankName, StatementTypeSelection } from '@/types'
import { validateFile } from '@/lib/validation'

interface UploadStepProps {
  selectedBanks: BankName[]
  filesByBank: Record<string, BankStatementFileItem[]>
  onFilesChange: (nextFilesByBank: Record<string, BankStatementFileItem[]>) => void
  onContinue: () => void
  isProcessing: boolean
}

export default function UploadStep({
  selectedBanks,
  filesByBank,
  onFilesChange,
  onContinue,
  isProcessing,
}: UploadStepProps) {
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const totalFiles = useMemo(
    () => selectedBanks.reduce((count, bank) => count + (filesByBank[bank]?.length || 0), 0),
    [filesByBank, selectedBanks]
  )

  const canContinue = useMemo(
    () =>
      selectedBanks.length > 0 &&
      selectedBanks.every((bank) => (filesByBank[bank]?.length || 0) > 0) &&
      selectedBanks.every((bank) =>
        (filesByBank[bank] || []).every((file) => Boolean(file.accountType))
      ),
    [filesByBank, selectedBanks]
  )

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const makeStatementLabel = (bankName: BankName, file: File, index: number) => {
    const cleanName = file.name.replace(/\.pdf$/i, '')
    return `${bankName} — ${cleanName || `Statement ${index + 1}`}`
  }

  const addFilesForBank = (
    bankName: BankName,
    incoming: FileList | File[]
  ) => {
    const nextFiles = Array.from(incoming)
      .filter((file) => {
        const validationError = validateFile(file)
        if (validationError) {
          window.alert(`${bankName}: ${file.name} — ${validationError}`)
          return false
        }
        return true
      })
      .map<BankStatementFileItem>((file, index) => ({
        id: `${bankName}-${file.name}-${file.size}-${Date.now()}-${index}`,
        bankName,
        file,
        statementLabel: makeStatementLabel(bankName, file, index),
        accountType: 'auto_detect',
        status: 'ready',
      }))

    if (nextFiles.length === 0) return

    onFilesChange({
      ...filesByBank,
      [bankName]: [...(filesByBank[bankName] || []), ...nextFiles],
    })
  }

  const removeFile = (bankName: BankName, fileId: string) => {
    onFilesChange({
      ...filesByBank,
      [bankName]: (filesByBank[bankName] || []).filter((item) => item.id !== fileId),
    })
  }

  const updateFileAccountType = (bankName: BankName, fileId: string, accountType: StatementTypeSelection) => {
    onFilesChange({
      ...filesByBank,
      [bankName]: (filesByBank[bankName] || []).map((item) =>
        item.id === fileId ? { ...item, accountType } : item
      ),
    })
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>, bankName: BankName) => {
    e.preventDefault()
    addFilesForBank(bankName, e.dataTransfer.files)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-black mb-1">
          Upload Bank Statement PDFs
        </h2>
        <p className="text-sm text-neutral-500 mb-2">
          We accept PDF bank statements up to 20MB each.
        </p>
        <p className="text-xs text-neutral-400">
          Upload one or more statements for each selected bank.
        </p>
      </div>

      {selectedBanks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-200 bg-neutral-50 p-8 text-center text-sm text-neutral-500">
          Please go back and select at least one bank.
        </div>
      ) : (
        <div className="space-y-4">
          {selectedBanks.map((bankName) => {
            const files = filesByBank[bankName] || []

            return (
              <div key={bankName} className="rounded-xl border border-border bg-white p-4 sm:p-5">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-black">{bankName}</h3>
                    <p className="text-xs text-neutral-500">Upload all statements for this bank</p>
                  </div>
                  <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-medium text-neutral-500">
                    {files.length} file{files.length === 1 ? '' : 's'}
                  </span>
                </div>

                <div
                  onDrop={(e) => handleDrop(e, bankName)}
                  onDragOver={handleDragOver}
                  onClick={() => inputRefs.current[bankName]?.click()}
                  className="relative cursor-pointer rounded-lg border-2 border-dashed border-border p-6 transition-colors hover:border-neutral-400 hover:bg-neutral-50"
                >
                  <input
                    ref={(node) => {
                      inputRefs.current[bankName] = node
                    }}
                    type="file"
                    accept="application/pdf"
                    multiple
                    onChange={(e) => {
                      if (e.target.files) {
                        addFilesForBank(bankName, e.target.files)
                        e.target.value = ''
                      }
                    }}
                    className="hidden"
                  />

                  <div className="flex flex-col items-center gap-2 text-center">
                    <Upload className="h-7 w-7 text-neutral-400" />
                    <div>
                      <p className="text-sm font-medium text-black">
                        Drag & drop PDFs for {bankName}
                      </p>
                      <p className="text-xs text-neutral-400 mt-1">
                        or click to browse and add multiple PDFs
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {files.length > 0 ? (
                    files.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2.5"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <FileText className="h-4 w-4 flex-none text-neutral-500" />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-black">
                              {item.file.name}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-neutral-400">
                              <span>{item.statementLabel}</span>
                              <span>·</span>
                              <span>{formatSize(item.file.size)}</span>
                            </div>
                          </div>
                        </div>
                        <div className="min-w-[180px]">
                          <label className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-neutral-500">
                            Bank Statement Type
                          </label>
                          <select
                            value={item.accountType}
                            onChange={(e) => updateFileAccountType(bankName, item.id, e.target.value as StatementTypeSelection)}
                            className="w-full rounded-md border border-border bg-white px-2.5 py-2 text-xs text-black focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-1"
                          >
                            <option value="auto_detect">Auto Detect (Recommended)</option>
                            <option value="salaried">Salaried</option>
                            <option value="business">Business</option>
                          </select>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeFile(bankName, item.id)}
                          className="rounded-full p-1 text-neutral-400 transition hover:bg-white hover:text-black"
                          aria-label={`Remove ${item.file.name}`}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-neutral-100 bg-neutral-50 px-3 py-4 text-center text-sm text-neutral-400">
                      No files uploaded for this bank yet.
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <button
        type="button"
        onClick={onContinue}
        disabled={isProcessing || totalFiles === 0 || !canContinue}
        className="w-full rounded-md bg-black px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
      >
        {isProcessing ? 'Preparing batch…' : `Continue with ${totalFiles} uploaded file${totalFiles === 1 ? '' : 's'}`}
      </button>
    </div>
  )
}
