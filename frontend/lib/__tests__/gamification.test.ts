import { describe, expect, it } from 'vitest'
import {
  EMPTY_INPUT,
  LEVELS,
  computeBadges,
  computeQuests,
  computeXp,
  countBanks,
  dayKey,
  levelFor,
  streakFrom,
} from '../gamification'

describe('gamification', () => {
  it('starts every new user at level 1 with zero XP', () => {
    expect(computeXp(EMPTY_INPUT)).toBe(0)
    const s = levelFor(0)
    expect(s.level.name).toBe('Rookie')
    expect(s.pct).toBe(0)
    expect(s.next?.name).toBe('Explorer')
    expect(s.xpToNext).toBe(60)
  })

  it('awards XP for real activity and ignores junk values', () => {
    const xp = computeXp({ ...EMPTY_INPUT, uploads: 2, processed: 2, reports: 2, batches: 1 })
    expect(xp).toBe(2 * 10 + 2 * 20 + 2 * 15 + 5)
    expect(computeXp({ ...EMPTY_INPUT, uploads: -4, processed: Number.NaN })).toBe(0)
  })

  it('caps the streak bonus at 7 days', () => {
    expect(computeXp({ ...EMPTY_INPUT, streakDays: 30 })).toBe(70)
  })

  it('moves up levels at the documented thresholds and tops out at Legend', () => {
    expect(levelFor(59).level.name).toBe('Rookie')
    expect(levelFor(60).level.name).toBe('Explorer')
    expect(levelFor(1600).level.name).toBe('Legend')
    const top = levelFor(99999)
    expect(top.next).toBeNull()
    expect(top.pct).toBe(100)
    expect(LEVELS.map((l) => l.min)).toEqual([...LEVELS.map((l) => l.min)].sort((a, b) => a - b))
  })

  it('reports in-level progress as a percentage', () => {
    // Explorer is 60..180 -> halfway is 120
    expect(levelFor(120).pct).toBe(50)
  })

  it('unlocks badges only when their target is reached', () => {
    const none = computeBadges(EMPTY_INPUT)
    expect(none.every((b) => !b.unlocked)).toBe(true)
    const some = computeBadges({ ...EMPTY_INPUT, uploads: 1, reports: 5, banksUsed: 2, guideOpened: true })
    const by = Object.fromEntries(some.map((b) => [b.id, b]))
    expect(by['first-upload'].unlocked).toBe(true)
    expect(by['five-reports'].unlocked).toBe(true)
    expect(by['multi-bank'].unlocked).toBe(false)
    expect(by['multi-bank'].current).toBe(2)
    expect(by['guide'].unlocked).toBe(true)
  })

  it('never reports progress above the target', () => {
    const b = computeBadges({ ...EMPTY_INPUT, reports: 99 }).find((x) => x.id === 'five-reports')!
    expect(b.current).toBe(5)
  })

  it('marks quests done from activity', () => {
    const q = computeQuests({ ...EMPTY_INPUT, uploads: 1, guideOpened: true })
    expect(q.find((x) => x.id === 'q-upload')?.done).toBe(true)
    expect(q.find((x) => x.id === 'q-guide')?.done).toBe(true)
    expect(q.find((x) => x.id === 'q-report')?.done).toBe(false)
  })

  it('counts consecutive visit days and tolerates a missed today', () => {
    const today = new Date(2026, 9, 17)
    const d = (offset: number) => dayKey(new Date(2026, 9, 17 + offset))
    expect(streakFrom([d(0), d(-1), d(-2)], today)).toBe(3)
    expect(streakFrom([d(-1), d(-2)], today)).toBe(2)
    expect(streakFrom([d(0), d(-2)], today)).toBe(1)
    expect(streakFrom([], today)).toBe(0)
    expect(streakFrom([d(-5)], today)).toBe(0)
  })

  it('counts distinct real banks only', () => {
    expect(countBanks(['HDFC Bank', 'hdfc bank', 'Unknown', '', null, undefined, 'Federal Bank'])).toBe(2)
  })
})
