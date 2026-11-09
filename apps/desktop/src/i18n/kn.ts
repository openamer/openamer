import { defineLocale } from './define-locale'

// Kannada (kn). Partial on purpose: every string not listed here
// falls back to English via defineLocale, so the app is fully usable before
// this catalog is translated. Fill in overrides as translations land.
export const kn = defineLocale({})
