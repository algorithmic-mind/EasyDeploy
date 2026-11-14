/** §10.4: en and fa catalogs must have exactly the same keys and no empty values. */
import { describe, expect, it } from 'vitest'

import { messages } from '@/i18n'
import { NAVIGATION } from '@/navigation'

function flatten(obj: Record<string, unknown>, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object')
      Object.assign(out, flatten(value as Record<string, unknown>, path))
    else out[path] = String(value)
  }
  return out
}

const en = flatten(messages.en)
const fa = flatten(messages.fa)

describe('i18n catalogs', () => {
  it('have the same keys in en and fa', () => {
    expect(Object.keys(fa).sort()).toEqual(Object.keys(en).sort())
  })

  it('have no empty strings', () => {
    for (const [key, value] of Object.entries({ ...en, ...fa })) {
      expect(value.trim(), key).not.toBe('')
    }
  })

  it('keep the same placeholders in both languages', () => {
    const params = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort()
    for (const key of Object.keys(en)) {
      expect(params(fa[key] ?? ''), key).toEqual(params(en[key] ?? ''))
    }
  })

  it('translate every navigation entry', () => {
    for (const section of NAVIGATION) {
      expect(en[`nav.${section.key}.title`], section.key).toBeTruthy()
      for (const page of section.pages) {
        expect(en[`nav.${section.key}.${page.key}`], page.path).toBeTruthy()
        expect(fa[`nav.${section.key}.${page.key}`], page.path).toBeTruthy()
      }
    }
  })
})
