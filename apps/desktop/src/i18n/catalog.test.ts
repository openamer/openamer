import { describe, expect, it } from 'vitest'

import { TRANSLATIONS } from './catalog'
import { LOCALE_OPTIONS, localeConfigValue } from './languages'

// A picker entry with no message tree in TRANSLATIONS resolves against
// `undefined` and every key falls through to English — the user picks a
// language and the whole UI stays English, with no error anywhere. That is
// what an unregistered `nas` locale did.
describe('desktop i18n catalog', () => {
  it('has a message tree for every locale offered in the picker', () => {
    const missing = LOCALE_OPTIONS.filter(option => !TRANSLATIONS[option.id]).map(option => option.id)

    expect(missing).toEqual([])
  })

  it('stores each picker entry under its config value', () => {
    for (const option of LOCALE_OPTIONS) {
      expect(localeConfigValue(option.id), option.id).toBe(option.configValue)
    }
  })

  it('offers every locale the catalog carries', () => {
    const offered = new Set<string>(LOCALE_OPTIONS.map(option => option.id))
    const unlisted = (Object.keys(TRANSLATIONS) as string[]).filter(locale => !offered.has(locale))

    expect(unlisted).toEqual([])
  })

  // A hotkey marker belongs on a visible label, never inside an ARIA label:
  // screen readers announce "[e]" verbatim, so the user hears "bracket e
  // bracket page précédente". Measured in `ln`, which shipped
  // `previousAria: 'Y[e] page précédente'` and `nextAria: 'Y[e] page suivante'`.
  it('keeps hotkey markers out of aria labels', () => {
    const offenders: string[] = []

    const walk = (node: unknown, path: string): void => {
      if (node === null || typeof node !== 'object') {
        return
      }

      for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
        const next = path ? `${path}.${key}` : key

        if (typeof value === 'string') {
          if (/aria/i.test(key) && /\[[A-Za-z0-9]\]/.test(value)) {
            offenders.push(next)
          }

          continue
        }

        walk(value, next)
      }
    }

    for (const [code, tree] of Object.entries(TRANSLATIONS)) {
      walk(tree, code)
    }

    expect(offenders).toEqual([])
  })

  // Measured 2026-11-16: the German update dialog rendered
  // "+ 1 weitere ÄnderungÄnderung enthalten" because the template already ended
  // with "Änderung" and the singular branch appended the word again. The same
  // generator shape existed in 37 locales (314 duplicates), e.g. bg
  // "нова промяна" + 'промяна'. A duplicated stem word is always a defect: the
  // branch is supposed to SUPPLY the word, not repeat it.
  it('never duplicates a stem word in the "more changes" line', () => {
    const offenders: string[] = []

    for (const [code, tree] of Object.entries(TRANSLATIONS)) {
      const updates = (tree as Record<string, unknown>)['updates'] as Record<string, unknown> | undefined
      const moreChanges = updates?.['moreChanges']

      if (typeof moreChanges !== 'function') {
        continue
      }

      for (const count of [1, 2, 5]) {
        const text = String((moreChanges as (n: number) => string)(count))

        if (/(\p{L}{4,})\1/u.test(text)) {
          offenders.push(`${code}(${count}): ${text}`)
        }
      }
    }

    expect(offenders).toEqual([])
  })
})
