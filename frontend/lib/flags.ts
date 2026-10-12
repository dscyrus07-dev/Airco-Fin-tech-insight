'use client'

/** Client feature flags (build-time env). Default off everywhere. */
export function unifiedEntry(): boolean {
  const v = process.env.NEXT_PUBLIC_UNIFIED_ENTRY
  return v === 'on' || v === '1' || v === 'true'
}
