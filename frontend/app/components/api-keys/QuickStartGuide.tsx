'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'

type QuickStartGuideProps = {
  keyPrefix: string
}

const BASE_URL = 'https://insights.theairco.ai'

const BANK_CODES = [
  { key: 'hdfc', aliases: 'HDFC, HDFC Bank' },
  { key: 'icici', aliases: 'ICICI, ICICI Bank' },
  { key: 'axis', aliases: 'AXIS, Axis Bank' },
  { key: 'kotak', aliases: 'KOTAK, Kotak Bank' },
  { key: 'sbi', aliases: 'SBI, State Bank' },
  { key: 'canara', aliases: 'CANARA, Canara Bank' },
  { key: 'idfc', aliases: 'IDFC, IDFC First, IDFC First Bank' },
  { key: 'karnataka', aliases: 'KARNATAKA, Karnataka Bank' },
  { key: 'paytm', aliases: 'PAYTM, Paytm Bank' },
  { key: 'union', aliases: 'UNION, Union Bank, Union Bank of India' },
  { key: 'bank_of_baroda', aliases: 'Bank of Baroda, BankOfBaroda, BOB' },
  { key: 'unknown', aliases: 'UNKNOWN, Unknown Bank (auto-detect)' },
]

const STATUS_ENUMS = [
  { value: 'pending', description: 'Job accepted, waiting in queue' },
  { value: 'running', description: 'PDF parsing + classification in progress' },
  { value: 'completed', description: 'Report ready for download' },
  { value: 'failed', description: 'Processing error — check error_message field' },
  { value: 'cancelled', description: 'Job was cancelled' },
]

const ERROR_CODES = [
  { code: '401', meaning: 'Invalid, revoked, or missing API key' },
  { code: '403', meaning: 'API key lacks required scope (e.g. upload, jobs:read, download)' },
  { code: '404', meaning: 'Job not found, or result file missing' },
  { code: '413', meaning: 'File exceeds 20 MB limit' },
  { code: '422', meaning: 'Unsupported bank_name or invalid form data' },
  { code: '429', meaning: 'Rate limit exceeded — retry after 60 seconds' },
  { code: '500', meaning: 'Internal server error — retry with backoff' },
  { code: '503', message: 'Storage upload failed — retry' },
]

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative">
      {label && (
        <div className="mb-1 text-xs font-medium text-neutral-500">{label}</div>
      )}
      <div className="group relative rounded-lg border border-neutral-200 bg-neutral-900">
        <pre className="overflow-x-auto whitespace-pre-wrap break-all p-3 font-mono text-[11px] leading-relaxed text-neutral-100">
          {code}
        </pre>
        <button
          onClick={copy}
          className="absolute right-2 top-2 rounded-md border border-neutral-700 bg-neutral-800 p-1.5 text-neutral-400 opacity-0 transition-opacity hover:text-white group-hover:opacity-100"
          title="Copy"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  )
}

function Section({
  title,
  number,
  children,
  defaultOpen = false,
}: {
  title: string
  number: number
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-neutral-200">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 py-3 text-left"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-neutral-400" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-neutral-400" />
        )}
        <span className="text-sm font-medium text-black">
          <span className="text-neutral-400">{number}.</span> {title}
        </span>
      </button>
      {open && <div className="pb-4">{children}</div>}
    </div>
  )
}

