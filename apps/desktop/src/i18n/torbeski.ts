import { defineLocale } from './define-locale'

// Torbeški (torbeski). BASE: inherited from Macedonian (mk) in the CLI
// catalog; this desktop module is still empty, so it falls back to English.
// Torbeški has no standard written norm and no ISO code of its own, and no MT
// system produces it -- native strings must be supplied, not generated here.
export const torbeski = defineLocale({})
