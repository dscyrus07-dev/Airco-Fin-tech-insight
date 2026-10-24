import { describe, expect, it } from 'vitest'
import { isScanned, parseOcrCatalog } from '@/lib/statementsApi'

describe('parseOcrCatalog', () => {
  it('reads an enabled block', () => {
    expect(parseOcrCatalog({ enabled: true, reading_modes: ['thorough', 'fast'], default_reading: 'fast', max_pages: 60 }))
      .toEqual({ enabled: true, reading_modes: ['thorough', 'fast'], default_reading: 'fast', max_pages: 60 })
  })
  it('treats anything but enabled === true as off', () => {
    for (const raw of [{ enabled: 'yes' }, { enabled: 1 }, {}, { enabled: false, reading_modes: ['fast'] }]) {
      expect(parseOcrCatalog(raw)?.enabled).toBe(false)
      expect(parseOcrCatalog(raw)?.reading_modes).toEqual([])
    }
    expect(parseOcrCatalog(undefined)).toBeNull()
  })
  it('drops unknown readings and repairs a bad default', () => {
    const c = parseOcrCatalog({ enabled: true, reading_modes: ['fast', 'turbo'], default_reading: 'turbo' })
    expect(c?.reading_modes).toEqual(['fast'])
    expect(c?.default_reading).toBe('fast')
  })
})

describe('isScanned', () => {
  it('is true only for a scanned capability', () => {
    expect(isScanned({ capability: { capability: 'SCANNED' } })).toBe(true)
    expect(isScanned({ capability: { capability: 'MIXED' } })).toBe(false)
    expect(isScanned({ capability: null })).toBe(false)
    expect(isScanned({})).toBe(false)
  })
})
