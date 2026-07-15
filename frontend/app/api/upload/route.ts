import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const authorization = request.headers.get('authorization')
    const cookieToken = request.cookies.get('kc_token')?.value
    const authHeader = authorization || (cookieToken ? `Bearer ${cookieToken}` : undefined)
    const userId = request.cookies.get('kc_user_id')?.value
    const userEmail = request.cookies.get('kc_user_email')?.value
    const userName = request.cookies.get('kc_user_name')?.value
    const preferredUsername = request.cookies.get('kc_preferred_username')?.value

    const file = formData.get('file')
    if (!file || !(file instanceof Blob)) {
      return NextResponse.json(
        { message: 'No PDF file provided.' },
        { status: 400 }
      )
    }

    const backendForm = new FormData()
    backendForm.append('file', file)
    backendForm.append('full_name', (formData.get('full_name') as string) || '')
    backendForm.append('account_type', (formData.get('account_type') as string) || '')
    backendForm.append('bank_name', (formData.get('bank_name') as string) || '')
    backendForm.append('mode', (formData.get('mode') as string) || 'free')

    const batchId = formData.get('batch_id') as string
    if (batchId) {
      backendForm.append('batch_id', batchId)
    }

    const statementLabel = formData.get('statement_label') as string
    if (statementLabel) {
      backendForm.append('statement_label', statementLabel)
    }

    const apiKey = formData.get('api_key') as string
    if (apiKey) {
      backendForm.append('api_key', apiKey)
    }

    const pdfPassword = formData.get('pdf_password') as string
    if (pdfPassword) {
      backendForm.append('pdf_password', pdfPassword)
    }

    const headers: HeadersInit = {}
    if (authHeader) headers.Authorization = authHeader
    if (userId) headers['X-Airco-User-Id'] = userId
    if (userEmail) headers['X-Airco-User-Email'] = userEmail
    if (userName) headers['X-Airco-User-Name'] = userName
    if (preferredUsername) headers['X-Airco-Preferred-Username'] = preferredUsername
    const response = await fetch(`${BACKEND_URL}/api/upload/bank-statement-async`, {
      method: 'POST',
      body: backendForm,
      headers: Object.keys(headers).length ? headers : undefined,
    })

    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const raw = data?.detail
      const message =
        typeof raw === 'string'
          ? raw
          : raw?.error || raw?.message || data?.message || 'Upload failed. Please try again.'
      const code = typeof raw === 'object' && raw ? raw.code : data?.code
      const needsPassword = Boolean(
        typeof raw === 'object' && raw && (raw.requires_password || raw.code === 'PDF_PASSWORD_REQUIRED' || raw.code === 'PDF_PASSWORD_INVALID')
      )

      return NextResponse.json({ message, code, needs_password: needsPassword }, { status: response.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Upload route error:', error)
    const msg = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { message: `Cannot reach backend server (${msg}).` },
      { status: 502 }
    )
  }
}
