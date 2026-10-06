import { NextRequest } from 'next/server'
import { forwardToBackend } from '@/lib/statementsProxy'

export async function POST(request: NextRequest) {
  let incoming: FormData
  try {
    incoming = await request.formData()
  } catch {
    return Response.json({ message: 'Please attach at least one PDF.', code: 'BAD_REQUEST' }, { status: 400 })
  }
  const form = new FormData()
  for (const file of incoming.getAll('files')) {
    if (file instanceof Blob) form.append('files', file, (file as File).name)
  }
  const passwords = incoming.get('passwords')
  if (typeof passwords === 'string' && passwords) form.append('passwords', passwords)
  return forwardToBackend(request, '/api/statements/analyze', { method: 'POST', body: form })
}
