import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function authHeaders(request: NextRequest): HeadersInit {
  const authorization = request.headers.get('authorization')
  const cookieToken = request.cookies.get('kc_token')?.value
  const authHeader = authorization || (cookieToken ? `Bearer ${cookieToken}` : undefined)
  const headers: HeadersInit = {}
  if (authHeader) headers.Authorization = authHeader
  return headers
}

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/api-keys`, {
      headers: authHeaders(request),
      cache: 'no-store',
    })
    const data = await response.json().catch(() => null)
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json({ message: `Cannot reach backend (${msg}).` }, { status: 502 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const response = await fetch(`${BACKEND_URL}/api/v1/api-keys`, {
      method: 'POST',
      headers: {
        ...authHeaders(request),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    const data = await response.json().catch(() => null)
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json({ message: `Cannot reach backend (${msg}).` }, { status: 502 })
  }
}
