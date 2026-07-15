'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AuthProvider } from '../../contexts/AuthContext'
import Dashboard from '../components/Dashboard'
import { getValidSessionAccessToken } from '../../lib/sessionToken'

function DashboardGuard() {
  const router = useRouter()
  const [isAuthorized, setIsAuthorized] = useState(false)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    const authorize = async () => {
      const token = await getValidSessionAccessToken()
      console.log('Dashboard guard - token check:', token ? 'found' : 'not found')
      if (!token) {
        console.log('Dashboard guard - no valid session, redirecting to login')
        setIsChecking(false)
        router.replace('/')
        return
      }

      console.log('Dashboard guard - valid session found, authorizing')
      setIsAuthorized(true)
      setIsChecking(false)
    }

    authorize().catch(() => {
      console.log('Dashboard guard - authorization failed, redirecting to login')
      router.replace('/')
      setIsChecking(false)
    })
  }, [router])

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
      </div>
    )
  }

  if (!isAuthorized) return null

  return <Dashboard />
}

export default function DashboardPage() {
  return (
    <AuthProvider>
      <DashboardGuard />
    </AuthProvider>
  )
}
