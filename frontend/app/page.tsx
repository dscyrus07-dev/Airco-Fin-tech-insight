'use client'

import Image from 'next/image'
import { useState, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AuthProvider, useAuth } from '../contexts/AuthContext'
import { getValidSessionAccessToken } from '../lib/sessionToken'
import Header from './components/layout/Header'
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
  const [isSubmitting, setIsSubmitting] = useState(false)

  const mailtoHref = useMemo(() => {
    const subject = encodeURIComponent('Airco Insights Login Credentials')
    const body = encodeURIComponent(REQUEST_MESSAGE)
    return `mailto:Info@the-airco.com?subject=${subject}&body=${body}`
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
    <main className="min-h-screen bg-white text-black">
      <div className="relative isolate min-h-screen overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(0,0,0,0.06),_transparent_35%),linear-gradient(to_bottom,_#ffffff,_#f7f7f7)]" />

        <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-8 sm:px-8 lg:px-10">
          <div className="flex items-center justify-center pt-6 sm:pt-10">
            <div className="flex items-center gap-4 rounded-full border border-black/5 bg-white/90 px-6 py-3 shadow-[0_12px_40px_rgba(0,0,0,0.06)] backdrop-blur">
              <Image
                src="/logo.png"
                alt="Airco Insights"
                width={48}
                height={48}
                className="h-12 w-12 rounded-full object-cover"
                priority
                unoptimized
              />
              <div>
                <p className="text-base font-semibold tracking-tight sm:text-lg">Airco Insights</p>
                <p className="text-xs text-neutral-500">Secure access request</p>
              </div>
            </div>
          </div>

          <div className="flex flex-1 items-center justify-center py-10 sm:py-14">
            <div className="grid w-full max-w-6xl gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:gap-16">
              <section className="flex flex-col justify-center text-center lg:text-left px-4 lg:px-0">
                <h1 className="text-4xl font-bold tracking-tight text-black sm:text-5xl lg:text-6xl leading-tight">
                  Transform Bank Statements
                  <span className="block text-3xl font-semibold text-neutral-600 sm:text-4xl lg:text-5xl mt-2">into Financial Intelligence</span>
                </h1>
                <p className="mt-6 text-lg leading-relaxed text-neutral-600 sm:text-xl lg:max-w-xl">
                  Upload, analyze, and convert raw bank data into structured insights — instantly.
                </p>

                <div className="mt-8 space-y-4">
                  <div className="flex items-center gap-3 text-neutral-700">
                    <div className="h-2 w-2 rounded-full bg-black"></div>
                    <span className="text-base font-medium">Automated transaction categorization</span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-700">
                    <div className="h-2 w-2 rounded-full bg-black"></div>
                    <span className="text-base font-medium">Monthly summaries & spending insights</span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-700">
                    <div className="h-2 w-2 rounded-full bg-black"></div>
                    <span className="text-base font-medium">Recurring transaction detection</span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-700">
                    <div className="h-2 w-2 rounded-full bg-black"></div>
                    <span className="text-base font-medium">Multi-bank support (HDFC, ICICI, SBI & more)</span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-700">
                    <div className="h-2 w-2 rounded-full bg-black"></div>
                    <span className="text-base font-medium">Export-ready Excel reports</span>
                  </div>
                </div>

                <div className="mt-10 flex flex-wrap items-center gap-2 text-sm text-neutral-500">
                  <span className="font-medium">Privacy-first</span>
                  <span className="text-neutral-400">•</span>
                  <span className="font-medium">No data stored</span>
                  <span className="text-neutral-400">•</span>
                  <span className="font-medium">Real-time processing</span>
                </div>
              </section>

              <section className="flex items-center justify-center">
                <div className="w-full max-w-md rounded-2xl border border-black/10 bg-white/80 p-8 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.15)] backdrop-blur-sm sm:p-10">
                  <div className="mb-8">
                    <p className="text-center text-sm font-semibold uppercase tracking-[0.3em] text-neutral-500">
                      Airco Insights
                    </p>
                    <p className="mt-1 text-center text-lg font-medium text-black">
                      Sign In
                    </p>
                  </div>

                  <form onSubmit={handleLogin} className="space-y-4">
                    <p className="rounded-lg border border-black/10 bg-neutral-50 px-4 py-3 text-sm leading-6 text-neutral-600">
                      You will be redirected to our secure login page to enter your credentials.
                    </p>

                    <button
                      type="submit"
                      disabled={isSubmitting || isLoading}
                      className="mt-2 flex w-full items-center justify-center rounded-lg bg-black px-4 py-3 text-sm font-semibold text-white transition hover:bg-neutral-800 hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSubmitting ? 'Redirecting...' : 'Continue to Sign In'}
                    </button>
                  </form>

                  <div className="mt-6 space-y-3 border-t border-black/5 pt-6">
                    <a
                      href={mailtoHref}
                      className="block w-full text-center rounded-lg border border-black/10 bg-neutral-50 px-4 py-3 text-sm font-medium text-black transition hover:bg-neutral-100"
                    >
                      Request Access via Email
                    </a>
                    <a
                      href={whatsappHref}
                      className="block w-full text-center rounded-lg border border-black/10 bg-neutral-50 px-4 py-3 text-sm font-medium text-black transition hover:bg-neutral-100"
                    >
                      Request Access via WhatsApp
                    </a>
                  </div>

                  <div className="pt-4 text-center">
                    <p className="text-xs text-neutral-500">
                      Need help? Contact our support team
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <footer className="pb-4 text-center text-[11px] text-neutral-400 sm:pb-6">
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

