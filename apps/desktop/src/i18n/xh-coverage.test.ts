import { describe, expect, it } from 'vitest'

import { en } from './en'
import { xh } from './xh'

// Deliberate verbatim DISPLAY values, classified individually rather than by
// length or capitalization. This is not permission to exempt arbitrary prose.
const VERBATIM_STRINGS: Record<string, string> = {
  // Product, protocol, platform and plan names.
  'settings.gateway.cloudTitle': 'OpenAmer Cloud',
  'settings.gateway.cloudSignInTitle': 'OpenAmer Cloud',
  'settings.nav.mcp': 'MCP',
  'settings.notifications.testTitle': 'OpenAmer',
  'settings.about.heading': 'OpenAmer Desktop',
  'settings.model.tasks.mcp.label': 'MCP',
  'skills.tabMcp': 'MCP',
  'webhooks.deliverOptions.telegram': 'Telegram',
  'webhooks.deliverOptions.discord': 'Discord',
  'webhooks.deliverOptions.slack': 'Slack',
  'cron.deliveryLabels.telegram': 'Telegram',
  'cron.deliveryLabels.discord': 'Discord',
  'cron.deliveryLabels.slack': 'Slack',
  'onboarding.pro': 'Pro',
  'modelPicker.pro': 'Pro',
  'shell.statusbar.cron': 'Cron',
  'shell.statusbar.contextUsagePanel.categories.mcp': 'MCP',
  'desktop.yoloTitle': 'YOLO',
  // Executable identifiers and example addresses must remain usable.
  'settings.appearance.installPlaceholder': 'publisher.extension',
  'profiles.env': 'env',
  'messaging.fieldCopy.MATTERMOST_URL.placeholder': 'https://mattermost.example.com',
  'messaging.fieldCopy.MATRIX_HOMESERVER.placeholder': 'https://matrix.org',
  'messaging.fieldCopy.MATRIX_USER_ID.placeholder': '@openamer:example.org',
  'messaging.fieldCopy.SIGNAL_HTTP_URL.placeholder': 'http://127.0.0.1:8080',
  'composer.urlPlaceholder': 'https://example.com/post',
  'install.remoteUrlPlaceholder': 'https://gateway.example.com/openamer',
  // Numeric, punctuation, sorting, unit and URL notation, not English prose.
  'profiles.renameDescSuffix': '.',
  'skills.sortAlpha': 'A–Z',
  'artifacts.zero': '0',
  'artifacts.colLocationLink': 'URL',
  'sidebar.row.ageDay': 'd',
  'sidebar.row.ageHour': 'h',
  'sidebar.row.ageMin': 'm',
  'composer.themeTryPost': '.',
  'composer.url': 'URL…',
}

function strings(value: unknown, parts: string[] = [], result = new Map<string, string>()) {
  if (typeof value === 'string') {
    const key = parts.join('\u001f')

    if (result.has(key)) {throw new Error(`Duplicate catalog path: ${JSON.stringify(parts)}`)}
    result.set(key, value)
  }
  else if (value !== null && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {strings(child, [...parts, key], result)}
  }

  return result
}

// This walks the MERGED runtime catalog, arrays and imported field records too.
// Dynamic functions need separate branch probes in xh-dynamic.test.ts.
// Different-from-English is a gap check, not native-speaker quality assurance.
describe('isiXhosa static runtime coverage', () => {
  const reference = strings(en)
  const translated = strings(xh)

  const verbatim = new Map(Object.entries(VERBATIM_STRINGS)
    .map(([path, value]) => [path.replaceAll('.', '\u001f'), value]))

  it('covers exactly the reference display-string paths', () => {
    expect([...translated.keys()].sort()).toEqual([...reference.keys()].sort())
  })

  it('has no unclassified English fallback strings', () => {
    const gaps = [...reference].filter(([key, value]) =>
      !translated.get(key)?.trim() || (translated.get(key) === value && !verbatim.has(key)))

    expect(gaps.map(([key]) => key.replaceAll('\u001f', '.'))).toEqual([])
  })

  it('keeps every explicitly exempt technical value byte-identical', () => {
    for (const [key, value] of verbatim) {
      expect(reference.get(key), key).toBe(value)
      expect(translated.get(key), key).toBe(value)
    }
  })
})
