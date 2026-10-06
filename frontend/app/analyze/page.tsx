'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AuthProvider } from '../../contexts/AuthContext'
import AnalyzeFlow from '../components/analyze/AnalyzeFlow'
import { getValidSessionAccessToken } from '../../lib/sessionToken'

function AnalyzeGuard() {
  const router = useRouter()
  const [state, setState] = useState<'checking' | 'ok'>('checking')

  useEffect(() => {
    getValidSessionAccessToken()
      .then((token) => {
        if (!token) router.replace('/')
        else setState('ok')
      })
      .catch(() => router.replace('/'))
  }, [router])

  if (state === 'checking') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
      </div>
    )
  }
  return <AnalyzeFlow />
}

export default function AnalyzePage() {
  return (
    <AuthProvider>
      <AnalyzeGuard />
    </AuthProvider>
  )
}
