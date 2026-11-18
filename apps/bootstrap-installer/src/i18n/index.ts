import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'
import { useMemo } from 'react'

import names from './language-names.json'
import { CATALOGS, FALLBACK, type Lang, LANGUAGES, loadCatalogue, type Strings, type Template } from './strings'

export * from './strings'

const STORAGE_KEY = 'openamer-setup-language'

/** `{name}` substitution for templates that carry counts. */
export function fmt(template: Template, vars: Record<string, number | string>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match))
}

/**
 * The OS language, narrowed to a language the installer actually ships.
 *
 * `navigator.languages` is ordered by preference and `de-AT` must find `de`, so
 * we try exact, then the primary subtag, then nothing. Returning `null` (rather
 * than English) lets the language screen preselect honestly: either a real
 * match is highlighted, or nothing is, and the person chooses.
 */
export function detectLang(): Lang | null {
  const candidates = typeof navigator === 'undefined' ? [] : [...(navigator.languages ?? []), navigator.language]

  for (const tag of candidates.filter(Boolean)) {
    const lower = tag.toLowerCase()
    const exact = LANGUAGES.find(code => code.toLowerCase() === lower)

    if (exact) {
      return exact
    }

    const primary = lower.split('-')[0] ?? ''
    const byPrimary = LANGUAGES.find(code => code.toLowerCase() === primary)

    if (byPrimary) {
      return byPrimary
    }
  }

  return null
}

function stored(): Lang | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)

    // LANGUAGES, not CATALOGS: catalogues are now per-language chunks, so at
    // startup only English is in memory. Validating against the loaded ones
    // silently dropped a remembered choice and fell back to the OS language.
    return value && LANGUAGES.includes(value) ? value : null
  } catch {
    return null
  }
}

/**
 * Active installer language.
 *
 * A remembered choice wins over the OS guess: someone who picked Japanese on a
 * German machine should not be asked in German again on the next update.
 */
export const $lang = atom<Lang>(stored() ?? detectLang() ?? FALLBACK)

/**
 * Switch language. The catalogue is a separate chunk, so it is awaited first:
 * publishing the atom earlier would paint one frame of English.
 */
export async function setLang(lang: Lang): Promise<void> {
  if (!(await loadCatalogue(lang))) {
    return
  }

  $lang.set(lang)

  try {
    window.localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Private mode / locked storage: the choice still applies to this run.
  }
}

/** Load the initial language's chunk before the first paint. */
export async function preloadInitialLanguage(): Promise<void> {
  await loadCatalogue($lang.get())
}

/** Catalogue for a language, falling back to English for a missing key. */
export function strings(lang: Lang = $lang.get()): Strings {
  return CATALOGS[lang] ?? CATALOGS[FALLBACK]!
}

/** Re-renders a screen when the language changes. */
export function useStrings(): Strings {
  const lang = useStore($lang)

  return useMemo(() => strings(lang), [lang])
}

/**
 * Right-to-left languages. The setup window flips the whole document for these
 * (`dir="rtl"`), exactly like the app does — Arabic text laid out left-to-right
 * reads as broken, not as translated.
 */
export const RTL_LANGUAGES: ReadonlySet<Lang> = new Set<Lang>([
  'ar',
  'ckb',
  'dv',
  'fa',
  'he',
  'ku',
  'ps',
  'sd',
  'ug',
  'ur',
  'yi'
])

export function isRtl(lang: Lang): boolean {
  return RTL_LANGUAGES.has(lang)
}

export interface LanguageEntry {
  code: Lang
  endonym: string
  englishName: string
}

const NAME_TABLE = names as Record<string, { endonym: string; englishName: string }>

/**
 * Every language the INSTALLER can speak — the whole point of building the list
 * from the catalogues instead of from a wish list: a language offered and then
 * answered in English mid-flow is worse than one that is not offered.
 */
export const LANGUAGE_ENTRIES: LanguageEntry[] = LANGUAGES.map(code => ({
  code,
  endonym: NAME_TABLE[code]?.endonym ?? code.toUpperCase(),
  englishName: NAME_TABLE[code]?.englishName ?? code.toUpperCase()
})).sort((a, b) => a.endonym.localeCompare(b.endonym, undefined, { sensitivity: 'base' }))
