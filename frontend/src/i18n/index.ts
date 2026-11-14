/**
 * vue-i18n setup: one JSON file per module per locale (`locales/<lang>/<module>.json`),
 * namespaced by file name, e.g. `nav.overview`. Switching language flips `<html dir>` at runtime.
 */
import { createI18n } from 'vue-i18n'

import { setRequestLanguage } from '@/api/http'

export const LOCALES = ['en', 'fa'] as const
export type Locale = (typeof LOCALES)[number]
export const RTL_LOCALES: ReadonlySet<string> = new Set(['fa'])
const STORAGE_KEY = 'ed.locale'

type Messages = Record<string, Record<string, unknown>>

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value)
}

function load(): Record<Locale, Messages> {
  // Each file holds one namespace as its top-level key: locales/en/auth.json → {"auth": {...}}.
  const files = import.meta.glob<{ default: Messages }>('../locales/*/*.json', { eager: true })
  const messages: Record<Locale, Messages> = { en: {}, fa: {} }
  for (const [path, mod] of Object.entries(files)) {
    const lang = /locales\/(\w+)\//.exec(path)?.[1]
    if (isLocale(lang)) Object.assign(messages[lang], mod.default)
  }
  return messages
}

export const messages = load()

export function initialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLocale(stored)) return stored
  } catch {
    // storage unavailable
  }
  return navigator.language?.toLowerCase().startsWith('fa') ? 'fa' : 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: messages as unknown as Record<Locale, Record<string, string>>,
  missingWarn: import.meta.env.DEV,
  fallbackWarn: false,
})

export function applyLocale(locale: Locale): void {
  i18n.global.locale.value = locale
  const html = document.documentElement
  html.lang = locale
  html.dir = RTL_LOCALES.has(locale) ? 'rtl' : 'ltr'
  setRequestLanguage(locale)
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // storage unavailable
  }
}
