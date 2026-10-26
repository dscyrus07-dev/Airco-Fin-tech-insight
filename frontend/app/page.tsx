'use client'

import Image from 'next/image'
import { useState, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AuthProvider, useAuth } from '../contexts/AuthContext'
import { getValidSessionAccessToken } from '../lib/sessionToken'
import Header, { useThemeMode } from './components/layout/Header'
import StepForm from './components/layout/StepForm'
import UploadStep from './components/upload/UploadStep'
import ModeSelection from './components/upload/ModeSelection'
import ProcessingStep from './components/processing/ProcessingStep'
import ResultStep from './components/results/ResultStep'
import {
  CheckCircle2,
  Clock3,
  Download,
  Edit3,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  Trash2,
  Upload,
  UserCircle2,
} from 'lucide-react'
import { UserDetails, ProcessingResult, ProcessingMode, Step } from '@/types'

const REQUEST_MESSAGE = `Hello Airco Insights Team,

I would like to request secure access to the Airco Insights platform.

Name:
Email:
Organization (if any):
Purpose of use:

Please provide further instructions to proceed.

Thank you.`

function LoginScreen() {
  const router = useRouter()
  const { isLoading, login: startLogin } = useAuth()
  const { dark, toggle: toggleTheme } = useThemeMode()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [bankCount, setBankCount] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/upload/supported-banks')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.count) setBankCount(data.count)
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  const mailtoHref = useMemo(() => {
    const subject = encodeURIComponent('Airco Insights Login Credentials')
    const body = encodeURIComponent(REQUEST_MESSAGE)
    return `mailto:info@the-airco.com?subject=${subject}&body=${body}`
  }, [])

  const whatsappHref = useMemo(() => {
    const text = encodeURIComponent(REQUEST_MESSAGE)
    return `https://wa.me/918355903494?text=${text}`
  }, [])

  useEffect(() => {
    const redirectIfAuthenticated = async () => {
      const token = await getValidSessionAccessToken()
      if (token) {
        router.replace('/dashboard')
      }
    }

    redirectIfAuthenticated().catch(() => {})
  }, [router])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      await startLogin()
    } catch {
      // The browser redirect should normally take over immediately.
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="bg-app min-h-screen text-slate-900 dark:text-slate-100">
      <div className="relative isolate min-h-screen overflow-hidden">
        <div className="relative mx-auto flex min-h-screen w-full flex-col px-6 py-8 sm:px-8 lg:px-14">
          <div className="flex items-center justify-between pt-2 sm:pt-4">
            <div className="flex items-center gap-4 rounded-2xl border border-[#A1B2CE]/40 bg-white/90 px-5 py-2.5 shadow-sm backdrop-blur dark:border-slate-700/80 dark:bg-[#0B1B36]/90">
              <Image
                src={dark ? '/logo-wordmark-dark.png' : '/logo-wordmark-light.png'}
                alt="Airco Insights"
                width={140}
                height={44}
                className="h-10 w-auto object-contain"
                priority
                unoptimized
              />
              <span className="h-7 w-px bg-slate-200 dark:bg-slate-700" aria-hidden="true" />
              <div>
                <p className="text-base font-bold tracking-tight text-[#01275C] dark:text-white sm:text-lg">Airco Insights</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Secure access request</p>
              </div>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded-full border border-slate-200 bg-white/90 px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-[#01275C]/40 dark:border-slate-700 dark:bg-[#0B1B36] dark:text-slate-200"
            >
              {dark ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>

          <div className="flex flex-1 items-center justify-center py-10 sm:py-14">
            <div className="grid w-full max-w-7xl gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:gap-16">
              <section className="flex flex-col justify-center text-center lg:text-left px-4 lg:px-0">
                <h1 className="text-4xl font-bold tracking-tight text-[#01275C] dark:text-white sm:text-5xl lg:text-6xl leading-tight">
                  Transform Bank Statements
                  <span className="block text-3xl font-semibold text-slate-600 dark:text-slate-300 sm:text-4xl lg:text-5xl mt-2">into Financial Intelligence</span>
                </h1>
                <p className="mt-6 text-lg leading-relaxed text-slate-600 dark:text-slate-300 sm:text-xl lg:max-w-xl">
                  Upload, analyze, and convert raw bank data into structured insights — instantly.
                </p>

                <div className="mt-8 space-y-4">
                  <div className="flex items-center gap-3 text-slate-700 dark:text-slate-200">
                    <div className="h-2 w-2 rounded-full bg-[#01275C] dark:bg-blue-400"></div>
                    <span className="text-base font-medium">Automated transaction categorization</span>
                  </div>
                  <div className="flex items-center gap-3 text-slate-700 dark:text-slate-200">
                    <div className="h-2 w-2 rounded-full bg-[#01275C] dark:bg-blue-400"></div>
                    <span className="text-base font-medium">Monthly summaries & spending insights</span>
                  </div>
                  <div className="flex items-center gap-3 text-slate-700 dark:text-slate-200">
                    <div className="h-2 w-2 rounded-full bg-[#01275C] dark:bg-blue-400"></div>
                    <span className="text-base font-medium">Recurring transaction detection</span>
                  </div>
                  <div className="flex items-center gap-3 text-slate-700 dark:text-slate-200">
                    <div className="h-2 w-2 rounded-full bg-[#01275C] dark:bg-blue-400"></div>
                    <span className="text-base font-medium">
                      Multi-bank support{bankCount ? ` (${bankCount} banks and more)` : ''}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-slate-700 dark:text-slate-200">
                    <div className="h-2 w-2 rounded-full bg-[#01275C] dark:bg-blue-400"></div>
                    <span className="text-base font-medium">Export-ready Excel reports</span>
                  </div>
                </div>

                <div className="mt-10 flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                  <span className="font-medium">Privacy-first</span>
                  <span className="text-slate-400">•</span>
                  <span className="font-medium">7-day auto-deletion</span>
                  <span className="text-slate-400">•</span>
                  <span className="font-medium">Real-time processing</span>
                </div>
              </section>

              <section className="flex items-center justify-center">
                <div className="card-surface w-full max-w-md p-8 sm:p-10">
                  <div className="mb-8 flex flex-col items-center">
                    <Image
                      src={dark ? '/logo-circle-dark.png' : '/logo-circle-light.png'}
                      alt="AiRCo Emblem"
                      width={64}
                      height={64}
                      className="mb-3 h-16 w-16 rounded-full shadow-sm"
                      unoptimized
                    />
                    <p className="text-center text-xs font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
                      Airco Insights
                    </p>
                    <p className="mt-1 text-center text-xl font-bold text-[#01275C] dark:text-white">
                      Sign In
                    </p>
                  </div>

                  <form onSubmit={handleLogin} className="space-y-4">
                    <p className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm leading-6 text-slate-600 dark:border-slate-700/80 dark:bg-slate-800/50 dark:text-slate-300">
                      You will be redirected to our secure login page to enter your credentials.
                    </p>

                    <button
                      type="submit"
                      disabled={isSubmitting || isLoading}
                      className="btn-primary mt-2 flex w-full items-center justify-center rounded-xl px-4 py-3 text-sm font-semibold text-white transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSubmitting ? 'Redirecting...' : 'Continue to Sign In'}
                    </button>
                  </form>

                  <div className="mt-6 space-y-3 border-t border-slate-200/80 pt-6 dark:border-slate-700/80">
                    <a
                      href={mailtoHref}
                      className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-medium text-slate-800 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      Request Access via Email
                    </a>
                    <a
                      href={whatsappHref}
                      className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-medium text-slate-800 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      Request Access via WhatsApp
                    </a>
                  </div>

                  <div className="pt-4 text-center">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Need help? Contact our support team
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <footer className="pb-4 text-center text-[11px] text-slate-400 sm:pb-6">
            Airco Insights — Secure access
          </footer>
        </div>
      </div>
    </main>
  )
}

export default function Page() {
  return (
    <AuthProvider>
      <LoginScreen />
    </AuthProvider>
  )
}

