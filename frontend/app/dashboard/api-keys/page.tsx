'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AuthProvider } from '../../../contexts/AuthContext'
import { getValidSessionAccessToken } from '../../../lib/sessionToken'
import ApiKeyList from '../../components/api-keys/ApiKeyList'
import { ArrowLeft } from 'lucide-react'

function ApiKeysGuard() {
  const router = useRouter()
  const [isAuthorized, setIsAuthorized] = useState(false)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    const authorize = async () => {
      const token = await getValidSessionAccessToken()
      if (!token) {
        setIsChecking(false)
        router.replace('/')
        return
      }
      setIsAuthorized(true)
      setIsChecking(false)
    }

    authorize().catch(() => {
      router.replace('/')
      setIsChecking(false)
    })
  }, [router])

  const getToken = useCallback(() => getValidSessionAccessToken(), [])

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
      </div>
    )
  }

  if (!isAuthorized) return null

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6 lg:px-8">
        <Link
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-black"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>
        <ApiKeyList getToken={getToken} />
      </div>
    </main>
  )
}

export default function ApiKeysPage() {
  return (
    <AuthProvider>
      <ApiKeysGuard />
    </AuthProvider>
  )
}
