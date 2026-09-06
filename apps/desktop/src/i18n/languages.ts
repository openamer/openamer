import { normalize } from '@/lib/text'

import type { Locale } from './types'

export const DEFAULT_LOCALE: Locale = 'en'

export const LOCALE_OPTIONS = [
  {
    id: 'en',
    name: 'English',
    englishName: 'English',
    configValue: 'en'
  },
  {
    id: 'zh',
    name: '简体中文',
    englishName: 'Simplified Chinese',
    configValue: 'zh'
  },
  {
    id: 'zh-hant',
    name: '繁體中文',
    englishName: 'Traditional Chinese',
    configValue: 'zh-hant'
  },
  {
    id: 'ja',
    name: '日本語',
    englishName: 'Japanese',
    configValue: 'ja'
  },
  {
    id: 'ar',
    name: 'العربية',
    englishName: 'Arabic',
    configValue: 'ar'
  },
  {
    id: 'de',
    name: 'Deutsch',
    englishName: 'German',
    configValue: 'de'
  },
  {
    id: 'es',
    name: 'Español',
    englishName: 'Spanish',
    configValue: 'es'
  },
  {
    id: 'pt',
    name: 'Português',
    englishName: 'Portuguese',
    configValue: 'pt'
  },
  {
    id: 'sq',
    name: 'Shqip',
    englishName: 'Albanian',
    configValue: 'sq'
  },
  {
    id: 'bs',
    name: 'Bosanski',
    englishName: 'Bosnian',
    configValue: 'bs'
  },
  {
    id: 'fr',
    name: 'Français',
    englishName: 'French',
    configValue: 'fr'
  },
  {
    id: 'it',
    name: 'Italiano',
    englishName: 'Italian',
    configValue: 'it'
  },
  {
    id: 'tr',
    name: 'Türkçe',
    englishName: 'Turkish',
    configValue: 'tr'
  },
  {
    id: 'ru',
    name: 'Русский',
    englishName: 'Russian',
    configValue: 'ru'
  },
  {
    id: 'hi',
    name: 'हिन्दी',
    englishName: 'Hindi',
    configValue: 'hi'
  },
  {
    id: 'fa',
    name: 'فارسی',
    englishName: 'Persian',
    configValue: 'fa'
  },
  {
    id: 'uk',
    name: 'Українська',
    englishName: 'Ukrainian',
    configValue: 'uk'
  },
  {
    id: 'ko',
    name: '한국어',
    englishName: 'Korean',
    configValue: 'ko'
  },
  {
    id: 'id',
    name: 'Bahasa Indonesia',
    englishName: 'Indonesian',
    configValue: 'id'
  },
  {
    id: 'th',
    name: 'ไทย',
    englishName: 'Thai',
    configValue: 'th'
  },
  {
    id: 'vi',
    name: 'Tiếng Việt',
    englishName: 'Vietnamese',
    configValue: 'vi'
  },
  {
    id: 'eo',
    name: 'Esperanto',
    englishName: 'Esperanto',
    configValue: 'eo'
  },
  {
    id: 'pl',
    name: 'Polski',
    englishName: 'Polish',
    configValue: 'pl'
  },
  {
    id: 'nl',
    name: 'Nederlands',
    englishName: 'Dutch',
    configValue: 'nl'
  },
  {
    id: 'ro',
    name: 'Română',
    englishName: 'Romanian',
    configValue: 'ro'
  },
  {
    id: 'el',
    name: 'Ελληνικά',
    englishName: 'Greek',
    configValue: 'el'
  },
  {
    id: 'cs',
    name: 'Čeština',
    englishName: 'Czech',
    configValue: 'cs'
  },
  {
    id: 'sv',
    name: 'Svenska',
    englishName: 'Swedish',
    configValue: 'sv'
  },
  {
    id: 'hu',
    name: 'Magyar',
    englishName: 'Hungarian',
    configValue: 'hu'
  },
  {
    id: 'bg',
    name: 'Български',
    englishName: 'Bulgarian',
    configValue: 'bg'
  },
  {
    id: 'da',
    name: 'Dansk',
    englishName: 'Danish',
    configValue: 'da'
  },
  {
    id: 'fi',
    name: 'Suomi',
    englishName: 'Finnish',
    configValue: 'fi'
  },
  {
    id: 'sk',
    name: 'Slovenčina',
    englishName: 'Slovak',
    configValue: 'sk'
  },
  {
    id: 'no',
    name: 'Norsk',
    englishName: 'Norwegian',
    configValue: 'no'
  },
  {
    id: 'ga',
    name: 'Gaeilge',
    englishName: 'Irish',
    configValue: 'ga'
  },
  {
    id: 'sl',
    name: 'Slovenščina',
    englishName: 'Slovenian',
    configValue: 'sl'
  }
] as const satisfies readonly { configValue: string; englishName: string; id: Locale; name: string }[]

