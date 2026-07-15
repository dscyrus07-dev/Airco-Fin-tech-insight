import { clearStoredTokens, getValidSessionAccessToken } from './sessionToken'

const KEYCLOAK_URL = process.env.NEXT_PUBLIC_KEYCLOAK_URL || 'http://localhost:8080'
const KEYCLOAK_REALM = process.env.NEXT_PUBLIC_KEYCLOAK_REALM || 'airco-insights'
const KEYCLOAK_CLIENT_ID = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || 'frontend-app'
const PKCE_VERIFIER_KEY = 'kc_pkce_code_verifier'

type TokenPayload = {
  sub?: string
  email?: string
  name?: string
  preferred_username?: string
  given_name?: string
  family_name?: string
  realm_access?: {
    roles?: string[]
  }
  exp?: number
}

export const keycloak: any = null

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

function base64UrlEncode(bytes: ArrayBuffer | Uint8Array): string {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  let binary = ''
  for (let i = 0; i < view.length; i += 1) {
    binary += String.fromCharCode(view[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function createCodeVerifier(): string {
  const random = new Uint8Array(32)
  crypto.getRandomValues(random)
  return base64UrlEncode(random)
}

async function createCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return base64UrlEncode(digest)
}

export function consumePkceCodeVerifier(): string | null {
  if (typeof window === 'undefined') return null
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY)
  sessionStorage.removeItem(PKCE_VERIFIER_KEY)
  return verifier
}

export const initKeycloak = async () => false

async function buildKeycloakLoginUrl() {
  if (typeof window === 'undefined') return ''

  const redirectUri = `${window.location.origin}/auth/callback`
  const codeVerifier = createCodeVerifier()
  const codeChallenge = await createCodeChallenge(codeVerifier)
  sessionStorage.setItem(PKCE_VERIFIER_KEY, codeVerifier)

  const url = new URL(`${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/auth`)
  url.searchParams.set('client_id', KEYCLOAK_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid profile email')
  url.searchParams.set('prompt', 'login')
  url.searchParams.set('code_challenge', codeChallenge)
  url.searchParams.set('code_challenge_method', 'S256')
  return url.toString()
}

export const getKeycloakLoginRedirectUri = () => {
  if (typeof window === 'undefined') return `${KEYCLOAK_URL}/auth/callback`
  return `${window.location.origin}/auth/callback`
}

export const login = async () => {
  if (typeof window === 'undefined') return

  const url = await buildKeycloakLoginUrl()
  if (url) {
    window.location.assign(url)
  }
}

export const logout = () => {
  clearStoredTokens()
  return Promise.resolve()
}

export const getToken = (): string | null => {
  if (typeof window === 'undefined') return null
  return sessionStorage.getItem('kc_token')
}

export const getRefreshToken = () => {
  if (typeof window === 'undefined') return null
  return sessionStorage.getItem('kc_refresh_token')
}

export const isTokenValid = () => {
  const token = getToken()
  if (!token) return false

  const payload = decodePayload(token)
  if (!payload?.exp) return false

  return payload.exp * 1000 > Date.now() + 60 * 1000
}

export const updateToken = async (_minValidity = 5) => {
  const token = await getValidSessionAccessToken()
  return !!token
}

export const getUserInfo = () => {
  const token = getToken()
  if (!token) return null

  const tokenData = decodePayload(token)
  if (!tokenData) return null

  return {
    id: tokenData.sub || '',
    email: tokenData.email || '',
    name: tokenData.name || tokenData.preferred_username || '',
    given_name: tokenData.given_name,
    family_name: tokenData.family_name,
    preferred_username: tokenData.preferred_username,
    roles: tokenData.realm_access?.roles || [],
  }
}

export const hasRole = (role: string) => {
  const token = getToken()
  if (!token) return false

  const tokenData = decodePayload(token)
  return tokenData?.realm_access?.roles?.includes(role) || false
}

export const isAuthenticated = () => {
  if (typeof window === 'undefined') return false
  return !!sessionStorage.getItem('kc_token')
}
