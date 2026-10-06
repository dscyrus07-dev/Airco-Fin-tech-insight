import { NextRequest } from 'next/server'
import { forwardToBackend } from '@/lib/statementsProxy'

export async function POST(request: NextRequest, { params }: { params: Promise<{ analysisId: string }> }) {
  const { analysisId } = await params
  const body = await request.text()
  return forwardToBackend(request, `/api/statements/${encodeURIComponent(analysisId)}/confirm`, { method: 'POST', body, json: true })
}
