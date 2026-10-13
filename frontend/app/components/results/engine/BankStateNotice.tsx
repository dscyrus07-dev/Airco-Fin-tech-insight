'use client'

import type { BankCatalogEntry } from '@/lib/statementsApi'
import { findCatalogEntry } from '@/lib/bankSupport'

/**
 * Persistent "needs review" notice for review-ceiling banks: these banks can
 * never produce a VERIFIED result, so the notice must be visible without
 * expanding anything — next to the badge, not inside it.
 * Returns null for any other state (the badge already carries those signals).
 */
export default function BankStateNotice({
  catalog,
  bankKey,
}: {
  catalog: BankCatalogEntry[]
  bankKey: string | null | undefined
}) {
  const entry = findCatalogEntry(catalog, bankKey)
  if (!entry || entry.support_state !== 'review_required') return null
  return (
    <div
      role="status"
      className="mt-2 w-full max-w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-left"
    >
      <p className="text-[11px] font-medium text-amber-900">
        {entry.name} reports always need review
        {entry.reason ? <span className="font-normal text-amber-800"> — {entry.reason}</span> : null}
      </p>
    </div>
  )
}
