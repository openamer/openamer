import { afterEach, describe, expect, it } from 'vitest'

import { setRuntimeI18nLocale, translateNow } from './runtime'
import { xh } from './xh'

// Mechanical integration coverage, not a native-speaker quality certificate.
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

  it('materializes day labels and array entries without English fallback', () => {
    expect(xh.cron.days).toEqual({
      '0': 'NgeCawa',
      '1': 'NgoMvulo',
      '2': 'NgoLwesibini',
      '3': 'NgoLwesithathu',
      '4': 'NgoLwesine',
      '5': 'NgoLwesihlanu',
      '6': 'NgoMgqibelo',
      '7': 'NgeCawa',
    })
    expect(xh.composer.newSessionPlaceholders[0]).toBe('Sakha ntoni?')
  })

  it('keeps access-control guidance and operational errors reachable', () => {
    setRuntimeI18nLocale('xh')
    expect(translateNow('messaging.fieldCopy.TELEGRAM_ALLOWED_USERS.help')).toBe(
      'Kuyacetyiswa. Ii-ID zamanani ezivela ku-@userinfobot, zahlulwe ngeekoma. Ngaphandle koku, nabani na angathumela umyalezo wabucala kwi-bot yakho.',
    )
    expect(translateNow('desktop.handoff.failed', 'network')).toBe(
      'Ukudlulisela kusilele: network',
    )
    expect(translateNow('webhooks.enabled', 'repo')).toBe('Ivuliwe: "repo"')
  })

  it('retains optional nested interpolation branches without undefined values', () => {
    setRuntimeI18nLocale('xh')
    expect(translateNow('install.testSucceeded', 'https://example.test', null)).toBe(
      'Kuqhagamshelwe ku-https://example.test.',
    )
    expect(translateNow('install.testSucceeded', 'https://example.test', '1.0')).toBe(
      'Kuqhagamshelwe ku-https://example.test (1.0).',
    )
  })
})
