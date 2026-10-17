/**
 * Gamification model for the dashboard: XP, levels, quests and badges.
 *
 * Everything is DERIVED from data the app already has (profile history counts plus a few
 * per-browser flags). Nothing is sent to the server and no score can unlock any feature —
 * it is purely motivational. All functions are pure so they can be unit-tested.
 */

export interface ProgressInput {
  uploads: number
  processed: number
  reports: number
  batches: number
  banksUsed: number
  verifiedReports: number
  guideOpened: boolean
  limitsOpened: boolean
  streakDays: number
}

export const EMPTY_INPUT: ProgressInput = {
  uploads: 0,
  processed: 0,
  reports: 0,
  batches: 0,
  banksUsed: 0,
  verifiedReports: 0,
  guideOpened: false,
  limitsOpened: false,
  streakDays: 0,
}

export interface Level {
  index: number
  name: string
  min: number
}

export const LEVELS: readonly Level[] = [
  { index: 1, name: 'Rookie', min: 0 },
  { index: 2, name: 'Explorer', min: 60 },
  { index: 3, name: 'Analyst', min: 180 },
  { index: 4, name: 'Specialist', min: 360 },
  { index: 5, name: 'Pro', min: 620 },
  { index: 6, name: 'Expert', min: 1000 },
  { index: 7, name: 'Legend', min: 1600 },
]

const num = (n: unknown): number => (typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.floor(n) : 0)

export function computeXp(i: ProgressInput): number {
  return (
    num(i.uploads) * 10 +
    num(i.processed) * 20 +
    num(i.reports) * 15 +
    num(i.batches) * 5 +
    num(i.verifiedReports) * 10 +
    (i.guideOpened ? 25 : 0) +
    (i.limitsOpened ? 25 : 0) +
    Math.min(num(i.streakDays), 7) * 10
  )
}

export interface LevelState {
  level: Level
  next: Level | null
  xp: number
  /** 0..100 progress inside the current level (100 at max level). */
  pct: number
  xpToNext: number
}

export function levelFor(xp: number): LevelState {
  const safe = Math.max(0, Math.floor(xp) || 0)
  let level = LEVELS[0]
  for (const l of LEVELS) if (safe >= l.min) level = l
  const next = LEVELS.find((l) => l.min > level.min) ?? null
  if (!next) return { level, next: null, xp: safe, pct: 100, xpToNext: 0 }
  const span = next.min - level.min
  return {
    level,
    next,
    xp: safe,
    pct: Math.min(100, Math.max(0, Math.round(((safe - level.min) / span) * 100))),
    xpToNext: next.min - safe,
  }
}

export type BadgeIcon = 'upload' | 'report' | 'stack' | 'bank' | 'shield' | 'book' | 'scale' | 'flame' | 'bolt' | 'crown'

export interface Badge {
  id: string
  title: string
  description: string
  icon: BadgeIcon
  unlocked: boolean
  current: number
  target: number
}

function badge(id: string, title: string, description: string, icon: BadgeIcon, current: number, target: number): Badge {
  const c = Math.min(current, target)
  return { id, title, description, icon, unlocked: current >= target, current: c, target }
}

export function computeBadges(i: ProgressInput): Badge[] {
  return [
    badge('first-upload', 'First Steps', 'Upload your first statement', 'upload', i.uploads, 1),
    badge('first-report', 'Report Ready', 'Generate your first report', 'report', i.reports, 1),
    badge('five-reports', 'Report Machine', 'Generate 5 reports', 'stack', i.reports, 5),
    badge('multi-bank', 'Bank Hopper', 'Analyse statements from 3 different banks', 'bank', i.banksUsed, 3),
    badge('reports-3', 'Hat-trick', 'Generate 3 reports', 'shield', i.reports, 3),
    badge('batch-3', 'Batch Boss', 'Run 3 upload batches', 'bolt', i.batches, 3),
    badge('guide', 'Guide Explorer', 'Read the "How to use" guide', 'book', i.guideOpened ? 1 : 0, 1),
    badge('limits', 'Fine-Print Reader', 'Read the limits & supported banks', 'scale', i.limitsOpened ? 1 : 0, 1),
    badge('streak-3', 'On a Roll', 'Visit 3 days in a row', 'flame', i.streakDays, 3),
    badge('twenty', 'Power User', 'Process 20 statements', 'crown', i.processed, 20),
  ]
}

export interface Quest {
  id: string
  title: string
  hint: string
  done: boolean
  target: 'upload' | 'guide' | 'limits' | 'report'
  xp: number
}

export function computeQuests(i: ProgressInput): Quest[] {
  return [
    { id: 'q-guide', title: 'Read the quick guide', hint: 'Takes one minute', done: i.guideOpened, target: 'guide', xp: 25 },
    { id: 'q-upload', title: 'Upload a statement', hint: 'Drop any supported bank PDF', done: i.uploads > 0, target: 'upload', xp: 10 },
    { id: 'q-report', title: 'Download your first report', hint: 'Excel, 9 sheets, fully categorized', done: i.reports > 0, target: 'report', xp: 15 },
    { id: 'q-limits', title: 'Check what is supported', hint: 'Banks and limits at a glance', done: i.limitsOpened, target: 'limits', xp: 25 },
  ]
}

/* ------------------------------------------------------------------ */
/* Per-browser state (guide/limits opened, visit days, seen badges).   */
/* Every access is guarded: storage can be blocked or throw.           */
/* ------------------------------------------------------------------ */

export interface LocalState {
  guideOpened: boolean
  limitsOpened: boolean
  visitDays: string[]
  seenBadges: string[]
  /** True once the user's existing badges were recorded as already seen (no celebration spam on first load). */
  baselined: boolean
}

const KEY = 'airco-progress-v1'

export const EMPTY_LOCAL: LocalState = { guideOpened: false, limitsOpened: false, visitDays: [], seenBadges: [], baselined: false }

export function readLocal(): LocalState {
  try {
    if (typeof window === 'undefined') return { ...EMPTY_LOCAL }
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return { ...EMPTY_LOCAL }
    const p = JSON.parse(raw) as Partial<LocalState>
    return {
      guideOpened: p.guideOpened === true,
      limitsOpened: p.limitsOpened === true,
      visitDays: Array.isArray(p.visitDays) ? p.visitDays.filter((d): d is string => typeof d === 'string').slice(-30) : [],
      seenBadges: Array.isArray(p.seenBadges) ? p.seenBadges.filter((d): d is string => typeof d === 'string') : [],
      baselined: p.baselined === true,
    }
  } catch {
    return { ...EMPTY_LOCAL }
  }
}

export function writeLocal(next: LocalState): void {
  try {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: progress simply is not remembered
  }
}

/** ISO day (local time) like 2026-10-17. */
export function dayKey(d: Date = new Date()): string {
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** Consecutive visit days ending today (or yesterday: a streak is not lost until a full day is missed). */
export function streakFrom(visitDays: string[], today: Date = new Date()): number {
  const set = new Set(visitDays)
  const cursor = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  if (!set.has(dayKey(cursor))) cursor.setDate(cursor.getDate() - 1)
  let n = 0
  while (set.has(dayKey(cursor))) {
    n += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  return n
}

/** Distinct, real bank names (ignores empty / "Unknown"). */
export function countBanks(names: Array<string | null | undefined>): number {
  const s = new Set<string>()
  for (const n of names) {
    const t = (n || '').trim()
    if (t && t.toLowerCase() !== 'unknown') s.add(t.toLowerCase())
  }
  return s.size
}
