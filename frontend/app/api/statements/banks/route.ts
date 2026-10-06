import { NextRequest } from 'next/server'
import { forwardToBackend } from '@/lib/statementsProxy'

export async function GET(request: NextRequest) {
  return forwardToBackend(request, '/api/statements/banks')
}
