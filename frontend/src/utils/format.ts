/** Formatting helpers: sizes, durations, dates (Gregorian or Jalali per user preference). */
import dayjs from 'dayjs'
import jalaliday from 'jalaliday'

dayjs.extend(jalaliday)

type Translate = (key: string, params?: Record<string, unknown>) => string

const UNITS = ['b', 'kb', 'mb', 'gb', 'tb'] as const

export function formatBytes(bytes: number, t: Translate): string {
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  const n = unit === 0 ? String(value) : value.toFixed(value < 10 ? 1 : 0)
  return t(`common.units.${UNITS[unit]}`, { n })
}

export function formatDuration(seconds: number, t: Translate): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (days) parts.push(t('common.duration.days', { n: days }))
  if (hours) parts.push(t('common.duration.hours', { n: hours }))
  if (minutes || parts.length === 0) parts.push(t('common.duration.minutes', { n: minutes }))
  return parts.join(' ')
}

export type CalendarKind = 'gregorian' | 'jalali'

export function formatDateTime(value: string | null | undefined, calendar: CalendarKind): string {
  if (!value) return ''
  const date = dayjs(value)
  if (calendar === 'jalali') return date.calendar('jalali').format('YYYY/MM/DD HH:mm')
  return date.calendar('gregory').format('YYYY-MM-DD HH:mm')
}

const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

export function toPersianDigits(text: string): string {
  return text.replace(/[0-9]/g, (d) => PERSIAN_DIGITS[Number(d)] ?? d)
}
