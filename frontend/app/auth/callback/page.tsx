'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { storeSessionTokens } from '../../../lib/sessionToken'
import { consumePkceCodeVerifier, getKeycloakLoginRedirectUri } from '../../../lib/keycloak'

export default function AuthCallbackPage() {
  const router = useRouter()
  const [status, setStatus] = useState('Completing sign-in...')
  const [error, setError] = useState('')

  useEffect(() => {
    const exchangeCode = async () => {
      const query = new URLSearchParams(window.location.search)
      const code = query.get('code')
      const errorParam = query.get('error')
      const errorDescription = query.get('error_description')

      if (errorParam) {
        setError(errorDescription || errorParam || 'Keycloak sign-in failed.')
        setStatus('Sign-in failed')
        return
      }

      if (!code) {
        setError('Missing authorization code from Keycloak.')
        setStatus('Sign-in failed')
        return
      }

      try {
        setStatus('Exchanging authorization code...')
        const redirectUri = getKeycloakLoginRedirectUri()
        const codeVerifier = consumePkceCodeVerifier()
        if (!codeVerifier) {
          throw new Error('Missing PKCE code verifier. Please start login again from the home page.')
        }
        const response = await fetch('/api/auth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code,
            redirect_uri: redirectUri,
            code_verifier: codeVerifier,
          }),
        })

        const data = await response.json().catch(() => null)
        if (!response.ok) {
          throw new Error(data?.message || data?.detail || 'Authorization code exchange failed.')
        }

        if (!data?.access_token) {
          throw new Error('Keycloak did not return an access token.')
        }

        storeSessionTokens(data.access_token, data.refresh_token)
        setStatus('Sign-in complete')
        router.replace('/dashboard')
      } catch (exchangeError) {
        const message = exchangeError instanceof Error ? exchangeError.message : 'Sign-in failed.'
        setError(message)
        setStatus('Sign-in failed')
      }
    }

    exchangeCode().catch(() => {
      setError('Unable to complete sign-in.')
      setStatus('Sign-in failed')
    })
  }, [router])

  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-6 text-black">
      <div className="w-full max-w-md rounded-2xl border border-black/10 bg-white p-8 text-center shadow-[0_25px_50px_-12px_rgba(0,0,0,0.15)]">
        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-black border-t-transparent" />
        <h1 className="text-2xl font-semibold tracking-tight">{status}</h1>
        <p className="mt-3 text-sm leading-6 text-neutral-600">
          Keycloak is handling your password and TOTP verification.
        </p>
        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </main>
  )
}
