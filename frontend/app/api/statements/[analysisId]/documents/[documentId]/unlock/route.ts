import { NextRequest } from 'next/server'
import { forwardToBackend } from '@/lib/statementsProxy'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ analysisId: string; documentId: string }> }
) {
  const { analysisId, documentId } = await params
  const body = await request.text()
  return forwardToBackend(
    request,
    `/api/statements/${encodeURIComponent(analysisId)}/documents/${encodeURIComponent(documentId)}/unlock`,
    { method: 'POST', body, json: true }
  )
}
