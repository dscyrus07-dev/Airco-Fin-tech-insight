import type { BankCatalogEntry, SupportState } from './statementsApi'

/**
 * Support-state grouping shared by the bank pickers, the supported-banks
 * panel and the result notice. Single source of wording + order so every
 * surface stays honest and consistent.
 */

export const STATE_ORDER: SupportState[] = ['verified', 'review_required', 'legacy', 'coming_soon', 'unsupported']

export const STATE_LABEL: Record<SupportState, string> = {
  verified: 'Verified',
  review_required: 'Review required',
  legacy: 'Legacy parser',
  coming_soon: 'Coming soon',
  unsupported: 'Not supported',
}

/** Colour is never the only signal: every state also has a text marker. */
export const STATE_ICON: Record<SupportState, string> = {
  verified: '✓',
  review_required: '⚠',
  legacy: '◦',
  coming_soon: '◷',
  unsupported: '✕',
}

export const STATE_TAG: Record<SupportState, string> = {
  verified: 'verified engine',
  review_required: 'always needs review',
  legacy: 'standard parser',
  coming_soon: 'coming soon',
  unsupported: 'not supported',
}

/** Only servable states are selectable anywhere. */
export const SELECTABLE_STATES: ReadonlySet<SupportState> = new Set(['verified', 'review_required', 'legacy'])

export const isSelectable = (s?: SupportState | null): boolean => !!s && SELECTABLE_STATES.has(s)

/** A list longer than this shows a search box. */
export const SEARCH_THRESHOLD = 12

export interface BankGroup {
  state: SupportState
  label: string
  banks: BankCatalogEntry[]
}

/** Group a catalog by state in display order; empty groups are dropped. */
export function groupByState(catalog: BankCatalogEntry[]): BankGroup[] {
  return STATE_ORDER
    .map((state) => ({ state, label: STATE_LABEL[state], banks: catalog.filter((b) => b.support_state === state) }))
    .filter((g) => g.banks.length > 0)
}

export function findCatalogEntry(catalog: BankCatalogEntry[], bankId: string | null | undefined): BankCatalogEntry | undefined {
  return bankId ? catalog.find((b) => b.id === bankId) : undefined
}

/** Fallback when an older backend returns no all_banks: servable list only, states from the entries themselves. */
export function catalogFromBanks(banks: { id: string; name: string; support_state?: SupportState | null; v2_served?: boolean }[]): BankCatalogEntry[] {
  return banks.map((b) => ({
    id: b.id,
    name: b.name,
    support_state: b.support_state ?? (b.v2_served ? 'verified' : 'legacy'),
  }))
}
