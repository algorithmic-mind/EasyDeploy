import { describe, expect, it } from 'vitest'

import { resolveTheme } from '@/composables/useTheme'
import { formatBytes, formatDateTime, formatDuration, toPersianDigits } from '@/utils/format'

const t = (key: string, params?: Record<string, unknown>) => `${key}:${String(params?.n)}`

describe('format', () => {
  it('formats bytes with binary units', () => {
    expect(formatBytes(512, t)).toBe('common.units.b:512')
    expect(formatBytes(2 * 1024 ** 3, t)).toBe('common.units.gb:2.0')
    expect(formatBytes(15 * 1024 ** 2, t)).toBe('common.units.mb:15')
  })

  it('formats durations', () => {
    expect(formatDuration(90061, t)).toBe(
      'common.duration.days:1 common.duration.hours:1 common.duration.minutes:1',
    )
    expect(formatDuration(5, t)).toBe('common.duration.minutes:0')
  })

  it('formats Gregorian and Jalali dates', () => {
    const iso = '2026-03-21T12:00:00Z' // Nowruz 1405 (minutes vary with the local time zone)
    expect(formatDateTime(iso, 'gregorian')).toMatch(/^2026-03-21 \d\d:\d\d$/)
    expect(formatDateTime(iso, 'jalali')).toMatch(/^1405\/01\/01 \d\d:\d\d$/)
    expect(formatDateTime(null, 'jalali')).toBe('')
  })

  it('converts digits to Persian', () => {
    expect(toPersianDigits('v1.2.30')).toBe('v۱.۲.۳۰')
  })

  it('resolves the system theme', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
    expect(resolveTheme('light', true)).toBe('light')
  })
})
