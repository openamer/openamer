import { ar } from './ar'
import { cs } from './cs'
import { da } from './da'
import { de } from './de'
import { el } from './el'
import { eo } from './eo'
import { nl } from './nl'
import { no } from './no'
import { pl } from './pl'
import { en } from './en'
import { es } from './es'
import { fi } from './fi'
import { ja } from './ja'
import { pt } from './pt'
import { ro } from './ro'
import { bg } from './bg'
import { bs } from './bs'
import { fr } from './fr'
import { it } from './it'
import { fa } from './fa'
import { id } from './id'
import { th } from './th'
import { vi } from './vi'
import { ko } from './ko'
import { uk } from './uk'
import { hi } from './hi'
import { hu } from './hu'
import { ru } from './ru'
import { tr } from './tr'
import { sk } from './sk'
import { sq } from './sq'
import { sv } from './sv'
import type { Locale, Translations } from './types'
import { zh } from './zh'
import { zhHant } from './zh-hant'

export const TRANSLATIONS: Record<Locale, Translations> = {
  en,
  zh,
  'zh-hant': zhHant,
  ja,
  ar,
  de,
  es,
  pt,
  sq,
  bs,
  fr,
  it,
  tr,
  ru,
  hi,
  fa,
  uk,
  ko,
  id,
  th,
  vi,
  eo,
  pl,
  nl,
  ro,
  el,
  cs,
  sv,
  hu,
  bg,
  da,
  fi,
  sk,
  no
}
