import { NextRequest } from 'next/server'
import { forwardToBackend } from '@/lib/statementsProxy'

export async function GET(request: NextRequest, { params }: { params: Promise<{ analysisId: string }> }) {
  const { analysisId } = await params
  return forwardToBackend(request, `/api/statements/${encodeURIComponent(analysisId)}`)
}
