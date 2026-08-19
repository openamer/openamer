/**
 * OpenAmer custom SVG icons.
 * Each icon wraps a ViewBox="0 0 24 24" SVG with a distinctive
 * hexagon-based shape, visibly different from Tabler's circular style.
 */
import * as React from 'react'

type Props = { className?: string; size?: string | number }

function Svg(children: React.ReactNode): React.ReactElement {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={24} height={24} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round"
    >
      {children}
    </svg>
  )
}

// ── Chat: hexagon ───────────────────────────────────────────
export function OaChat({ className, size }: Props) {
  return Svg(
    <>
      <path d="M21 16v-6a9 9 0 0 0-9-9" />
      <path d="M3 10v6a2 2 0 0 0 2 2h3l2 4 2-4h5a2 2 0 0 0 2-2" />
      <circle cx="10" cy="10" r="1" fill="currentColor" />
      <circle cx="14" cy="10" r="1" fill="currentColor" />
    </>
  )
}

// ── Skills: neural nodes ────────────────────────────────────
export function OaSkills({ className, size }: Props) {
  return Svg(
    <>
      <path d="M12 3a7 7 0 0 0-7 7v4a7 7 0 0 0 14 0v-4a7 7 0 0 0-7-7z" />
      <circle cx="8" cy="10" r="1.5" fill="currentColor" />
      <circle cx="16" cy="10" r="1.5" fill="currentColor" />
      <circle cx="12" cy="14" r="1.5" fill="currentColor" />
      <line x1="9" y1="10" x2="11" y2="14" />
      <line x1="15" y1="10" x2="13" y2="14" />
    </>
  )
}

// ── Settings: hexagon gear ──────────────────────────────────
export function OaSettings({ className, size }: Props) {
  return Svg(
    <>
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </>
  )
}

// ── Send: arrow ─────────────────────────────────────────────
export function OaSend({ className, size }: Props) {
  return Svg(
    <>
      <path d="M12 4v14" />
      <path d="M7 13l5 5 5-5" />
      <circle cx="12" cy="4" r="2" fill="currentColor" />
    </>
  )
}

// ── Search ──────────────────────────────────────────────────
export function OaSearch({ className, size }: Props) {
  return Svg(
    <>
      <circle cx="10" cy="10" r="5" />
      <path d="M20 20l-4.5-4.5" />
      <circle cx="10" cy="10" r="1.5" fill="currentColor" />
    </>
  )
}

// ── Close / X ───────────────────────────────────────────────
export function OaClose({ className, size }: Props) {
  return Svg(
    <>
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <line x1="9" y1="9" x2="15" y2="15" />
      <line x1="15" y1="9" x2="9" y2="15" />
    </>
  )
}

// ── Plus ────────────────────────────────────────────────────
export function OaPlus({ className, size }: Props) {
  return Svg(
    <>
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <line x1="12" y1="8" x2="12" y2="16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </>
  )
}

// ── Mic ─────────────────────────────────────────────────────
export function OaMic({ className, size }: Props) {
  return Svg(
    <>
      <rect x="10" y="3" width="4" height="10" rx="2" />
      <path d="M6 12a6 6 0 0 0 12 0" />
      <path d="M12 19v3" />
    </>
  )
}

// ── Chevrons ────────────────────────────────────────────────
export function OaChevronDown({ className, size }: Props) {
  return Svg(<><circle cx="12" cy="12" r="8" /><path d="M8 10l4 4 4-4" /></>)
}
export function OaChevronLeft({ className, size }: Props) {
  return Svg(<><circle cx="12" cy="12" r="8" /><path d="M14 8l-4 4 4 4" /></>)
}
export function OaChevronRight({ className, size }: Props) {
  return Svg(<><circle cx="12" cy="12" r="8" /><path d="M10 8l4 4-4 4" /></>)
}

// ── Pin ─────────────────────────────────────────────────────
export function OaPin({ className, size }: Props) {
  return Svg(<><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" fill="currentColor" /></>)
}

// ── More/Dots ───────────────────────────────────────────────
export function OaMore({ className, size }: Props) {
  return Svg(
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="5" r="1.5" fill="currentColor" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
      <circle cx="12" cy="19" r="1.5" fill="currentColor" />
    </>
  )
}

// ── Check ───────────────────────────────────────────────────
export function OaCheck({ className, size }: Props) {
  return Svg(<><circle cx="12" cy="12" r="8" /><path d="M9 12l2 2 4-4" /></>)
}

// ── Message ─────────────────────────────────────────────────
export function OaMessage({ className, size }: Props) {
  return Svg(
    <>
      <path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z" />
      <circle cx="12" cy="11" r="1" fill="currentColor" />
    </>
  )
}

// ── Attach ──────────────────────────────────────────────────
export function OaAttach({ className, size }: Props) {
  return Svg(<><path d="M6 12l6-6a3 3 0 0 1 4.5 4.5L8 18a1.5 1.5 0 0 1-2-2l8-8" /></>)
}