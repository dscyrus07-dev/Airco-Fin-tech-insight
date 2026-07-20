'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { KeyRound, Plus, Trash2 } from 'lucide-react'
import CreateKeyModal from './CreateKeyModal'

export type ApiKeyRow = {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  environment: string
  is_active: boolean
  last_used_at: string | null
  usage_count: number
  processed_pdf_count: number
  created_at: string | null
  revoked_at: string | null
}

type ApiKeyListProps = {
  getToken: () => Promise<string | null>
}

export default function ApiKeyList({ getToken }: ApiKeyListProps) {
  const [keys, setKeys] = useState<ApiKeyRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const loadKeys = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) {
        setError('Not authenticated')
        setKeys([])
        return
      }
      const response = await fetch('/api/api-keys', {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) {
        setError(data?.detail || data?.message || 'Failed to load keys')
        setKeys([])
        return
      }
      setKeys(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load keys')
      setKeys([])
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => {
    void loadKeys()
  }, [loadKeys])

  const newestActivePrefix = useMemo(() => {
    const active = keys.find((k) => k.is_active)
    return active?.key_prefix || 'airco_sk_test_…'
  }, [keys])

  const handleRevoke = async (key: ApiKeyRow) => {
    const confirmed = window.confirm(
      `Revoke "${key.name}" (${key.key_prefix}…)? This cannot be undone.`,
    )
    if (!confirmed) return
    try {
      const token = await getToken()
      if (!token) return
      const response = await fetch(`/api/api-keys/${encodeURIComponent(key.id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        alert(data?.detail || data?.message || 'Failed to revoke key')
        return
      }
      await loadKeys()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to revoke key')
    }
  }

  const formatDate = (value: string | null) => {
    if (!value) return '—'
    try {
      return new Date(value).toLocaleString()
    } catch {
      return value
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-black">API Keys</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Create and manage keys for partner integrations (X-API-Key).
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          <Plus className="h-4 w-4" />
          Create Key
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
        </div>
      ) : keys.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-200 px-6 py-16 text-center">
          <KeyRound className="mx-auto h-10 w-10 text-neutral-300" />
          <p className="mt-3 text-sm font-medium text-neutral-700">No API keys yet</p>
          <p className="mt-1 text-xs text-neutral-400">Create your first key to start integrating.</p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="mt-4 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white"
          >
            Create your first API key
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-neutral-200">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-neutral-100 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Prefix</th>
                <th className="px-4 py-3 font-medium">Env</th>
                <th className="px-4 py-3 font-medium">Scopes</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Last used</th>
                <th className="px-4 py-3 font-medium">PDFs</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-neutral-50 last:border-0">
                  <td className="px-4 py-3 font-medium text-black">{key.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-600">
                    {key.key_prefix}…
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        key.environment === 'live'
                          ? 'border-green-200 bg-green-50 text-green-700'
                          : 'border-amber-200 bg-amber-50 text-amber-700'
                      }`}
                    >
                      {key.environment}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(key.scopes || []).map((scope) => (
                        <span
                          key={scope}
                          className="rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] text-neutral-600"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs font-medium ${
                        key.is_active ? 'text-green-700' : 'text-red-600'
                      }`}
                    >
                      {key.is_active ? 'Active' : 'Revoked'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-500">{formatDate(key.created_at)}</td>
                  <td className="px-4 py-3 text-xs text-neutral-500">
                    {formatDate(key.last_used_at)}
                  </td>
                  <td className="px-4 py-3 text-xs font-medium text-neutral-800">
                    {key.processed_pdf_count ?? 0}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {key.is_active && (
                      <button
                        type="button"
                        onClick={() => handleRevoke(key)}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4">
        <p className="text-sm font-medium text-black">Quick start</p>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-neutral-600">{`# Upload
curl -X POST "https://your-domain/api/v1/statements" \\
  -H "X-API-Key: ${newestActivePrefix}YOUR_SECRET" \\
  -F "file=@statement.pdf" -F "bank_name=HDFC" -F "mode=free"

# Poll
curl "https://your-domain/api/v1/jobs/JOB_ID" \\
  -H "X-API-Key: ${newestActivePrefix}YOUR_SECRET"

# Download
curl -L "https://your-domain/api/v1/jobs/JOB_ID/download" \\
  -H "X-API-Key: ${newestActivePrefix}YOUR_SECRET" -o report.xlsx`}</pre>
      </div>

      <CreateKeyModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => void loadKeys()}
        getToken={getToken}
      />
    </div>
  )
}
