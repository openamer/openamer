// Upstream-Derived: apps/desktop/src/app/settings/billing/open-external.ts @ 60ec6a3b8 (MIT)
import { openExternalLink } from '@/lib/external-link'

// Optional-arg convenience over the canonical opener — the billing rows pass
// possibly-undefined URLs straight through from their view models.
export function openExternal(url?: string) {
  if (url) {
    openExternalLink(url)
  }
}
