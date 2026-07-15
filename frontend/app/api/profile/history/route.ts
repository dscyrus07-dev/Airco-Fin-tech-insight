import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const authorization = request.headers.get('authorization')
    const cookieToken = request.cookies.get('kc_token')?.value
    const authHeader = authorization || (cookieToken ? `Bearer ${cookieToken}` : undefined)
    const userId = request.cookies.get('kc_user_id')?.value
    const userEmail = request.cookies.get('kc_user_email')?.value
    const userName = request.cookies.get('kc_user_name')?.value
    const preferredUsername = request.cookies.get('kc_preferred_username')?.value
    const headers: HeadersInit = {}
    if (authHeader) headers.Authorization = authHeader
    if (userId) headers['X-Airco-User-Id'] = userId
    if (userEmail) headers['X-Airco-User-Email'] = userEmail
    if (userName) headers['X-Airco-User-Name'] = userName
    if (preferredUsername) headers['X-Airco-Preferred-Username'] = preferredUsername
    const response = await fetch(`${BACKEND_URL}/api/profile/history`, {
      headers: Object.keys(headers).length ? headers : undefined,
    })

    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = data?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.error || data?.message || 'Failed to load profile history.'

      return NextResponse.json({ message }, { status: response.status })
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
