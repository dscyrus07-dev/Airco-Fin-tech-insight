'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { keycloak, login, logout, getToken, isTokenValid, updateToken, hasRole, isAuthenticated } from '../lib/keycloak'
import { clearStoredTokens, getValidSessionAccessToken } from '../lib/sessionToken'

export interface User {
  id: string
  email: string
  name: string
  given_name?: string
  family_name?: string
  preferred_username?: string
  roles: string[]
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  keycloak: typeof keycloak
  login: () => Promise<void>
  logout: () => Promise<void>
  hasRole: (role: string) => boolean
  getAccessToken: () => Promise<string | null>
  refreshToken: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const parseStoredTokenUser = (): User | null => {
  if (typeof window === 'undefined') return null
  const token = sessionStorage.getItem('kc_token')
  if (!token) return null

  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const decoded = JSON.parse(atob(padded))

    return {
      id: decoded.sub || '',
      email: decoded.email || '',
      name: decoded.name || decoded.preferred_username || '',
      given_name: decoded.given_name,
      family_name: decoded.family_name,
      preferred_username: decoded.preferred_username,
      roles: decoded.realm_access?.roles || [],
    }
  } catch (error) {
    console.error('Failed to parse stored token:', error)
    return null
  }
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [keycloakInstance, setKeycloakInstance] = useState(keycloak)

  useEffect(() => {
    const initializeKeycloak = async () => {
      try {
        // For custom login flow, skip Keycloak initialization and just check stored tokens
        // const authenticated = await initKeycloak()
        setIsLoading(false)
        
        const storedUser = parseStoredTokenUser()
        if (storedUser) {
          setUser(storedUser)
        }
      } catch (error) {
        console.error('Keycloak initialization error:', error)
        const storedUser = parseStoredTokenUser()
        if (storedUser) {
          setUser(storedUser)
        }
        setIsLoading(false)
      }
    }

    initializeKeycloak()

    // Set up token refresh interval
    const tokenRefreshInterval = setInterval(async () => {
      if (isAuthenticated()) {
        try {
          await updateToken(70) // Refresh if less than 70 seconds validity
        } catch (error) {
          console.error('Token refresh error:', error)
          await logout()
        }
      }
    }, 60000) // Check every minute

    return () => clearInterval(tokenRefreshInterval)
  }, [])

  // Listen to token events (disabled for custom login flow)
  useEffect(() => {
    // Token event listeners disabled to prevent conflicts with custom login
    return () => {}
  }, [])

  const handleLogin = async () => {
    await login()
  }

  const handleLogout = async () => {
    clearStoredTokens()
    await logout()
    setUser(null)

    if (typeof window !== 'undefined' && window.location.pathname !== '/') {
      window.location.replace('/')
    }
  }

  const handleHasRole = (role: string): boolean => {
    return hasRole(role)
  }

  const handleGetAccessToken = async (): Promise<string | null> => {
    if (!isAuthenticated()) {
      return getValidSessionAccessToken()
    }
    if (!isTokenValid()) {
      try {
        await updateToken(5)
      } catch (error) {
        console.error('Failed to refresh token:', error)
        await handleLogout()
        return null
      }
    }
    return getToken()
  }

  const handleRefreshToken = async (): Promise<boolean> => {
    try {
      return await updateToken(5)
    } catch (error) {
      console.error('Failed to refresh token:', error)
      await handleLogout()
      return false
    }
  }

  const value: AuthContextType = {
    user,
    isAuthenticated: isAuthenticated(),
    isLoading,
    keycloak: keycloakInstance,
    login: handleLogin,
    logout: handleLogout,
    hasRole: handleHasRole,
    getAccessToken: handleGetAccessToken,
    refreshToken: handleRefreshToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
