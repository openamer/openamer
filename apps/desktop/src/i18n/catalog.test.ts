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
})
