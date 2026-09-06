import { ar } from './ar'
import { de } from './de'
import { en } from './en'
import { es } from './es'
import { ja } from './ja'
import { pt } from './pt'
import { bs } from './bs'
import { fr } from './fr'
import { it } from './it'
import { fa } from './fa'
import { id } from './id'
import { th } from './th'
import { ko } from './ko'
import { uk } from './uk'
import { hi } from './hi'
import { ru } from './ru'
import { tr } from './tr'
import { sq } from './sq'
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
  th
}
