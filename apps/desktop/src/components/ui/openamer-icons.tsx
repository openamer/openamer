/**
 * OpenAmer custom SVG icons — replaces the most visible Tabler icons
 * with OpenAmer's own visual identity. Inspired by the eye / neural
 * motif in Eisblau (#00b4d8 / #48cae4).
 *
 * Each icon is wrapped with `toTablerIcon` so it matches the exact
 * Tabler `Icon` type used throughout the app.
 */

import type { Icon as IconComponent } from '@tabler/icons-react'
import * as React from 'react'

import { cn } from '@/lib/utils'

function s(size?: string | number): number {
  return typeof size === 'number' ? size : 24
}

function toTablerIcon(
  render: (n: number) => React.ReactElement
): IconComponent {
  const Icon: IconComponent = ({ className, size }: any) => {
    const n = s(size)

    return (
      <svg
        className={cn(className)}
        fill="none" height={n} stroke="currentColor"
        strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
        viewBox="0 0 24 24" width={n}
        xmlns="http://www.w3.org/2000/svg"
      >
        {render(n)}
      </svg>
    )
  }

  Icon.displayName = 'OaIcon'

  return Icon
}

// ── Chat bubble with eye ───────────────────────────────────────
export const OaChat: IconComponent = toTablerIcon(n => (
  <>
    <path d="M21 12a9 9 0 1 0-8.5 9" />
    <path d="M12 7a5 5 0 0 0-4.5 5 5 5 0 0 0 4.5 5" />
    <circle cx="12" cy="12" fill="currentColor" r="2" />
    <path d="M17 17l3 3" />
    <path d="M20 17l-3 3" />
  </>
))

// ── Skills / Brain with neural nodes ───────────────────────────
export const OaSkills: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="6" r="2" />
    <circle cx="6" cy="12" r="2" />
    <circle cx="18" cy="12" r="2" />
    <circle cx="12" cy="18" r="2" />
    <line x1="10" x2="7" y1="7" y2="11" />
    <line x1="14" x2="17" y1="7" y2="11" />
    <line x1="7" x2="10" y1="13" y2="17" />
    <line x1="17" x2="14" y1="13" y2="17" />
    <circle cx="12" cy="12" fill="currentColor" r="1" />
  </>
))

// ── Messaging / Mail ───────────────────────────────────────────
export const OaMessage: IconComponent = toTablerIcon(n => (
  <>
    <path d="M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" />
    <polyline points="22,7 12,13 2,7" />
    <circle cx="12" cy="13" fill="currentColor" r="1" />
  </>
))

// ── Settings / Gear eye ────────────────────────────────────────
export const OaSettings: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7" strokeDasharray="2 3" />
    <circle cx="12" cy="12" fill="currentColor" r="1.5" />
  </>
))

// ── Send / Arrow ───────────────────────────────────────────────
export const OaSend: IconComponent = toTablerIcon(n => (
  <>
    <path d="M3 12h14" />
    <path d="M12 5l7 7-7 7" />
    <circle cx="4" cy="12" fill="currentColor" r="1" />
  </>
))

// ── Search / Eye with scan ─────────────────────────────────────
export const OaSearch: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="11" cy="11" r="5" />
    <path d="M20 20l-4.5-4.5" />
    <circle cx="11" cy="11" fill="currentColor" r="2" />
  </>
))

// ── Attach / Paperclip ─────────────────────────────────────────
export const OaAttach: IconComponent = toTablerIcon(n => (
  <>
    <path d="M5 12l7-7a3 3 0 0 1 4.5 4.5L8 18a1.5 1.5 0 0 1-2-2l8-8" />
  </>
))

// ── Mic ────────────────────────────────────────────────────────
export const OaMic: IconComponent = toTablerIcon(n => (
  <>
    <rect height="11" rx="3" width="6" x="9" y="2" />
    <path d="M5 12a7 7 0 0 0 14 0" />
    <path d="M12 19v3" />
  </>
))

// ── Pin ────────────────────────────────────────────────────────
export const OaPin: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" fill="currentColor" r="3" />
    <line x1="12" x2="12" y1="4" y2="2" />
    <line x1="12" x2="12" y1="22" y2="20" />
  </>
))

// ── More / Dots ────────────────────────────────────────────────
export const OaMore: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="5" fill="currentColor" r="1.5" />
    <circle cx="12" cy="12" fill="currentColor" r="1.5" />
    <circle cx="12" cy="19" fill="currentColor" r="1.5" />
  </>
))

// ── Close / X ──────────────────────────────────────────────────
export const OaClose: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="12" r="8" />
    <line x1="9" x2="15" y1="9" y2="15" />
    <line x1="15" x2="9" y1="9" y2="15" />
  </>
))

// ── Plus / Add ─────────────────────────────────────────────────
export const OaPlus: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="12" r="8" />
    <line x1="12" x2="12" y1="8" y2="16" />
    <line x1="8" x2="16" y1="12" y2="12" />
  </>
))

// ── Check / Done ───────────────────────────────────────────────
export const OaCheck: IconComponent = toTablerIcon(n => (
  <>
    <circle cx="12" cy="12" r="8" />
    <polyline points="9,12 11,14 15,10" />
  </>
))

// ── Chevron Left ───────────────────────────────────────────────
export const OaChevronLeft: IconComponent = toTablerIcon(n => (
  <>
    <path d="M14 6l-6 6 6 6" />
  </>
))

// ── Chevron Right ──────────────────────────────────────────────
export const OaChevronRight: IconComponent = toTablerIcon(n => (
  <>
    <path d="M10 6l6 6-6 6" />
  </>
))

// ── Chevron Down ───────────────────────────────────────────────
export const OaChevronDown: IconComponent = toTablerIcon(n => (
  <>
    <path d="M6 10l6 6 6-6" />
  </>
))