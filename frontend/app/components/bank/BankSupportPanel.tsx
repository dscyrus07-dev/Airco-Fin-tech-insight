'use client'

import type { BankCatalogEntry, OcrCatalog } from '@/lib/statementsApi'
import { STATE_ICON, STATE_LABEL, groupByState, isSelectable } from '@/lib/bankSupport'

/**
 * "Supported banks" panel: counts and names come from the API catalog, never
 * hard-coded. Servable banks are listed plainly; coming-soon and unsupported
 * banks are greyed with their one-line reason. Colour is never the only
 * signal — every row carries an icon plus a text tag.
 */
export default function BankSupportPanel({ catalog, ocr }: { catalog: BankCatalogEntry[]; ocr?: OcrCatalog | null }) {
  const groups = groupByState(catalog)
  if (!groups.length) return null
  const servable = catalog.filter((b) => isSelectable(b.support_state))

  return (
    <div className="mt-4 border-t border-slate-200/80 pt-3.5 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <p className="leading-relaxed">
        <span className="font-semibold text-[#01275C] dark:text-blue-300">{servable.length} banks supported</span>
        {groups.map((g) =>
          g.state === 'verified' || g.state === 'review_required' || g.state === 'legacy' ? null : (
            <span key={g.state}> · {g.banks.length} {g.label.toLowerCase()}</span>
          )
        )}
        .{ocr?.enabled ? ' Scanned statements are read with the universal OCR parser.' : ''} Other banks stay
        unprocessed — you can still pick a bank manually if one was detected incorrectly.
      </p>
      <details className="mt-2">
        <summary className="cursor-pointer select-none font-semibold text-[#01275C] underline decoration-dotted underline-offset-4 hover:text-[#0D3B82] dark:text-blue-300 dark:hover:text-blue-200">
          See the full bank list
        </summary>
        <div className="mt-3 space-y-3 rounded-xl border border-slate-200/90 bg-slate-50/70 p-4 dark:border-slate-700/80 dark:bg-[#08152B]/80">
          {groups.map((g) => (
            <div key={g.state} className="rounded-lg border border-slate-200/70 bg-white p-3 dark:border-slate-800 dark:bg-[#0B1B36]">
              <p className="font-semibold text-slate-800 dark:text-slate-100">
                <span aria-hidden="true" className="mr-1.5">{STATE_ICON[g.state]}</span>
                {g.label} ({g.banks.length})
              </p>
              <ul className={`mt-1.5 pl-5 ${isSelectable(g.state) ? 'grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3' : 'space-y-1'}`}>
                {g.banks.map((b) => (
                  <li key={b.id} className={isSelectable(b.support_state) ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 dark:text-slate-500'}>
                    {b.name}
                    {!isSelectable(b.support_state) && b.reason ? (
                      <span className="text-slate-400 dark:text-slate-500"> — {b.reason}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {ocr?.enabled && (
            <div className="rounded-lg border border-[#01275C]/20 bg-[#01275C]/[0.03] p-3 dark:border-blue-500/30 dark:bg-blue-950/30">
              <p className="font-semibold text-[#01275C] dark:text-blue-300">
                <span aria-hidden="true" className="mr-1.5">◉</span>
                Universal OCR parser (any scanned statement)
              </p>
              <ul className="mt-1 space-y-0.5 pl-5">
                <li className="text-slate-600 dark:text-slate-300">
                  Scanned or photographed statements from any bank — figures are read from the image and every
                  report is marked needs review{ocr.max_pages ? ` (up to ${ocr.max_pages} pages)` : ''}.
                </li>
              </ul>
            </div>
          )}
        </div>
      </details>
    </div>
  )
}
