/**
 * OpenAmer custom SVG icons — direct SVG components.
 * No wrapper, no forwardRef trickery — just plain SVG.
 */
import * as React from 'react'

type Props = { className?: string; size?: string | number }

function sz(s?: string | number): string {
  const n = typeof s === 'number' ? s : 24

  return `w-[${n}px] h-[${n}px]`
}

// ── Chat: hexagon with eye ──────────────────────────────────
export function OaChat({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M21 16v-6a9 9 0 0 0-9-9" />
      <path d="M3 10v6a2 2 0 0 0 2 2h3l2 4 2-4h5a2 2 0 0 0 2-2" />
      <circle cx="10" cy="10" fill="currentColor" r="1" />
      <circle cx="14" cy="10" fill="currentColor" r="1" />
    </svg>
  )
}

// ── Skills: neural nodes ────────────────────────────────────
export function OaSkills({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 3a7 7 0 0 0-7 7v4a7 7 0 0 0 14 0v-4a7 7 0 0 0-7-7z" />
      <circle cx="8" cy="10" fill="currentColor" r="1.5" />
      <circle cx="16" cy="10" fill="currentColor" r="1.5" />
      <circle cx="12" cy="14" fill="currentColor" r="1.5" />
      <line x1="9" x2="11" y1="10" y2="14" />
      <line x1="15" x2="13" y1="10" y2="14" />
    </svg>
  )
}

// ── Settings ─────────────────────────────────────────────────
export function OaSettings({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" fill="currentColor" r="1.5" />
    </svg>
  )
}

// ── Send ─────────────────────────────────────────────────────
export function OaSend({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 4v14" />
      <path d="M7 13l5 5 5-5" />
      <circle cx="12" cy="4" fill="currentColor" r="2" />
    </svg>
  )
}

// ── Search ───────────────────────────────────────────────────
export function OaSearch({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="10" cy="10" r="5" />
      <path d="M20 20l-4.5-4.5" />
      <circle cx="10" cy="10" fill="currentColor" r="1.5" />
    </svg>
  )
}

// ── Close ────────────────────────────────────────────────────
export function OaClose({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <line x1="9" x2="15" y1="9" y2="15" />
      <line x1="15" x2="9" y1="9" y2="15" />
    </svg>
  )
}

// ── Plus ─────────────────────────────────────────────────────
export function OaPlus({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2l2.5 3h4l1 3.5 3 2.5-1.5 3.5 1.5 3.5-3 2.5-1 3.5h-4L12 22l-2.5-3h-4l-1-3.5-3-2.5 1.5-3.5L1.5 9 4.5 6.5l1-3.5h4z" />
      <line x1="12" x2="12" y1="8" y2="16" />
      <line x1="8" x2="16" y1="12" y2="12" />
    </svg>
  )
}

// ── Mic ──────────────────────────────────────────────────────
export function OaMic({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect height="10" rx="2" width="4" x="10" y="3" />
      <path d="M6 12a6 6 0 0 0 12 0" />
      <path d="M12 19v3" />
    </svg>
  )
}

// ── Chevrons ─────────────────────────────────────────────────
export function OaChevronDown({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <path d="M8 10l4 4 4-4" />
    </svg>
  )
}

export function OaChevronLeft({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <path d="M14 8l-4 4 4 4" />
    </svg>
  )
}

export function OaChevronRight({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <path d="M10 8l4 4-4 4" />
    </svg>
  )
}

// ── Pin ──────────────────────────────────────────────────────
export function OaPin({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" fill="currentColor" r="3" />
    </svg>
  )
}

// ── More/Dots ────────────────────────────────────────────────
export function OaMore({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="5" fill="currentColor" r="1.5" />
      <circle cx="12" cy="12" fill="currentColor" r="1.5" />
      <circle cx="12" cy="19" fill="currentColor" r="1.5" />
    </svg>
  )
}

// ── Check ────────────────────────────────────────────────────
export function OaCheck({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="12" cy="12" r="8" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  )
}

// ── Message ──────────────────────────────────────────────────
export function OaMessage({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z" />
      <circle cx="12" cy="11" fill="currentColor" r="1" />
    </svg>
  )
}

// ── Attach ───────────────────────────────────────────────────
export function OaAttach({ className, size }: Props) {
  return (
    <svg
      className={className}
      fill="none" height={24} stroke="currentColor"
      strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      viewBox="0 0 24 24" width={24}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M6 12l6-6a3 3 0 0 1 4.5 4.5L8 18a1.5 1.5 0 0 1-2-2l8-8" />
    </svg>
  )
}