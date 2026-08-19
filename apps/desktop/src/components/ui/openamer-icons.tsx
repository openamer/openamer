/**
 * OpenAmer custom SVG icons — replaces the most visible Tabler icons
 * with OpenAmer's own visual identity.
 *
 * Uses forwardRef to be fully compatible with Tabler's IconComponent type.
 */

import * as React from 'react'
import { forwardRef } from 'react'

import { cn } from '@/lib/utils'

type IconProps = { className?: string; size?: string | number }

function s(size?: string | number): number {
  return typeof size === 'number' ? size : 24
}

function oa(
  render: (n: number) => React.ReactElement,
  name: string
) {
  const Icon = forwardRef<SVGSVGElement, IconProps>(
    ({ className, size, ...props }, ref) => {
      const n = s(size)

      return (
        <svg
          className={cn(className)}
          fill="none"
          height={n}
          ref={ref}
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          viewBox="0 0 24 24"
          width={n}
          xmlns="http://www.w3.org/2000/svg"
          {...props}
        >
          {render(n)}
        </svg>
      )
    }
  )

  Icon.displayName = name

  return Icon
}

// ── Chat / Messages: Hexagon with inner nodes ────────────────
export const OaChat = oa(() => (
  <>
    <path d="M21 16v-6a9 9 0 0 0-9-9" />
    <path d="M3 10v6a2 2 0 0 0 2 2h3l2 4 2-4h5a2 2 0 0 0 2-2" />
    <circle cx="10" cy="10" fill="currentColor" r="1" />
    <circle cx="14" cy="10" fill="currentColor" r="1" />
  </>
), 'OaChat')

// ── Skills / Brain: Neural network with hex nodes ────────────
export const OaSkills = oa(() => (
  <>
    <path d="M12 3a7 7 0 0 0-7 7v4a7 7 0 0 0 14 0v-4a7 7 0 0 0-7-7z" />
    <circle cx="8" cy="10" fill="currentColor" r="1.5" />
    <circle cx="16" cy="10" fill="currentColor" r="1.5" />
    <circle cx="12" cy="14" fill="currentColor" r="1.5" />
    <line x1="9" x2="11" y1="10" y2="14" />
    <line x1="15" x2="13" y1="10" y2="14" />
    <line x1="8" x2="16" y1="10" y2="10" />
  </>
), 'OaSkills')

// ── Settings: Hexagon gear ──────────────────────────────────
export const OaSettings = oa(() => (
  <>
    <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="12" cy="12" fill="currentColor" r="1.5" />
  </>
), 'OaSettings')

// ── Send: Arrow with hexagonal node ─────────────────────────
export const OaSend = oa(() => (
  <>
    <path d="M12 4v14" />
    <path d="M7 13l5 5 5-5" />
    <circle cx="12" cy="4" fill="currentColor" r="2" />
  </>
), 'OaSend')

// ── Search: Hexagon with magnifier ──────────────────────────
export const OaSearch = oa(() => (
  <>
    <path d="M10 5a5 5 0 1 0 4 8" />
    <circle cx="10" cy="10" r="5" />
    <path d="M20 20l-4.5-4.5" />
    <circle cx="10" cy="10" fill="currentColor" r="1.5" />
  </>
), 'OaSearch')

// ── Close / X: Hexagon with X ───────────────────────────────
export const OaClose = oa(() => (
  <>
    <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
    <line x1="9" x2="15" y1="9" y2="15" />
    <line x1="15" x2="9" y1="9" y2="15" />
  </>
), 'OaClose')

// ── Plus / Add: Hexagon with + ──────────────────────────────
export const OaPlus = oa(() => (
  <>
    <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
    <line x1="12" x2="12" y1="8" y2="16" />
    <line x1="8" x2="16" y1="12" y2="12" />
  </>
), 'OaPlus')

// ── Mic: Hexagon with mic ──────────────────────────────────
export const OaMic = oa(() => (
  <>
    <rect height="10" rx="2" width="4" x="10" y="3" />
    <path d="M6 12a6 6 0 0 0 12 0" />
    <path d="M12 19v3" />
  </>
), 'OaMic')

// ── Chevrons ────────────────────────────────────────────────
export const OaChevronDown = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <path d="M8 10l4 4 4-4" />
  </>
), 'OaChevronDown')

export const OaChevronLeft = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <path d="M14 8l-4 4 4 4" />
  </>
), 'OaChevronLeft')

export const OaChevronRight = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <path d="M10 8l4 4-4 4" />
  </>
), 'OaChevronRight')

// ── Attach ──────────────────────────────────────────────────
export const OaAttach = oa(() => (
  <>
    <path d="M6 12l6-6a3 3 0 0 1 4.5 4.5L8 18a1.5 1.5 0 0 1-2-2l8-8" />
  </>
), 'OaAttach')

// ── Pin ─────────────────────────────────────────────────────
export const OaPin = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" fill="currentColor" r="3" />
  </>
), 'OaPin')

// ── More / Dots ─────────────────────────────────────────────
export const OaMore = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="5" fill="currentColor" r="1.5" />
    <circle cx="12" cy="12" fill="currentColor" r="1.5" />
    <circle cx="12" cy="19" fill="currentColor" r="1.5" />
  </>
), 'OaMore')

// ── Check / Done ────────────────────────────────────────────
export const OaCheck = oa(() => (
  <>
    <circle cx="12" cy="12" r="8" />
    <path d="M9 12l2 2 4-4" />
  </>
), 'OaCheck')

// ── Message ─────────────────────────────────────────────────
export const OaMessage = oa(() => (
  <>
    <path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z" />
    <circle cx="12" cy="11" fill="currentColor" r="1" />
  </>
), 'OaMessage')