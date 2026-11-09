import { defineLocale } from './define-locale'

// Church Slavic (cu). Partial on purpose: every string not listed here
// falls back to English via defineLocale, so the app is fully usable before
// this catalog is translated. Fill in overrides as translations land.
export const cu = defineLocale({})
