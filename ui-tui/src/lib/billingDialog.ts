import type { BillingBlock } from '@openamer/shared/billing'

export interface BillingDialogCopy {
  cancelLabel: string
  confirmLabel: string
  detail: string
  title: string
}

/**
 * Copy for the out-of-credits confirm dialog (the TUI's billing wall). The
 * dialog is the actionable layer — the full provider guidance already lands in
 * the transcript — so `detail` stays to one concise, non-truncating line and the
 * confirm button carries the recovery: OpenAmer → `/topup`, other providers → their
 * billing page (or `/model` to switch when we have no URL). Pure + exported so
 * the wording is unit-tested without driving the gateway.
 */
export function billingDialogCopy(block: BillingBlock): BillingDialogCopy {
  if (block.is_openamer) {
    return {
      cancelLabel: 'Dismiss',
      confirmLabel: 'Top up',
      detail: 'Your OpenAmer credit balance is exhausted — top up to keep going.',
      title: 'Out of OpenAmer credits'
    }
  }

  const label = block.provider_label || 'your provider'

  return {
    cancelLabel: 'Dismiss',
    confirmLabel: block.billing_url ? 'Open billing page' : 'Switch provider',
    detail: `${label} reports your credits or billing are exhausted.`,
    title: `Out of credits · ${label}`
  }
}
