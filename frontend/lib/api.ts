import { ProcessingResult, ProcessingMode, StatementTypeSelection, UserDetails } from '@/types'

const API_URL = '/api'

// Helper function to get auth token
async function getAuthToken(): Promise<string | null> {
  try {
    // Get token from Keycloak context
    const { useAuth } = await import('../contexts/AuthContext')
    const auth = useAuth()
    return await auth.getAccessToken()
  } catch (error) {
    console.error('Failed to get auth token:', error)
    return null
  }
}

// Helper function to make authenticated API calls
async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken()
  
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
    'Content-Type': 'application/json',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  return fetch(url, {
    ...options,
    headers,
  })
}

export async function uploadStatement(
  file: File,
  userDetails: UserDetails,
  mode: ProcessingMode = 'free',
  apiKey?: string,
  pdfPassword?: string,
  batchId?: string,
  statementLabel?: string,
  bankName?: string,
  accountType?: StatementTypeSelection,
): Promise<ProcessingResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('full_name', userDetails.fullName)
  formData.append('account_type', accountType || userDetails.accountType)
  formData.append('bank_name', bankName || userDetails.bankName)
  formData.append('mode', mode)

  if (batchId) {
    formData.append('batch_id', batchId)
  }

  if (statementLabel) {
    formData.append('statement_label', statementLabel)
  }

  if (mode === 'hybrid' && apiKey) {
    formData.append('api_key', apiKey)
  }

  if (pdfPassword) {
    formData.append('pdf_password', pdfPassword)
  }

  // Get auth token
  const token = await getAuthToken()
  const headers: Record<string, string> = {}
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_URL}/upload/bank-statement`, {
    method: 'POST',
    body: formData,
    headers,
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    const raw = errorData?.detail ?? errorData
    const message =
      typeof raw === 'string'
        ? raw
        : raw?.error || raw?.message || errorData?.message || 'Failed to process statement. Please try again.'
    const error = new Error(message) as Error & { code?: string; needs_password?: boolean }
    error.code = typeof raw === 'object' && raw ? raw.code || errorData?.code : errorData?.code
    error.needs_password = Boolean(
      typeof raw === 'object' && raw && (raw.requires_password || raw.code === 'PDF_PASSWORD_REQUIRED' || raw.code === 'PDF_PASSWORD_INVALID')
    )
    throw error
  }

  return response.json()
}

export async function getUserJobs(): Promise<any[]> {
  const response = await authenticatedFetch(`${API_URL}/jobs`)
  
  if (!response.ok) {
    throw new Error('Failed to fetch jobs')
  }
  
  return response.json()
}

export async function getJobStatus(jobId: string): Promise<any> {
  const response = await authenticatedFetch(`${API_URL}/jobs/${jobId}`)
  
  if (!response.ok) {
    throw new Error('Failed to fetch job status')
  }
  
  return response.json()
}

export async function cancelJob(jobId: string): Promise<void> {
  const response = await authenticatedFetch(`${API_URL}/jobs/${jobId}/cancel`, {
    method: 'POST',
  })
  
  if (!response.ok) {
    throw new Error('Failed to cancel job')
  }
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await authenticatedFetch(`${API_URL}/jobs/${jobId}`, {
    method: 'DELETE',
  })
  
  if (!response.ok) {
    throw new Error('Failed to delete job')
  }
}
