import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const authorization = request.headers.get('authorization')
    const response = await fetch(`${BACKEND_URL}/api/jobs/${jobId}`, {
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
      resultData.excel_url = `/api/jobs/${encodeURIComponent(jobId)}/download`
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
