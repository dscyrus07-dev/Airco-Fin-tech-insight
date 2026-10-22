'use client'

import { useMemo } from 'react'
import Accordion from './Accordion'
import Icon from './Icon'
import type { IconName } from './Icon'
import { useBankCatalog } from '@/app/hooks/useBankCatalog'
import { groupByState } from '@/lib/bankSupport'

const STEPS: Array<{ icon: IconName; title: string; body: string }> = [
  { icon: 'user', title: 'Tell us who the statement belongs to', body: 'Type the account holder’s name so the report is labelled correctly.' },
  { icon: 'bank', title: 'Pick the bank', body: 'Choose the bank that issued the statement. Not sure? Pick the closest match; the engine double-checks it.' },
  { icon: 'upload', title: 'Drop your PDF statements', body: 'Drag the files in, or click to browse. You can add up to 20 statements at once. If a PDF is locked, we will ask for its password.' },
  { icon: 'eye', title: 'Review before we start', body: 'Check the list once: right bank, right file. Fix anything that looks off, then confirm.' },
  { icon: 'clock', title: 'Wait a moment', body: 'We read every transaction, sort it into a category and check that the balances add up. Most statements take under a minute.' },
  { icon: 'download', title: 'Download your Excel report', body: 'You get a ready-to-use workbook with every transaction, category totals and summaries. Reports are kept for 7 days, so download what you need.' },
]

interface HelpCenterProps {
  onGuideOpened?: () => void
  onLimitsOpened?: () => void
}

export default function HelpCenter({ onGuideOpened, onLimitsOpened }: HelpCenterProps) {
  const catalog = useBankCatalog()
  const groups = useMemo(() => groupByState(catalog.all_banks ?? []), [catalog.all_banks])
  const count = (s: string) => groups.find((g) => g.state === s)?.banks.length ?? 0
  const ready = count('verified') + count('review_required') + count('legacy')
  const total = catalog.all_banks?.length ?? 0

  return (
    <div className="space-y-4" id="help-center">
      <Accordion
        title="How to use Airco Insights"
        subtitle="A 2-minute guide in plain language"
        icon="book"
        onFirstOpen={onGuideOpened}
      >
        <ol className="grid gap-4 sm:grid-cols-2">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-3 rounded-xl bg-slate-50/70 p-4 ring-1 ring-slate-100">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white">
                {i + 1}
              </span>
              <div>
                <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Icon name={s.icon} size={16} className="text-indigo-500" />
                  {s.title}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-4 flex items-start gap-2 rounded-xl bg-indigo-50 p-3 text-sm text-indigo-900">
          <Icon name="lightbulb" size={18} className="mt-0.5 shrink-0" />
          Tip: use the original PDF downloaded from your bank. Photos, scans and screenshots cannot be read.
        </p>
      </Accordion>

      <Accordion
        title="Limits & supported banks"
        subtitle={ready > 0 ? `${ready} banks ready to use • what we cannot do yet` : 'What we cannot do yet'}
        icon="scale"
        accent="amber"
        onFirstOpen={onLimitsOpened}
      >
        {total > 0 && (
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ['Ready to use', ready],
              ['Verified engine', count('verified')],
              ['Always needs review', count('review_required')],
              ['Coming soon', count('coming_soon')],
            ].map(([label, n]) => (
              <div key={label as string} className="rounded-xl bg-slate-50 p-3 text-center ring-1 ring-slate-100">
                <p className="text-2xl font-bold text-slate-900">{n as number}</p>
                <p className="text-xs text-slate-500">{label as string}</p>
              </div>
            ))}
          </div>
        )}
        <h4 className="mb-2 text-sm font-semibold text-slate-900">Good to know</h4>
        <ul className="space-y-2 text-sm text-slate-600">
          {[
            'Only text-based PDFs are supported. Scanned or photographed statements cannot be read (no OCR).',
            'Up to 20 statements per batch, up to 500 pages per PDF, and 30 uploads per minute.',
            'Files and reports are deleted automatically after 7 days.',
            'Some banks do not print running balances, so their totals cannot be independently proven. These are marked “needs review”.',
            'Categories come from a fixed rulebook. A few unusual entries may stay as “Others”; they are never guessed silently.',
            'This tool organises your data. It does not give financial, credit or legal advice.',
          ].map((t) => (
            <li key={t} className="flex gap-2">
              <Icon name="info" size={16} className="mt-0.5 shrink-0 text-amber-500" />
              <span>{t}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-slate-500">
          Open <span className="font-medium">Supported banks</span> in the upload step for the full, searchable list.
        </p>
      </Accordion>
    </div>
  )
}
