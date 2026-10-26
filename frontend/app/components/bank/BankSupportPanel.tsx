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
    <div className="mt-3 text-xs text-gray-500">
      <p>
        <span className="font-medium text-gray-600">{servable.length} banks supported</span>
        {groups.map((g) =>
          g.state === 'verified' || g.state === 'review_required' || g.state === 'legacy' ? null : (
            <span key={g.state}> · {g.banks.length} {g.label.toLowerCase()}</span>
          )
        )}
        .{ocr?.enabled ? ' Scanned statements are read with the universal OCR parser.' : ''} Other banks stay
        unprocessed — you can still pick a bank manually if one was detected incorrectly.
      </p>
      <details className="mt-1">
        <summary className="cursor-pointer select-none text-gray-600 underline decoration-dotted underline-offset-2">
          See the full bank list
        </summary>
        <div className="mt-2 space-y-2 rounded border border-neutral-200 bg-white p-3">
          {groups.map((g) => (
            <div key={g.state}>
              <p className="font-medium text-neutral-700">
                <span aria-hidden="true" className="mr-1">{STATE_ICON[g.state]}</span>
                {g.label} ({g.banks.length})
              </p>
              <ul className="mt-0.5 space-y-0.5 pl-5">
                {g.banks.map((b) => (
                  <li key={b.id} className={isSelectable(b.support_state) ? 'text-neutral-600' : 'text-neutral-400'}>
                    {b.name}
                    {!isSelectable(b.support_state) && b.reason ? (
                      <span className="text-neutral-400"> — {b.reason}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {ocr?.enabled && (
            <div>
              <p className="font-medium text-neutral-700">
                <span aria-hidden="true" className="mr-1">◉</span>
                Universal OCR parser (any scanned statement)
              </p>
              <ul className="mt-0.5 space-y-0.5 pl-5">
                <li className="text-neutral-400">
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
