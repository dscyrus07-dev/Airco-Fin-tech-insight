'use client'

import { useState, useEffect } from 'react'
import { ProcessingResult, SheetPreview } from '@/types'
import CollapsiblePreview from './CollapsiblePreview'
import DownloadButtons from './DownloadButtons'
import { CheckCircle2, Eye, FileSpreadsheet, Download, Archive } from 'lucide-react'
import SpreadsheetEditor from '../spreadsheet/SpreadsheetEditor'
import { SpreadsheetProvider } from '../spreadsheet/SpreadsheetContext'

interface ResultStepProps {
  result: ProcessingResult
  batchResults?: Array<{
    id: string
    bankName: string
    fileName: string
    result: ProcessingResult
  }>
}

/** Lite 9-sheet order — Credit Card Payments before Transactions (last). */
const PLACEHOLDER_SHEETS: SheetPreview[] = [
  { title: 'Sheet 1 — Summary', headers: ['Metric', 'Value'], rows: [] },
  { title: 'Sheet 2 — Monthly Analysis', headers: ['Metric'], rows: [] },
  { title: 'Sheet 3 — Top 5 Credits', headers: ['Date', 'Description', 'Category', 'Amount', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 4 — Top 5 Debits', headers: ['Date', 'Description', 'Category', 'Amount', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 5 — Bounce And Penal Transactions', headers: ['Date', 'Description', 'Category', 'Debit', 'Credit', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 6 — Salary Transactions', headers: ['Date', 'Description', 'Category', 'Debit', 'Credit', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 7 — Loan Repayment Transactions', headers: ['Date', 'Description', 'Category', 'Debit', 'Credit', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 8 — Credit Card Payments', headers: ['Date', 'Description', 'Category', 'Debit', 'Credit', 'Balance', 'Month'], rows: [] },
  { title: 'Sheet 9 — Transactions', headers: ['Date', 'Description', 'Ref/Cheque No', 'Debit', 'Credit', 'Balance', 'Category', 'Month'], rows: [] },
]

export default function ResultStep({ result, batchResults = [] }: ResultStepProps) {
  const [viewMode, setViewMode] = useState<'preview' | 'review'>('preview')
  const [expandedSheets, setExpandedSheets] = useState<Set<number>>(new Set())
  const [isDesktop, setIsDesktop] = useState(false)
  const [selectedBatchResultId, setSelectedBatchResultId] = useState<string>(batchResults[0]?.id || 'current')

  useEffect(() => {
    setIsDesktop(window.innerWidth >= 1024)
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    if (batchResults.length === 0) return

    setSelectedBatchResultId((current) => {
      const hasCurrent = batchResults.some((item) => item.id === current)
      return hasCurrent ? current : batchResults[0].id
    })
  }, [batchResults])

  const activeResult = batchResults.find((item) => item.id === selectedBatchResultId)?.result || result
  const batchOverview = batchResults.length > 1 ? {
    statementCount: batchResults.length,
    bankCount: new Set(batchResults.map((item) => item.bankName)).size,
    totalTransactions: batchResults.reduce((sum, item) => sum + Number(item.result.stats?.total_transactions || 0), 0),
  } : null
  const bankGroups = batchResults.length > 1
    ? Array.from(
        batchResults.reduce((groups, item) => {
          const group = groups.get(item.bankName) || {
            bankName: item.bankName,
            statementCount: 0,
            totalTransactions: 0,
            items: [] as typeof batchResults,
          }

          group.statementCount += 1
          group.totalTransactions += Number(item.result.stats?.total_transactions || 0)
          group.items.push(item)
          groups.set(item.bankName, group)
          return groups
        }, new Map<string, { bankName: string; statementCount: number; totalTransactions: number; items: typeof batchResults }>()
      ).values())
    : []

  const sheets: SheetPreview[] = [
    activeResult.account_summary || PLACEHOLDER_SHEETS[0],
    activeResult.monthly_analysis || PLACEHOLDER_SHEETS[1],
    activeResult.top5_credits || PLACEHOLDER_SHEETS[2],
    activeResult.top5_debits || PLACEHOLDER_SHEETS[3],
    activeResult.bounces_penal || PLACEHOLDER_SHEETS[4],
    activeResult.salary_transactions || PLACEHOLDER_SHEETS[5],
    activeResult.loan_repayment || PLACEHOLDER_SHEETS[6],
    activeResult.credit_card_payments || PLACEHOLDER_SHEETS[7],
    activeResult.raw_transactions || PLACEHOLDER_SHEETS[8], // Transactions last
  ]

  const modeLabel = activeResult.mode === 'hybrid' ? 'Hybrid (System + AI)' : 'Free (System Only)'

  const toggleSheetExpansion = (index: number) => {
    const newExpanded = new Set(expandedSheets)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedSheets(newExpanded)
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 className="w-6 h-6 text-black" />
        <h2 className="text-xl font-semibold text-black">
          Categorization Complete
        </h2>
      </div>
      <p className="text-base text-neutral-500 mb-4">
        {batchResults.length > 1
          ? 'Your statements have been categorized and structured. Select a statement below to preview or download its report.'
          : 'Your statement has been categorized and structured. Preview or download below.'}
      </p>

      {batchOverview && (
        <div className="mb-5 grid grid-cols-3 gap-2 rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-center">
          <div className="rounded-md bg-white px-3 py-2 shadow-sm ring-1 ring-neutral-100">
            <p className="text-sm font-semibold text-black">{batchOverview.statementCount}</p>
            <p className="text-[10px] text-neutral-500">Statements</p>
          </div>
          <div className="rounded-md bg-white px-3 py-2 shadow-sm ring-1 ring-neutral-100">
            <p className="text-sm font-semibold text-black">{batchOverview.bankCount}</p>
            <p className="text-[10px] text-neutral-500">Banks</p>
          </div>
          <div className="rounded-md bg-white px-3 py-2 shadow-sm ring-1 ring-neutral-100">
            <p className="text-sm font-semibold text-black">{batchOverview.totalTransactions}</p>
            <p className="text-[10px] text-neutral-500">Transactions</p>
          </div>
        </div>
      )}

      {bankGroups.length > 0 && (
        <div className="mb-5 space-y-3">
          {bankGroups.map((group) => (
            <details key={group.bankName} open className="rounded-lg border border-neutral-200 bg-white shadow-sm">
              <summary className="cursor-pointer list-none px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-black">{group.bankName}</p>
                    <p className="mt-1 text-xs text-neutral-500">
                      {group.statementCount} statement(s) • {group.totalTransactions} transactions
                    </p>
                  </div>
                  <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] uppercase tracking-wide text-neutral-500">
                    Bank group
                  </span>
                </div>
              </summary>
              <div className="border-t border-neutral-100 px-3 py-2 space-y-1.5">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setSelectedBatchResultId(item.id)}
                    className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition ${selectedBatchResultId === item.id
                      ? 'bg-black text-white'
                      : 'bg-neutral-50 text-black hover:bg-neutral-100'
                      }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.fileName}</p>
                      <p className={`truncate text-xs ${selectedBatchResultId === item.id ? 'text-neutral-200' : 'text-neutral-500'}`}>
                        {item.result.stats?.total_transactions || 0} transactions
                      </p>
                    </div>
                    <span className="ml-3 shrink-0 text-[10px] uppercase tracking-wide">
                      Select
                    </span>
                  </button>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}

      {batchResults.length > 1 && (
        <div className="mb-5 rounded-lg border border-neutral-200 bg-neutral-50 p-3">
          <label className="mb-2 block text-xs font-medium text-neutral-600">
            Select statement
          </label>
          <select
            value={selectedBatchResultId}
            onChange={(e) => setSelectedBatchResultId(e.target.value)}
            className="w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black"
          >
            {batchResults.map((item) => (
              <option key={item.id} value={item.id}>
                {item.bankName} — {item.fileName}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* View Options */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-neutral-600 bg-neutral-100 border border-neutral-200 px-3 py-1.5 rounded-full">
            {modeLabel}
          </span>
          {activeResult.stats && (
            <>
              <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                {activeResult.stats.total_transactions} transactions
              </span>
              <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                {activeResult.stats.coverage_percent}% categorized
              </span>
              {activeResult.stats.ai_classified > 0 && (
                <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                  {activeResult.stats.ai_classified} AI classified
                </span>
              )}
            </>
          )}
          {activeResult.ai_usage && (
            <span className="text-xs text-neutral-500 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full">
              AI Cost: ${activeResult.ai_usage.estimated_cost_usd?.toFixed(4)} (~₹{activeResult.ai_usage.estimated_cost_inr?.toFixed(2)})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('preview')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${viewMode === 'preview'
              ? 'bg-black text-white'
              : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
          >
            <Eye className="w-3.5 h-3.5" />
            Preview
          </button>
          {isDesktop && (
            <button
              onClick={() => setViewMode('review')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${viewMode === 'review'
                ? 'bg-black text-white'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Review Data
            </button>
          )}
        </div>
      </div>

      {viewMode === 'preview' && (
        <div className="space-y-3">
          {sheets.map((sheet, idx) => (
            <CollapsiblePreview key={idx} sheet={sheet} />
          ))}
        </div>
      )}

      {viewMode === 'review' && (
        <SpreadsheetProvider>
          <SpreadsheetEditor 
            initialResult={activeResult} 
            onExit={() => setViewMode('preview')} 
            apiKey={activeResult.mode === 'hybrid' ? 'requires-auth-key-passthrough-if-needed' : ''} 
          />
        </SpreadsheetProvider>
      )}

      {/* Download All button for batch results */}
      {batchResults.length > 1 && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Archive className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-900">
                {batchResults.filter(r => r.result.status === 'success').length} report(s) ready
              </span>
            </div>
            <button
              onClick={async () => {
                // Download all Excel files sequentially
                const successfulResults = batchResults.filter(r => r.result.status === 'success' && r.result.excel_url)
                for (let i = 0; i < successfulResults.length; i++) {
                  const item = successfulResults[i]
                  const link = document.createElement('a')
                  link.href = item.result.excel_url
                  link.download = `${item.bankName}_${item.fileName.replace(/\.pdf$/i, '')}_Report.xlsx`
                  document.body.appendChild(link)
                  link.click()
                  document.body.removeChild(link)
                  // Small delay between downloads
                  if (i < successfulResults.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 500))
                  }
                }
              }}
              disabled={batchResults.filter(r => r.result.status === 'success' && r.result.excel_url).length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="h-4 w-4" />
              Download All
            </button>
          </div>
          {batchResults.some(r => r.result.status === 'error') && (
            <p className="text-xs text-amber-600 mt-2">
              Note: {batchResults.filter(r => r.result.status === 'error').length} file(s) failed and won't be downloaded.
            </p>
          )}
        </div>
      )}

      <DownloadButtons
        excelUrl={activeResult.excel_url}
        pdfUrl={activeResult.pdf_url}
        result={activeResult}
        fileNameHint={
          batchResults.find((item) => item.id === selectedBatchResultId)?.fileName
          || 'airco_report'
        }
      />

      {/* Legal Disclaimer */}
      <p className="text-xs text-neutral-300 text-center mt-6 leading-relaxed">
        This report contains categorized transaction data only. No financial advice, predictions, or recommendations are provided.
      </p>
    </div>
  )
}
