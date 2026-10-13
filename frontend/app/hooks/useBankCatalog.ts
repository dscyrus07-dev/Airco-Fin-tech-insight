'use client'

import { useEffect, useState } from 'react'
import { listBankCatalog, type BankCatalog } from '@/lib/statementsApi'
import { FALLBACK_BANK_LIST } from '@/lib/banks'
import { catalogFromBanks } from '@/lib/bankSupport'

let cache: Promise<BankCatalog> | null = null

function load(): Promise<BankCatalog> {
  if (!cache) {
    cache = listBankCatalog().catch(() => ({
      banks: FALLBACK_BANK_LIST.map((b) => ({ id: b.id, name: b.name as string })),
      all_banks: catalogFromBanks(FALLBACK_BANK_LIST.map((b) => ({ ...b, name: b.name as string, v2_served: false }))),
    }))
  }
  return cache
}

/**
 * Shared catalog for every bank UI surface: servable `banks` plus `all_banks`
 * with support states. One fetch per session; falls back to the shipped
 * default servable list when the API is unreachable.
 */
export function useBankCatalog(): BankCatalog {
  const [catalog, setCatalog] = useState<BankCatalog>({ banks: [], all_banks: [] })
  useEffect(() => {
    let cancelled = false
    load().then((c) => {
      if (!cancelled) setCatalog(c)
    })
    return () => {
      cancelled = true
    }
  }, [])
  return catalog
}
