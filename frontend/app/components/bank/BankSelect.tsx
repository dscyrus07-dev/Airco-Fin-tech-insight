'use client'

import { useMemo, useState } from 'react'
import type { BankCatalogEntry } from '@/lib/statementsApi'
import { SEARCH_THRESHOLD, STATE_TAG, groupByState, isSelectable } from '@/lib/bankSupport'

interface BankSelectProps {
  /** Full catalog (all support states) or a servable-only list. */
  catalog: BankCatalogEntry[]
  value: string
  onChange: (bankId: string) => void
  ariaLabel?: string
  placeholder?: string
  showPlaceholder?: boolean
  /** When false, only selectable (servable) banks are listed. */
  showNonSelectable?: boolean
  className?: string
}

/**
 * Grouped bank dropdown: states get plain headings (optgroup labels), banks that
 * are coming soon / unsupported stay visible but disabled with a one-line
 * explanation. A search field filters the list when it exceeds 12 entries.
 * Native select: keyboard navigation and screen-reader announcements for free;
 * colour is never the only signal (text tags on every non-verified option).
 */
export default function BankSelect({
  catalog,
  value,
  onChange,
  ariaLabel = 'Bank',
  placeholder = 'Select bank…',
  showPlaceholder = false,
  showNonSelectable = true,
  className = 'min-w-0 rounded border px-2 py-1 text-sm',
}: BankSelectProps) {
  const [query, setQuery] = useState('')

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = q ? catalog.filter((b) => b.name.toLowerCase().includes(q)) : catalog
    const visible = showNonSelectable ? filtered : filtered.filter((b) => isSelectable(b.support_state))
    return groupByState(visible)
  }, [catalog, query, showNonSelectable])

  const total = catalog.length

  return (
    <div className="min-w-0">
      {total > SEARCH_THRESHOLD && (
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter banks…"
          aria-label="Filter banks"
          className="mb-1 w-full min-w-0 rounded border px-2 py-1 text-xs"
        />
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full ${className}`}
        aria-label={ariaLabel}
      >
        {showPlaceholder && <option value="">{placeholder}</option>}
        {groups.map((g) => (
          <optgroup key={g.state} label={g.label}>
            {g.banks.map((b) => {
              const selectable = isSelectable(b.support_state)
              const tag = STATE_TAG[b.support_state]
              return (
                <option key={b.id} value={b.id} disabled={!selectable}>
                  {b.name}
                  {tag ? ` · ${tag}` : ''}
                </option>
              )
            })}
          </optgroup>
        ))}
      </select>
    </div>
  )
}
