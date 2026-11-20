import { useId } from 'react'

import { cn } from '@/lib/utils'

interface BrandLoaderProps extends Omit<React.ComponentProps<'span'>, 'children'> {
  /**
   * Render as decoration only: no `role="status"`, no accessible name.
   *
   * Use this when the loader sits inside a row that is itself the live region,
   * so the label is announced once instead of twice.
   */
  decorative?: boolean
  /** Accessible name announced while the loader is up. */
  label?: string
}

/**
 * OpenAmer's own loading mark — the O/A monogram drawing itself.
 *
 * The brand mark is an O enclosing an A (same master as the app icon). Every
 * other loader in this app renders a generic math curve from
 * `unicode-animations`, which any product could have; this one is ours: a
 * permanent O track, a sweeping arc that traces it, and an A that writes itself
 * in two strokes, holds, and erases. Nothing is borrowed.
 *
 * Geometry and colours are lifted from `public/openamer.png` (ring radius
 * 0.742·R, ring stroke 0.086·size, A box 0.38 × 0.40 of the tile, gradient
 * #5DEBFA → #17BFBA on the top-left → bottom-right diagonal), so the loader
 * reads as the same mark as the taskbar icon.
 *
 * Motion lives in `styles.css` (`.oa-loader*`), including a reduced-motion
 * branch that pins the finished mark instead of freezing it mid-erase.
 */
export function BrandLoader({ className, decorative = false, label = 'Loading', ...props }: BrandLoaderProps) {
  // React ids contain characters that are not safe inside `url(#…)` fragments.
  const gradientId = `oa-loader-gradient-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const gradient = `url(#${gradientId})`

  return (
    <span
      {...props}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : (props['aria-label'] ?? label)}
      className={cn('oa-loader inline-grid size-[1.15em] shrink-0 place-items-center', className)}
      data-slot="brand-loader"
      role={decorative ? undefined : 'status'}
    >
      <svg aria-hidden="true" className="block size-full overflow-visible" fill="none" viewBox="0 0 48 48">
        <defs>
          <linearGradient gradientUnits="userSpaceOnUse" id={gradientId} x1="6" x2="42" y1="6" y2="42">
            <stop offset="0" stopColor="var(--oa-loader-from)" />
            <stop offset="1" stopColor="var(--oa-loader-to)" />
          </linearGradient>
        </defs>

        {/* The O: a permanent faint track plus the arc that sweeps it. */}
        <circle className="oa-loader-ring-track" cx="24" cy="24" r="17.8" stroke={gradient} strokeWidth="4.1" />
        <circle
          className="oa-loader-ring-sweep"
          cx="24"
          cy="24"
          pathLength={100}
          r="17.8"
          stroke={gradient}
          strokeDasharray="30 70"
          strokeLinecap="round"
          strokeWidth="4.1"
        />

        {/* The A: two strokes, written in sequence. `pathLength` normalises both
            to 0–100 so the dash window in CSS is independent of real length. */}
        <path
          className="oa-loader-a-legs"
          d="M14.9 32.7 24 13.3 33.1 32.7"
          pathLength={100}
          stroke={gradient}
          strokeDasharray="100"
          strokeDashoffset="100"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3.7"
        />
        <path
          className="oa-loader-a-bar"
          d="M19.4 26.9h9.2"
          pathLength={100}
          stroke={gradient}
          strokeDasharray="100"
          strokeDashoffset="100"
          strokeLinecap="round"
          strokeWidth="3.7"
        />
      </svg>
    </span>
  )
}
