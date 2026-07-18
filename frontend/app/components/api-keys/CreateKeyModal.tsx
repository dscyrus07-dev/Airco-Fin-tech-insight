'use client'

import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

const SCOPE_OPTIONS = [
  { id: 'upload', label: 'Upload' },
  { id: 'jobs:read', label: 'Jobs: Read' },
  { id: 'download', label: 'Download' },
  { id: 'jobs:delete', label: 'Jobs: Delete' },
] as const

const DEFAULT_SCOPES = ['upload', 'jobs:read', 'download']

type CreateKeyModalProps = {
  open: boolean
  onClose: () => void
  onCreated: () => void
  getToken: () => Promise<string | null>
}

export default function CreateKeyModal({ open, onClose, onCreated, getToken }: CreateKeyModalProps) {
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>([...DEFAULT_SCOPES])
  const [environment, setEnvironment] = useState<'test' | 'live'>('test')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fullKey, setFullKey] = useState<string | null>(null)
  const [savedConfirm, setSavedConfirm] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!open) return null

  const reset = () => {
    setName('')
    setScopes([...DEFAULT_SCOPES])
    setEnvironment('test')
    setLoading(false)
    setError(null)
    setFullKey(null)
    setSavedConfirm(false)
    setCopied(false)
  }

  const handleClose = () => {
    if (fullKey && !savedConfirm) return
    reset()
    onClose()
  }

  const toggleScope = (scope: string) => {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    )
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (scopes.length === 0) {
      setError('Select at least one scope')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) {
        setError('Not authenticated')
        return
      }
      const response = await fetch('/api/api-keys', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name.trim(),
          scopes,
          environment,
        }),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) {
        setError(data?.detail || data?.message || 'Failed to create key')
        return
      }
      setFullKey(data.full_key)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create key')
    } finally {
      setLoading(false)
    }
  }

  const copyKey = async () => {
    if (!fullKey) return
    await navigator.clipboard.writeText(fullKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-neutral-200 bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-black">
          {fullKey ? 'Save your API key' : 'Create New API Key'}
        </h2>

        {!fullKey ? (
          <div className="mt-4 space-y-4">
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Partner X integration"
                className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-black"
              />
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Scopes</p>
              <div className="mt-2 flex flex-wrap gap-3">
                {SCOPE_OPTIONS.map((opt) => (
                  <label key={opt.id} className="flex items-center gap-2 text-sm text-neutral-700">
                    <input
                      type="checkbox"
                      checked={scopes.includes(opt.id)}
                      onChange={() => toggleScope(opt.id)}
                      className="h-4 w-4 rounded border-neutral-300"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                Environment
              </p>
              <div className="mt-2 flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="env"
                    checked={environment === 'test'}
                    onChange={() => setEnvironment('test')}
                  />
                  Test
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="env"
                    checked={environment === 'live'}
                    onChange={() => setEnvironment('live')}
                  />
                  Live
                </label>
              </div>
              <p className="mt-1 text-xs text-neutral-400">
                Defaults to Test. Live keys only work against production.
              </p>
            </div>

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg border border-neutral-200 px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={handleCreate}
                className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
              >
                {loading ? 'Creating…' : 'Create Key'}
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
              Save this key now — you will not see it again. If you lose it, revoke it and create a
              new one.
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-3">
              <code className="flex-1 break-all font-mono text-xs text-black">{fullKey}</code>
              <button
                type="button"
                onClick={copyKey}
                className="shrink-0 rounded-md border border-neutral-200 bg-white p-2 text-neutral-600 hover:text-black"
                title="Copy"
              >
                {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
            <label className="flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={savedConfirm}
                onChange={(e) => setSavedConfirm(e.target.checked)}
                className="h-4 w-4 rounded border-neutral-300"
              />
              I&apos;ve saved this key safely
            </label>
            <div className="flex justify-end">
              <button
                type="button"
                disabled={!savedConfirm}
                onClick={handleClose}
                className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
