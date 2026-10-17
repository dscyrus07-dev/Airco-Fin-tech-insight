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
    { label: 'Statements uploaded', value: uploads, icon: 'upload', tint: 'bg-indigo-50 text-indigo-600' },
    { label: 'Processed', value: processed, icon: 'bolt', tint: 'bg-violet-50 text-violet-600' },
    { label: 'Reports ready', value: reports, icon: 'report', tint: 'bg-emerald-50 text-emerald-600' },
    { label: 'Batches', value: batches, icon: 'stack', tint: 'bg-amber-50 text-amber-600' },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((it, i) => (
        <div key={it.label} className="card-surface flex items-center gap-3 p-4 animate-fade-up" style={{ animationDelay: `${i * 70}ms` }}>
          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${it.tint}`}>
            <Icon name={it.icon} size={20} />
          </span>
          <div className="min-w-0">
            <AnimatedNumber value={it.value} className="block text-xl font-bold text-slate-900" />
            <p className="truncate text-xs text-slate-500">{it.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
