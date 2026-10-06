import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Forwards the signed-in user's token to the backend. The backend does the authentication and ownership checks.
export async function forwardToBackend(
  request: NextRequest,
  path: string,
  init: { method: 'GET' | 'POST'; body?: BodyInit | null; json?: boolean } = { method: 'GET' }
): Promise<NextResponse> {
  try {
    const authorization = request.headers.get('authorization')
    const cookieToken = request.cookies.get('kc_token')?.value
    const authHeader = authorization || (cookieToken ? `Bearer ${cookieToken}` : undefined)
    const headers: Record<string, string> = {}
    if (authHeader) headers.Authorization = authHeader
    if (init.json) headers['Content-Type'] = 'application/json'

    const response = await fetch(`${BACKEND_URL}${path}`, {
      method: init.method,
      body: init.body ?? undefined,
      headers,
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const raw = data?.detail
      const message =
        typeof raw === 'string' ? raw : raw?.error || raw?.message || data?.message || 'Request failed. Please try again.'
      const code = typeof raw === 'object' && raw ? raw.code : undefined
      return NextResponse.json({ message, code }, { status: response.status })
    }
    return NextResponse.json(data)
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json({ message: `Cannot reach backend server (${msg}).` }, { status: 502 })
  }
}