export default function QuickStartGuide({ keyPrefix }: QuickStartGuideProps) {
  const pk = keyPrefix || 'airco_sk_live_…'

  const uploadCurl = `# Upload a bank statement PDF
curl -X POST "${BASE_URL}/api/v1/statements" \\
  -H "X-API-Key: ${pk}YOUR_SECRET" \\
  -F "file=@statement.pdf" \\
  -F "bank_name=HDFC" \\
  -F "mode=free" \\
  -F "pdf_password=1234"`

  const uploadResponse = `{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "submitted",
  "message": "Processing started. Check job status with /api/v1/jobs/{job_id}"
}`

  const pollCurl = `# Poll job status (poll every 5 seconds)
curl "${BASE_URL}/api/v1/jobs/job_a1b2c3d4e5f6" \\
  -H "X-API-Key: ${pk}YOUR_SECRET"`

  const pollResponsePending = `{
  "id": "job_a1b2c3d4e5f6",
  "type": "pdf_processing",
  "status": "running",
  "correlation_id": "corr_xyz123",
  "bank_name": "HDFC",
  "created_at": "2025-07-21T10:30:00Z",
  "started_at": "2025-07-21T10:30:01Z",
  "completed_at": null,
  "error_message": null,
  "input_data": { ... },
  "result_data": {}
}`

  const pollResponseCompleted = `{
  "id": "job_a1b2c3d4e5f6",
  "type": "pdf_processing",
  "status": "completed",
  "correlation_id": "corr_xyz123",
  "bank_name": "HDFC",
  "created_at": "2025-07-21T10:30:00Z",
  "started_at": "2025-07-21T10:30:01Z",
  "completed_at": "2025-07-21T10:30:45Z",
  "error_message": null,
  "input_data": { ... },
  "result_data": {
    "excel_path": "/tmp/.../report.xlsx",
    "excel_object_key": "users/.../report.xlsx"
  }
}`

  const pollResponseFailed = `{
  "id": "job_a1b2c3d4e5f6",
  "type": "pdf_processing",
  "status": "failed",
  "correlation_id": "corr_xyz123",
  "bank_name": "HDFC",
  "created_at": "2025-07-21T10:30:00Z",
  "started_at": "2025-07-21T10:30:01Z",
  "completed_at": "2025-07-21T10:30:10Z",
  "error_message": "Failed to parse PDF: encrypted file, password incorrect",
  "input_data": { ... },
  "result_data": {}
}`

  const downloadCurl = `# Download the Excel report (only when status=completed)
curl -L "${BASE_URL}/api/v1/jobs/job_a1b2c3d4e5f6/download" \\
  -H "X-API-Key: ${pk}YOUR_SECRET" \\
  -o statement_HDFC_report.xlsx`

  const pythonSnippet = `import requests, time

BASE = "${BASE_URL}"
HEADERS = {"X-API-Key": "${pk}YOUR_SECRET"}

# 1. Upload
with open("statement.pdf", "rb") as f:
    resp = requests.post(f"{BASE}/api/v1/statements", headers=HEADERS,
        files={"file": f}, data={"bank_name": "HDFC", "mode": "free"})
job_id = resp.json()["job_id"]

# 2. Poll until completed
while True:
    job = requests.get(f"{BASE}/api/v1/jobs/{job_id}", headers=HEADERS).json()
    if job["status"] in ("completed", "failed"):
        break
    time.sleep(5)

if job["status"] != "completed":
    raise RuntimeError(job.get("error_message", "Job failed"))

# 3. Download
report = requests.get(f"{BASE}/api/v1/jobs/{job_id}/download", headers=HEADERS)
with open("report.xlsx", "wb") as f:
    f.write(report.content)`

  const nodeSnippet = `const fs = require('fs')
const BASE = '${BASE_URL}'
const HEADERS = { 'X-API-Key': '${pk}YOUR_SECRET' }

async function main() {
  // 1. Upload
  const form = new FormData()
  form.append('file', new Blob([fs.readFileSync('statement.pdf')]), 'statement.pdf')
  form.append('bank_name', 'HDFC')
  form.append('mode', 'free')
  const upload = await fetch(BASE + '/api/v1/statements', { method: 'POST', headers: HEADERS, body: form })
  const { job_id } = await upload.json()

  // 2. Poll
  let job
  while (true) {
    job = await (await fetch(BASE + '/api/v1/jobs/' + job_id, { headers: HEADERS })).json()
    if (['completed', 'failed'].includes(job.status)) break
    await new Promise(r => setTimeout(r, 5000))
  }
  if (job.status !== 'completed') throw new Error(job.error_message)

  // 3. Download
  const report = await fetch(BASE + '/api/v1/jobs/' + job_id + '/download', { headers: HEADERS })
  fs.writeFileSync('report.xlsx', Buffer.from(await report.arrayBuffer()))
}
main()`

  const aiPrompt = `You are an AI assistant integrating with the Airco Insights API.

## API Quick Reference
- Base URL: ${BASE_URL}
- Auth: X-API-Key header (format: airco_sk_live_<32hex> or airco_sk_test_<32hex>)
- Upload: POST /api/v1/statements (multipart form: file, bank_name, mode=free, pdf_password?)
- Poll: GET /api/v1/jobs/{job_id}
- Download: GET /api/v1/jobs/{job_id}/download

## Supported bank_name values
hdfc, icici, axis, kotak, sbi, canara, idfc, karnataka, paytm, union, bank_of_baroda, unknown

## Job status values
pending -> running -> completed | failed

## Polling
Poll every 5 seconds. Timeout after 120 seconds.
Download is only available when status=completed.

## File constraints
- PDF only, max 20 MB
- Password-protected PDFs: pass pdf_password form field

## Error codes
401=bad key, 403=missing scope, 404=not found, 413=file too large,
422=unsupported bank, 429=rate limited (retry after 60s), 500=server error`

  return (
    <div className="rounded-xl border border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 px-5 py-4">
        <h2 className="text-base font-semibold text-black">Integrator&apos;s Quickstart</h2>
        <p className="mt-1 text-xs text-neutral-500">
          Complete API reference for automated bank statement processing. No guesswork needed.
        </p>
      </div>

      <div className="px-5">
        {/* Base URL & Auth */}
        <Section title="Base URL & Authentication" number={1} defaultOpen={true}>
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
                <div className="text-xs font-medium text-neutral-500">Live (Production)</div>
                <code className="mt-1 block font-mono text-xs text-black">{BASE_URL}</code>
              </div>
              <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
                <div className="text-xs font-medium text-neutral-500">Sandbox (Test keys)</div>
                <code className="mt-1 block font-mono text-xs text-black">{BASE_URL}</code>
                <div className="mt-1 text-[10px] text-neutral-400">
                  Test keys (airco_sk_test_*) and live keys (airco_sk_live_*) both hit the same domain.
                  Test keys are rate-limited and watermarked.
                </div>
              </div>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-xs text-blue-900">
              <strong>Authentication header:</strong> Pass your API key in the{' '}
              <code className="font-mono">X-API-Key</code> header. Key format is{' '}
              <code className="font-mono">airco_sk_live_&lt;32hex&gt;</code> or{' '}
              <code className="font-mono">airco_sk_test_&lt;32hex&gt;</code>. Do NOT base64-encode the key.
              The full key is shown only once at creation time — store it securely.
            </div>
          </div>
        </Section>

        {/* Supported Banks */}
        <Section title="Supported bank_name Values" number={2} defaultOpen={true}>
          <div className="space-y-2">
            <p className="text-xs text-neutral-600">
              Pass any of these as the <code className="font-mono">bank_name</code> form field. Values are
              case-insensitive. Both short codes and full names are accepted.
            </p>
            <div className="overflow-hidden rounded-lg border border-neutral-200">
              <table className="w-full text-xs">
                <thead className="bg-neutral-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-neutral-500">Key (recommended)</th>
                    <th className="px-3 py-2 text-left font-medium text-neutral-500">Accepted aliases</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {BANK_CODES.map((b) => (
                    <tr key={b.key}>
                      <td className="px-3 py-2 font-mono text-black">{b.key}</td>
                      <td className="px-3 py-2 text-neutral-600">{b.aliases}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-neutral-400">
              Use <code className="font-mono">unknown</code> if you don&apos;t know the bank — the engine
              will auto-detect from the PDF content.
            </p>
          </div>
        </Section>

        {/* Upload */}
        <Section title="Upload Statement (POST /api/v1/statements)" number={3} defaultOpen={true}>
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-xs font-medium text-neutral-500">Form fields</div>
              <div className="overflow-hidden rounded-lg border border-neutral-200">
                <table className="w-full text-xs">
                  <thead className="bg-neutral-50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-neutral-500">Field</th>
                      <th className="px-3 py-2 text-left font-medium text-neutral-500">Required</th>
                      <th className="px-3 py-2 text-left font-medium text-neutral-500">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    <tr><td className="px-3 py-2 font-mono text-black">file</td><td className="px-3 py-2 text-red-600">Yes</td><td className="px-3 py-2 text-neutral-600">PDF file (max 20 MB)</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">bank_name</td><td className="px-3 py-2 text-red-600">Yes</td><td className="px-3 py-2 text-neutral-600">Bank code (see list above)</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">mode</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">Always <code className="font-mono">free</code> (default). <code className="font-mono">hybrid</code> is not available via API.</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">pdf_password</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">Password for encrypted PDFs. If omitted on a protected PDF, the job will fail with a password error.</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">full_name</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">Account holder name (for report header)</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">account_type</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">e.g. savings, current</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">batch_id</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">Group multiple uploads under a batch</td></tr>
                    <tr><td className="px-3 py-2 font-mono text-black">statement_label</td><td className="px-3 py-2 text-neutral-400">No</td><td className="px-3 py-2 text-neutral-600">Custom label for the statement</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <CodeBlock label="cURL — upload (with password-protected PDF)" code={uploadCurl} />
            <CodeBlock label="Response (200 OK)" code={uploadResponse} />
          </div>
        </Section>

        {/* Poll */}
        <Section title="Poll Job Status (GET /api/v1/jobs/{job_id})" number={4} defaultOpen={true}>
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-xs font-medium text-neutral-500">Job status values</div>
              <div className="overflow-hidden rounded-lg border border-neutral-200">
                <table className="w-full text-xs">
                  <thead className="bg-neutral-50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-neutral-500">Status</th>
                      <th className="px-3 py-2 text-left font-medium text-neutral-500">Meaning</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {STATUS_ENUMS.map((s) => (
                      <tr key={s.value}>
                        <td className="px-3 py-2 font-mono text-black">{s.value}</td>
                        <td className="px-3 py-2 text-neutral-600">{s.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-xs text-amber-900">
              <strong>Polling guidance:</strong> Poll every <strong>5 seconds</strong>. Typical processing
              takes <strong>10-60 seconds</strong> depending on PDF size and page count. Set a client-side
              timeout of <strong>120 seconds</strong>. Stop polling when status is{' '}
              <code className="font-mono">completed</code> or <code className="font-mono">failed</code>.
            </div>
            <CodeBlock label="cURL — poll" code={pollCurl} />
            <CodeBlock label="Response — running" code={pollResponsePending} />
            <CodeBlock label="Response — completed" code={pollResponseCompleted} />
            <CodeBlock label="Response — failed" code={pollResponseFailed} />
          </div>
        </Section>

        {/* Download */}
        <Section title="Download Report (GET /api/v1/jobs/{job_id}/download)" number={5} defaultOpen={true}>
          <div className="space-y-3">
            <CodeBlock label="cURL — download" code={downloadCurl} />
            <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600">
              <p className="font-medium text-black">Response details:</p>
              <ul className="mt-2 space-y-1">
                <li>• <strong>Content-Type:</strong> <code className="font-mono">application/vnd.openxmlformats-officedocument.spreadsheetml.sheet</code></li>
                <li>• <strong>Content-Disposition:</strong> <code className="font-mono">attachment; filename=&quot;statement_HDFC_report.xlsx&quot;</code></li>
                <li>• <strong>200 OK:</strong> Binary .xlsx file stream</li>
                <li>• <strong>400:</strong> Job not completed yet — keep polling</li>
                <li>• <strong>404:</strong> Job not found or result file expired</li>
              </ul>
            </div>
          </div>
        </Section>

        {/* Error Codes */}
        <Section title="Error Codes & HTTP Status" number={6}>
          <div className="overflow-hidden rounded-lg border border-neutral-200">
            <table className="w-full text-xs">
              <thead className="bg-neutral-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500">HTTP Code</th>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500">Meaning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {ERROR_CODES.map((e) => (
                  <tr key={e.code}>
                    <td className="px-3 py-2 font-mono text-black">{e.code}</td>
                    <td className="px-3 py-2 text-neutral-600">{e.meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 text-[11px] text-neutral-400">
            All errors return JSON: <code className="font-mono">{`{ "detail": "error message" }`}</code>.
            Rate-limited responses (429) include no retry-after header — wait 60 seconds before retrying.
          </div>
        </Section>

        {/* File Constraints */}
        <Section title="File Constraints" number={7}>
          <div className="space-y-2 text-xs text-neutral-600">
            <ul className="space-y-1.5">
              <li>• <strong>Format:</strong> PDF only (text-based or scanned). Image-only PDFs are not supported.</li>
              <li>• <strong>Max file size:</strong> 20 MB</li>
              <li>• <strong>Page limit:</strong> No hard limit, but processing time scales with page count</li>
              <li>• <strong>Multi-account:</strong> Each PDF should contain one account. Multi-account PDFs may produce partial results.</li>
              <li>• <strong>Password-protected:</strong> Pass <code className="font-mono">pdf_password</code> form field. If the password is wrong, the job fails with <code className="font-mono">&quot;Failed to parse PDF: encrypted file, password incorrect&quot;</code></li>
              <li>• <strong>Scanned PDFs:</strong> Supported if they contain extractable text. Pure image PDFs (no text layer) are not supported.</li>
            </ul>
          </div>
        </Section>

        {/* Rate Limits */}
        <Section title="Rate Limits & Concurrency" number={8}>
          <div className="space-y-2 text-xs text-neutral-600">
            <ul className="space-y-1.5">
              <li>• <strong>Default rate limit:</strong> 60 requests per minute per API key</li>
              <li>• <strong>Daily quota:</strong> Configurable per key (0 = unlimited by default)</li>
              <li>• <strong>Concurrency:</strong> Multiple jobs can run in parallel. No hard limit, but rate limiting applies to all requests including polling.</li>
              <li>• <strong>429 response:</strong> <code className="font-mono">{`{ "detail": "Rate limit exceeded" }`}</code> — wait 60 seconds before retrying</li>
              <li>• <strong>Tip:</strong> Poll less frequently (every 5s, not every 1s) to avoid burning your rate limit on polling</li>
            </ul>
          </div>
        </Section>

        {/* API Key Scopes */}
        <Section title="API Key Scopes" number={9}>
          <div className="overflow-hidden rounded-lg border border-neutral-200">
            <table className="w-full text-xs">
              <thead className="bg-neutral-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500">Scope</th>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500">Required for</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                <tr><td className="px-3 py-2 font-mono text-black">upload</td><td className="px-3 py-2 text-neutral-600">POST /api/v1/statements</td></tr>
                <tr><td className="px-3 py-2 font-mono text-black">jobs:read</td><td className="px-3 py-2 text-neutral-600">GET /api/v1/jobs/{'{job_id}'}, GET /api/v1/jobs</td></tr>
                <tr><td className="px-3 py-2 font-mono text-black">download</td><td className="px-3 py-2 text-neutral-600">GET /api/v1/jobs/{'{job_id}'}/download</td></tr>
                <tr><td className="px-3 py-2 font-mono text-black">jobs:delete</td><td className="px-3 py-2 text-neutral-600">DELETE /api/v1/jobs/{'{job_id}'}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-neutral-400">
            New keys default to <code className="font-mono">upload, jobs:read, download</code>. Missing a
            scope returns <code className="font-mono">403</code> with{' '}
            <code className="font-mono">{`{ "detail": "Missing required scope: upload" }`}</code>.
          </p>
        </Section>

        {/* Code Samples */}
        <Section title="Code Samples (Python & Node.js)" number={10}>
          <div className="space-y-3">
            <CodeBlock label="Python — full flow" code={pythonSnippet} />
            <CodeBlock label="Node.js — full flow" code={nodeSnippet} />
          </div>
        </Section>

        {/* AI Prompt */}
        <Section title="AI / LLM Integration Prompt" number={11}>
          <div className="space-y-2">
            <p className="text-xs text-neutral-600">
              Paste this prompt into your AI agent or LLM to give it full context about the API. Works with
              Claude, GPT, Cursor, Windsurf, and other AI coding assistants.
            </p>
            <CodeBlock label="System prompt for AI agents" code={aiPrompt} />
          </div>
        </Section>
      </div>

      <div className="border-t border-neutral-200 px-5 py-3">
        <p className="text-[11px] text-neutral-400">
          Need help? Generate or manage your API keys on this page. All endpoints require the{' '}
          <code className="font-mono">X-API-Key</code> header.
        </p>
      </div>
    </div>
  )
}
