import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const authorization = request.headers.get('authorization')
    const response = await fetch(`${BACKEND_URL}/api/jobs/${jobId}/download`, {
      headers: authorization ? { Authorization: authorization } : undefined,
    })

    if (!response.ok) {
      const data = await response.json().catch(() => null)
      const detail = data?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.error || data?.message || 'Failed to download file.'

      return NextResponse.json({ message }, { status: response.status })
    }

    const contentType = response.headers.get('content-type') || 'application/octet-stream'
    const disposition = response.headers.get('content-disposition') || 'attachment'
    const buffer = await response.arrayBuffer()

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': disposition,
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { message: `Cannot reach backend server (${message}).` },
      { status: 502 }
    )
  }
}
