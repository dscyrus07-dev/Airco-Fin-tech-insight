import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function buildProxyHeaders(request: NextRequest): HeadersInit {
  const authorization = request.headers.get('authorization')
  const cookieToken = request.cookies.get('kc_token')?.value
  const authHeader = authorization || (cookieToken ? `Bearer ${cookieToken}` : undefined)
  const userId =
    request.headers.get('x-airco-user-id') || request.cookies.get('kc_user_id')?.value
  const userEmail =
    request.headers.get('x-airco-user-email') || request.cookies.get('kc_user_email')?.value
  const userName =
    request.headers.get('x-airco-user-name') || request.cookies.get('kc_user_name')?.value
  const preferredUsername =
    request.headers.get('x-airco-preferred-username') ||
    request.cookies.get('kc_preferred_username')?.value

  const headers: HeadersInit = {}
  if (authHeader) headers.Authorization = authHeader
  if (userId) headers['X-Airco-User-Id'] = userId
  if (userEmail) headers['X-Airco-User-Email'] = userEmail
  if (userName) headers['X-Airco-User-Name'] = userName
  if (preferredUsername) headers['X-Airco-Preferred-Username'] = preferredUsername
  return headers
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ fileId: string }> | { fileId: string } },
) {
  try {
    const params = await Promise.resolve(context.params)
    const fileId = params.fileId
    if (!fileId) {
      return NextResponse.json({ message: 'File id is required.' }, { status: 400 })
    }

    const headers = buildProxyHeaders(request)
    const response = await fetch(
      `${BACKEND_URL}/api/profile/files/${encodeURIComponent(fileId)}`,
      {
        method: 'DELETE',
        headers: Object.keys(headers).length ? headers : undefined,
      },
    )

    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = data?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.error || data?.message || 'Failed to delete file.'
      return NextResponse.json({ message }, { status: response.status })
    }

    return NextResponse.json(data || { message: 'File deleted successfully' })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { message: `Cannot reach backend server (${message}).` },
      { status: 502 },
    )
  }
}