// `name` is the endonym (native name) shown in the picker so users recognize
// their language regardless of the current UI language. No country flags:
// languages are not countries. `englishName` is search-only (not shown) so an
// English speaker can type "japanese"/"traditional" to filter the list.
export const LOCALE_META: Record<Locale, { name: string; englishName: string }> = Object.fromEntries(
  LOCALE_OPTIONS.map(locale => [locale.id, { name: locale.name, englishName: locale.englishName }])
) as Record<Locale, { name: string; englishName: string }>

const LOCALE_ALIASES: Record<string, Locale> = {
  en: 'en',
  'en-us': 'en',
  en_us: 'en',
  zh: 'zh',
  'zh-cn': 'zh',
  zh_cn: 'zh',
  'zh-hans': 'zh',
  zh_hans: 'zh',
  'zh-hans-cn': 'zh',
  zh_hans_cn: 'zh',
  'zh-tw': 'zh-hant',
  zh_tw: 'zh-hant',
  'zh-hk': 'zh-hant',
  zh_hk: 'zh-hant',
  'zh-mo': 'zh-hant',
  zh_mo: 'zh-hant',
  'zh-hant': 'zh-hant',
  zh_hant: 'zh-hant',
  'zh-hant-tw': 'zh-hant',
  zh_hant_tw: 'zh-hant',
  'zh-hant-hk': 'zh-hant',
  zh_hant_hk: 'zh-hant',
  ja: 'ja',
  'ja-jp': 'ja',
  ja_jp: 'ja',
  ar: 'ar',
  'ar-sa': 'ar',
  ar_sa: 'ar',
  'ar-ae': 'ar',
  ar_ae: 'ar',
  'ar-eg': 'ar',
  ar_eg: 'ar',
  arabic: 'ar',
  العربية: 'ar',
  de: 'de',
  'de-de': 'de',
  de_de: 'de',
  'de-at': 'de',
  de_at: 'de',
  'de-ch': 'de',
  de_ch: 'de',
  german: 'de',
  deutsch: 'de',
  es: 'es',
  'es-es': 'es',
  es_es: 'es',
  'es-mx': 'es',
  es_mx: 'es',
  'es-ar': 'es',
  es_ar: 'es',
  spanish: 'es',
  español: 'es',
  pt: 'pt',
  'pt-pt': 'pt',
  pt_pt: 'pt',
  'pt-br': 'pt',
  pt_br: 'pt',
  portuguese: 'pt',
  português: 'pt',
  sq: 'sq',
  'sq-al': 'sq',
  sq_al: 'sq',
  albanian: 'sq',
  shqip: 'sq',
  bs: 'bs',
  'bs-ba': 'bs',
  bs_ba: 'bs',
  bosnian: 'bs',
  bosanski: 'bs',
  fr: 'fr',
  'fr-fr': 'fr',
  fr_fr: 'fr',
  'fr-ca': 'fr',
  fr_ca: 'fr',
  french: 'fr',
  français: 'fr',
  it: 'it',
  'it-it': 'it',
  it_it: 'it',
  italian: 'it',
  italiano: 'it',
  tr: 'tr',
  'tr-tr': 'tr',
  tr_tr: 'tr',
  turkish: 'tr',
  türkçe: 'tr',
  ru: 'ru',
  'ru-ru': 'ru',
  ru_ru: 'ru',
  russian: 'ru',
  русский: 'ru',
  hi: 'hi',
  'hi-in': 'hi',
  hi_in: 'hi',
  hindi: 'hi',
  हिन्दी: 'hi',
  fa: 'fa',
  'fa-ir': 'fa',
  fa_ir: 'fa',
  persian: 'fa',
  farsi: 'fa',
  فارسی: 'fa',
  uk: 'uk',
  'uk-ua': 'uk',
  uk_ua: 'uk',
  ukrainian: 'uk',
  українська: 'uk',
  ko: 'ko',
  'ko-kr': 'ko',
  ko_kr: 'ko',
  korean: 'ko',
  한국어: 'ko',
  id: 'id',
  'id-id': 'id',
  id_id: 'id',
  indonesian: 'id',
  'bahasa indonesia': 'id',
  th: 'th',
  'th-th': 'th',
  th_th: 'th',
  thai: 'th',
  ไทย: 'th',
  vi: 'vi',
  'vi-vn': 'vi',
  vi_vn: 'vi',
  vietnamese: 'vi',
  'tiếng việt': 'vi',
  eo: 'eo',
  esperanto: 'eo',
  pl: 'pl',
  'pl-pl': 'pl',
  pl_pl: 'pl',
  polish: 'pl',
  polski: 'pl',
  nl: 'nl',
  'nl-nl': 'nl',
  nl_nl: 'nl',
  'nl-be': 'nl',
  nl_be: 'nl',
  dutch: 'nl',
  nederlands: 'nl',
  flemish: 'nl',
  ro: 'ro',
  'ro-ro': 'ro',
  ro_ro: 'ro',
  romanian: 'ro',
  română: 'ro',
  el: 'el',
  'el-gr': 'el',
  el_gr: 'el',
  greek: 'el',
  ελληνικά: 'el',
  cs: 'cs',
  'cs-cz': 'cs',
  cs_cz: 'cs',
  czech: 'cs',
  čeština: 'cs',
  sv: 'sv',
  'sv-se': 'sv',
  sv_se: 'sv',
  swedish: 'sv',
  svenska: 'sv',
  hu: 'hu',
  'hu-hu': 'hu',
  hu_hu: 'hu',
  hungarian: 'hu',
  magyar: 'hu',
  bg: 'bg',
  'bg-bg': 'bg',
  bg_bg: 'bg',
  bulgarian: 'bg',
  български: 'bg',
  da: 'da',
  'da-dk': 'da',
  da_dk: 'da',
  danish: 'da',
  dansk: 'da',
  fi: 'fi',
  'fi-fi': 'fi',
  fi_fi: 'fi',
  finnish: 'fi',
  suomi: 'fi',
  sk: 'sk',
  'sk-sk': 'sk',
  sk_sk: 'sk',
  slovak: 'sk',
  slovenčina: 'sk',
  no: 'no',
  'no-no': 'no',
  no_no: 'no',
  nb: 'no',
  'nb-no': 'no',
  norwegian: 'no',
  norsk: 'no',
  ga: 'ga',
  'ga-ie': 'ga',
  ga_ie: 'ga',
  irish: 'ga',
  gaeilge: 'ga',
  sl: 'sl',
  'sl-si': 'sl',
  sl_si: 'sl',
  slovenian: 'sl',
  slovenščina: 'sl'
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && LOCALE_OPTIONS.some(locale => locale.id === value)
}

export function normalizeLocale(value: unknown): Locale {
  if (typeof value !== 'string') {
    return DEFAULT_LOCALE
  }

  return LOCALE_ALIASES[normalize(value)] ?? DEFAULT_LOCALE
}

export function isSupportedLocaleValue(value: unknown): boolean {
  return typeof value === 'string' && LOCALE_ALIASES[normalize(value)] != null
}

export function localeConfigValue(locale: Locale): string {
  return LOCALE_OPTIONS.find(item => item.id === locale)?.configValue ?? DEFAULT_LOCALE
}
