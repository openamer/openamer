import { afterEach, describe, expect, it } from 'vitest'

import { setRuntimeI18nLocale, translateNow } from './runtime'

// This is deliberately partial coverage, not a claim of language completeness.
describe('isiXhosa catalog integration', () => {
  afterEach(() => setRuntimeI18nLocale('en'))

  it('resolves translated strings from the registered catalog', () => {
    setRuntimeI18nLocale('xh')
    expect(translateNow('common.save')).toBe('Gcina')
    expect(translateNow('commandCenter.installTheme.pageTitle')).toBe('Faka umxholo')
  })

  it('preserves the signature and substitutions of translated functions', () => {
    setRuntimeI18nLocale('xh')
    expect(translateNow('commandCenter.generatePet.hatchRow', 'sketching', 2, 4)).toBe(
      'Kuzotywa isakhelo 2 kwezingu-4…',
    )
    expect(translateNow('commandCenter.openamerActiveSessions', 'test-version', 3)).toBe(
      'OpenAmer test-version · Iiseshoni ezisebenzayo 3',
    )
  })
})
