'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { ProcessingMode, ProcessingResult } from '@/types'

const FREE_MESSAGES = [
  'Extracting transactions...',
  'Detecting bank format...',
  'Running rule engine...',
  'Categorizing transactions...',
  'Detecting recurring patterns...',
  'Generating structured report...',
]

const HYBRID_MESSAGES = [
  'Extracting transactions...',
  'Detecting bank format...',
  'Running rule engine...',
  'Classifying with AI...',
  'Validating AI categories...',
  'Detecting recurring patterns...',
  'Generating structured report...',
]

interface ProcessingStepProps {
  jobId: string
  mode?: ProcessingMode
  onComplete: (result: ProcessingResult) => void
  onError: (message: string) => void
}

export default function ProcessingStep({
  jobId,
  mode = 'free',
  onComplete,
  onError,
}: ProcessingStepProps) {
  const [messageIndex, setMessageIndex] = useState(0)
  const [pollError, setPollError] = useState('')
  const messages = mode === 'hybrid' ? HYBRID_MESSAGES : FREE_MESSAGES

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length)
    }, 2500)
    return () => clearInterval(interval)
  }, [messages.length])

  useEffect(() => {
    if (!jobId) return

    let cancelled = false

    const poll = async () => {
      try {
        const token = sessionStorage.getItem('kc_token')
        const response = await fetch(`/api/jobs/${jobId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        })
        const data = await response.json().catch(() => ({}))

        if (!response.ok) {
          throw new Error(data.message || 'Failed to fetch job status.')
        }

        const status = String(data.status || '').toLowerCase()
        if (status === 'completed' && data.result_data) {
          if (!cancelled) onComplete(data.result_data as ProcessingResult)
          return
        }

        if (status === 'failed' || status === 'cancelled') {
          throw new Error(data.error_message || 'Processing failed.')
        }

        if (!cancelled) {
          setTimeout(poll, 2000)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Processing failed.'
        if (!cancelled) {
          setPollError(message)
          onError(message)
        }
      }
    }

    poll()

    return () => {
      cancelled = true
    }
  }, [jobId, onComplete, onError])

  return (
    <div className="animate-fade-in flex flex-col items-center justify-center py-16">
      <Loader2 className="w-10 h-10 text-black animate-spin mb-6" />
      <p className="text-sm font-medium text-black animate-pulse-text">
        {messages[messageIndex]}
      </p>
      <p className="text-xs text-neutral-400 mt-3">
        This may take a moment depending on the number and size of uploaded statements.
      </p>
      <div className="mt-4 px-3 py-1 bg-neutral-50 border border-neutral-200 rounded-full">
        <span className="text-[10px] text-neutral-500 font-medium">
          {mode === 'hybrid' ? 'System + AI Mode' : 'Free Mode (System Only)'}
        </span>
      </div>
      <p className="text-[10px] text-neutral-300 mt-3 font-mono">
        job: {jobId.slice(0, 16)}...
      </p>
      {pollError && (
        <p className="text-xs text-red-600 mt-3">{pollError}</p>
      )}
    </div>
  )
}
