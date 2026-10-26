import AnimatedNumber from './AnimatedNumber'
import Icon from './Icon'
import type { IconName } from './Icon'

interface StatsStripProps {
  uploads: number
  processed: number
  reports: number
  batches: number
}

export default function StatsStrip({ uploads, processed, reports, batches }: StatsStripProps) {
  const items: Array<{ label: string; value: number; icon: IconName; tint: string }> = [
    { label: 'Statements uploaded', value: uploads, icon: 'upload', tint: 'bg-[#01275C]/10 text-[#01275C] dark:bg-blue-500/20 dark:text-blue-300' },
    { label: 'Processed', value: processed, icon: 'bolt', tint: 'bg-blue-50 text-blue-700 dark:bg-sky-500/20 dark:text-sky-300' },
    { label: 'Reports ready', value: reports, icon: 'report', tint: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300' },
    { label: 'Batches', value: batches, icon: 'stack', tint: 'bg-amber-50 text-amber-600 dark:bg-amber-500/20 dark:text-amber-300' },
  ]
  return (
    <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
      {items.map((it, i) => (
        <div key={it.label} className="card-surface flex items-center gap-3.5 p-4 sm:p-5 animate-fade-up" style={{ animationDelay: `${i * 70}ms` }}>
          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${it.tint}`}>
            <Icon name={it.icon} size={20} />
          </span>
          <div className="min-w-0">
            <AnimatedNumber value={it.value} className="block text-xl font-bold text-[#01275C] dark:text-white" />
            <p className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">{it.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
