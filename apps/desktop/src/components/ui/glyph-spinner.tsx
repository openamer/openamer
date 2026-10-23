import { useEffect, useState } from 'react'
import spinners, { type BrailleSpinnerName as SpinnerName } from 'unicode-animations'

import { usePaneVisible } from '@/components/pane-shell/pane-visibility'
import { cn } from '@/lib/utils'

export type { SpinnerName }

interface NormalisedSpinner {
  frames: readonly string[]
  interval: number
}

// Some spinners ship multi-character frames. Pull the first cell so each
// frame fits in one monospace box — matches how the TUI uses them.
const FRAMES_BY_NAME: Record<SpinnerName, NormalisedSpinner> = (() => {
  const out = {} as Record<SpinnerName, NormalisedSpinner>

  for (const name of Object.keys(spinners) as SpinnerName[]) {
    const raw = spinners[name]

    out[name] = {
      frames: raw.frames.map(frame => [...frame][0] ?? '⠀'),
      interval: raw.interval
    }
  }

  return out
})()

interface GlyphSpinnerProps {
  ariaLabel?: string
  className?: string
  /**
   * Render as decoration only: no `role="status"`, no accessible name.
   *
   * Use this when the spinner sits inside a row that is itself the live region
   * (e.g. the thread status row, which already carries `role="status"` and the
   * label). Two nested `status` regions both announce, and the accessible name
   * becomes ambiguous for `getByRole('status', { name })` — one surface, one
   * announcement.
   */
  decorative?: boolean
  spinner?: SpinnerName
}

/**
 * One-char glyph spinner driven by `unicode-animations` (braille, orbit, scan,
 * etc. — pick any `spinner` name). Mirrors the spinner used by the Ink TUI so
 * the desktop and terminal experiences read the same visually. Renders inside
 * an `inline-flex` cell with `leading-none` and `items-center` so it sits
 * vertically centred inside its parent's line-box.
 */
export function GlyphSpinner({
  ariaLabel = 'Loading',
  className,
  decorative = false,
  spinner = 'braille'
}: GlyphSpinnerProps) {
  const spin = FRAMES_BY_NAME[spinner] ?? FRAMES_BY_NAME.braille!
  const [frame, setFrame] = useState(0)
  // Pause when this surface is a hidden (kept-alive) tab: N mounted tabs each
  // ticking a setInterval + setState burn CPU for pixels nobody can see.
  const visible = usePaneVisible()

  useEffect(() => {
    if (!visible) {
      return
    }

    setFrame(0)
    const id = window.setInterval(() => setFrame(f => (f + 1) % spin.frames.length), spin.interval)

    return () => window.clearInterval(id)
  }, [spin, visible])

  const cellClass = cn('inline-flex items-center justify-center font-mono leading-none tabular-nums', className)

  if (decorative) {
    return (
      <span aria-hidden="true" className={cellClass}>
        {spin.frames[frame]}
      </span>
    )
  }

  return (
    <span aria-label={ariaLabel} className={cellClass} role="status">
      {spin.frames[frame]}
    </span>
  )
}
