import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  try {
    const { filename } = await params

    if (!filename) {
      return NextResponse.json({ message: 'No filename provided.' }, { status: 400 })
    }

    const backendUrl = `${BACKEND_URL}/download/${encodeURIComponent(filename)}`
    console.log(`Proxying download: ${backendUrl}`)

    const response = await fetch(backendUrl)

    if (!response.ok) {
      return NextResponse.json(
        { message: 'File not found or expired.' },
        { status: response.status }
      )
    }

    const contentType = response.headers.get('content-type') || 'application/octet-stream'
    const buffer = await response.arrayBuffer()

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    })
  } catch (error) {
    console.error('Download proxy error:', error)
    return NextResponse.json(
      { message: 'Failed to download file.' },
      { status: 502 }
    )
  }
}
