'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { SheetPreview } from '@/types'

interface CollapsiblePreviewProps {
  sheet: SheetPreview
}

export default function CollapsiblePreview({ sheet }: CollapsiblePreviewProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 transition-colors"
      >
        <span className="text-sm font-medium text-black">{sheet.title}</span>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-neutral-500" />
        ) : (
          <ChevronRight className="w-4 h-4 text-neutral-500" />
        )}
      </button>

      {isOpen && (
        <div className="border-t border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50">
                {sheet.headers.map((header, i) => (
                  <th
                    key={i}
                    className="px-4 py-2 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider whitespace-nowrap"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheet.rows.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-neutral-50'}
                >
                  {row.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="px-4 py-2 text-sm text-black whitespace-nowrap"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {sheet.rows.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-neutral-400">
              No data available in preview.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
