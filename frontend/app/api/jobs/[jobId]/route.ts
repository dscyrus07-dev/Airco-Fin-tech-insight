import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const authorization = request.headers.get('authorization')
    const token = request.nextUrl.searchParams.get('t')
    const query = token ? `?t=${encodeURIComponent(token)}` : ''
    const response = await fetch(`${BACKEND_URL}/api/jobs/${encodeURIComponent(jobId)}${query}`, {
      headers: authorization ? { Authorization: authorization } : undefined,
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      const detail = data?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.error || data?.message || 'Failed to fetch job status.'

      return NextResponse.json({ message }, { status: response.status })
    }

    const resultData = data?.result_data
    if (resultData) {
      // Signed, short-lived, single-job token so a plain link can download.
      // The backend persists an unsigned excel_url, so always (re)sign ours.
      const dl = resultData.download_token ? `?t=${encodeURIComponent(resultData.download_token)}` : ''
      const canonical = `/api/jobs/${encodeURIComponent(jobId)}/download`
      const existing: string = typeof resultData.excel_url === 'string' ? resultData.excel_url : ''
      if (!existing || existing.split('?')[0].replace(/\/+$/, '') === canonical || /^\/api\/jobs\/[^/]+\/download$/.test(existing.split('?')[0])) {
        resultData.excel_url = `${canonical}${dl}`
      } else if (dl && existing.startsWith('/') && !/[?&]t=/.test(existing)) {
        resultData.excel_url = `${existing}${existing.includes('?') ? '&' : '?'}${dl.slice(1)}`
      }
    }

    return NextResponse.json(data)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { message: `Cannot reach backend server (${message}).` },
      { status: 502 }
    )
  }
}
