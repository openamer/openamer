import { ar } from './ar'
import { bg } from './bg'
import { bs } from './bs'
import { cs } from './cs'
import { da } from './da'
import { de } from './de'
import { el } from './el'
import { en } from './en'
import { eo } from './eo'
import { es } from './es'
import { et } from './et'
import { fa } from './fa'
import { fi } from './fi'
import { fr } from './fr'
import { ga } from './ga'
import { hi } from './hi'
import { hr } from './hr'
import { hu } from './hu'
import { id } from './id'
import { it } from './it'
import { ja } from './ja'
import { ko } from './ko'
import { lt } from './lt'
import { lv } from './lv'
import { nl } from './nl'
import { no } from './no'
import { pl } from './pl'
import { pt } from './pt'
import { ro } from './ro'
import { ru } from './ru'
import { sk } from './sk'
import { sl } from './sl'
import { sq } from './sq'
import { sv } from './sv'
import { th } from './th'
import { tr } from './tr'
import type { Locale, Translations } from './types'
import { uk } from './uk'
import { vi } from './vi'
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
  no,
  ga,
  sl,
  hr,
  et,
  lv,
  lt
}
