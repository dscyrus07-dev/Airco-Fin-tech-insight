'use client'

import { Download, FileSpreadsheet, FileText, FileJson } from 'lucide-react'
import type { ProcessingResult, SheetPreview } from '@/types'

interface DownloadButtonsProps {
  excelUrl: string
  pdfUrl?: string
  result?: ProcessingResult
  fileNameHint?: string
}

function slugFileName(value: string, fallback = 'airco_report'): string {
  const base = value.replace(/\.pdf$/i, '').replace(/\.xlsx$/i, '').trim()
  const cleaned = base.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  return cleaned || fallback
}

function buildExportJson(result: ProcessingResult, fileNameHint: string) {
  const sheetKeys: Array<{ key: keyof ProcessingResult; name: string }> = [
    { key: 'account_summary', name: 'Summary' },
    { key: 'monthly_analysis', name: 'Monthly Analysis' },
    { key: 'top5_credits', name: 'Top 5 Credits' },
    { key: 'top5_debits', name: 'Top 5 Debits' },
    { key: 'bounces_penal', name: 'Bounce And Penal Transactions' },
    { key: 'salary_transactions', name: 'Salary Transactions' },
    { key: 'loan_repayment', name: 'Loan Repayment Transactions' },
    { key: 'credit_card_payments', name: 'Credit Card Payments' },
    { key: 'raw_transactions', name: 'Transactions' },
  ]

  const sheets = sheetKeys.map(({ key, name }) => {
    const preview = result[key] as SheetPreview | undefined
    return {
      name,
      title: preview?.title || name,
      headers: preview?.headers || [],
      rows: preview?.rows || [],
    }
  })

  return {
    format: 'airco-insights-lite-export',
    version: '1.0',
    exportedAt: new Date().toISOString(),
    sourceFile: fileNameHint,
    mode: result.mode,
    bank: (result as any).bank || (result as any).bank_key || '',
    excel_url: result.excel_url,
    stats: result.stats || null,
    ai_usage: result.ai_usage || null,
    statement_profile: result.statement_profile || null,
    sheets,
  }
}

export default function DownloadButtons({
  excelUrl,
  pdfUrl,
  result,
  fileNameHint = 'airco_report',
}: DownloadButtonsProps) {
  const baseName = slugFileName(fileNameHint)
  const excelName = `${baseName}_Report.xlsx`
  const jsonName = `${baseName}_Report.json`

  const handleJsonDownload = () => {
    if (!result) return
    const payload = buildExportJson(result, fileNameHint)
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = jsonName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col sm:flex-row gap-3 mt-8">
      <a
        href={excelUrl}
        download={excelName}
        className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 bg-black text-white text-sm font-medium rounded-md hover:bg-neutral-800 transition-colors"
      >
        <FileSpreadsheet className="w-4 h-4" />
        Download Excel
      </a>

      <button
        type="button"
        onClick={handleJsonDownload}
        disabled={!result}
        className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 border border-border text-black text-sm font-medium rounded-md hover:bg-neutral-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <FileJson className="w-4 h-4" />
        Download JSON
      </button>

      {pdfUrl && (
        <a
          href={pdfUrl}
          download
          className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 border border-border text-black text-sm font-medium rounded-md hover:bg-neutral-50 transition-colors"
        >
          <FileText className="w-4 h-4" />
          Download PDF
        </a>
      )}
    </div>
  )
}
