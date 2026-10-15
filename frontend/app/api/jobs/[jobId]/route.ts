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
    if (resultData && !resultData?.excel_url) {
      // Signed, short-lived, single-job token so a plain link can download.
      const dl = resultData.download_token ? `?t=${encodeURIComponent(resultData.download_token)}` : ''
      resultData.excel_url = `/api/jobs/${encodeURIComponent(jobId)}/download${dl}`
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
