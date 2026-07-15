'use client'

type TokenPayload = {
  exp?: number
  sub?: string
  email?: string
  name?: string
  preferred_username?: string
  given_name?: string
  family_name?: string
  realm_access?: {
    roles?: string[]
  }
}

function decodePayload(token: string): TokenPayload | null {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null

    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

export function buildUserHeadersFromToken(token: string): Record<string, string> {
  const payload = decodePayload(token)
  if (!payload?.sub) return {}

  const headers: Record<string, string> = {
    'X-Airco-User-Id': payload.sub,
  }

  if (payload.email) headers['X-Airco-User-Email'] = payload.email
  if (payload.name || payload.preferred_username) {
    headers['X-Airco-User-Name'] = payload.name || payload.preferred_username || ''
  }
  if (payload.preferred_username) {
    headers['X-Airco-Preferred-Username'] = payload.preferred_username
  }
  if (payload.given_name) headers['X-Airco-Given-Name'] = payload.given_name
  if (payload.family_name) headers['X-Airco-Family-Name'] = payload.family_name

  return headers
}

function isTokenFresh(token: string, minSeconds = 60): boolean {
  const payload = decodePayload(token)
  if (!payload?.exp) return false
  return payload.exp * 1000 > Date.now() + minSeconds * 1000
}

export function clearStoredTokens() {
  if (typeof window === 'undefined') return
  sessionStorage.removeItem('kc_token')
  sessionStorage.removeItem('kc_refresh_token')
  document.cookie = 'kc_token=; Path=/; Max-Age=0; SameSite=Lax'
  document.cookie = 'kc_refresh_token=; Path=/; Max-Age=0; SameSite=Lax'
  document.cookie = 'kc_user_id=; Path=/; Max-Age=0; SameSite=Lax'
  document.cookie = 'kc_user_email=; Path=/; Max-Age=0; SameSite=Lax'
  document.cookie = 'kc_user_name=; Path=/; Max-Age=0; SameSite=Lax'
  document.cookie = 'kc_preferred_username=; Path=/; Max-Age=0; SameSite=Lax'
}

export function storeSessionTokens(accessToken: string, refreshToken?: string | null) {
  if (typeof window === 'undefined') return
  console.log('Storing access token in sessionStorage')
  sessionStorage.setItem('kc_token', accessToken)
  document.cookie = `kc_token=${encodeURIComponent(accessToken)}; Path=/; SameSite=Lax`
  console.log('Token stored, checking if it exists:', sessionStorage.getItem('kc_token') ? 'yes' : 'no')

  const payload = decodePayload(accessToken)
  if (payload?.sub) {
    document.cookie = `kc_user_id=${encodeURIComponent(payload.sub)}; Path=/; SameSite=Lax`
  }
  if (payload?.email) {
    document.cookie = `kc_user_email=${encodeURIComponent(payload.email)}; Path=/; SameSite=Lax`
  }
  const userName = payload?.name || payload?.preferred_username
  if (userName) {
    document.cookie = `kc_user_name=${encodeURIComponent(userName)}; Path=/; SameSite=Lax`
  }
  if (payload?.preferred_username) {
    document.cookie = `kc_preferred_username=${encodeURIComponent(payload.preferred_username)}; Path=/; SameSite=Lax`
  }

  if (refreshToken) {
    sessionStorage.setItem('kc_refresh_token', refreshToken)
    document.cookie = `kc_refresh_token=${encodeURIComponent(refreshToken)}; Path=/; SameSite=Lax`
  }
}

export async function getValidSessionAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null

  const accessToken = sessionStorage.getItem('kc_token')
  if (accessToken && isTokenFresh(accessToken)) {
    return accessToken
  }

  const refreshToken = sessionStorage.getItem('kc_refresh_token')
  if (!refreshToken) {
    return accessToken
  }

  try {
    const resp = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!resp.ok) {
      clearStoredTokens()
      return null
    }

    const data = await resp.json()
    if (data.access_token) {
      storeSessionTokens(data.access_token, data.refresh_token)
    }

    return data.access_token || null
  } catch {
    return accessToken
  }
}
