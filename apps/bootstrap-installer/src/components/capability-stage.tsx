import clsx from 'clsx'
import { useEffect, useMemo, useState } from 'react'

import type { Capability } from '../i18n/strings'

import {
  HelixIllustration,
  LocalComputeIllustration,
  SkillGraphIllustration,
  ToolRunIllustration,
  WorldScriptsIllustration
} from './illustrations'

/*
 * CapabilityStage — the picture that shows what is being installed.
 *
 * A setup window is the one moment a person is paying full attention and has
 * nothing else to do, so it is the right place to say what the product is. Four
 * cards, one illustration each, advancing on their own every 4.5 s so nobody has
 * to click anything, and clickable dots for people who want to drive.
 *
 * Accessibility: the rotation stops for `prefers-reduced-motion`, the dots are
 * real buttons with labels, and the card text is plain DOM (not an image), so a
 * screen reader reads the whole claim.
 */
const ILLUSTRATIONS = [
  HelixIllustration,
  LocalComputeIllustration,
  WorldScriptsIllustration,
  SkillGraphIllustration
]

const ACCENTS = [
  'text-primary',
  'text-primary/85',
  'text-primary/80',
  'text-primary/85'
]

const ROTATE_MS = 4500

export function CapabilityStage({ capabilities }: { capabilities: Capability[] }) {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)

  const reduced = useMemo(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return false
    }

    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  }, [])

  useEffect(() => {
    if (reduced || paused || capabilities.length < 2) {
      return
    }

    const id = window.setTimeout(() => setIndex(i => (i + 1) % capabilities.length), ROTATE_MS)

    return () => window.clearTimeout(id)
  }, [capabilities.length, index, paused, reduced])

  const active = capabilities[index] ?? capabilities[0]

  if (!active) {
    return null
  }

  const Illustration = ILLUSTRATIONS[index % ILLUSTRATIONS.length] ?? ToolRunIllustration

  return (
    <div
      className="flex h-full flex-col justify-center gap-5"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div
        className={clsx(
          'installer-card relative flex h-[248px] shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-foreground/10 p-4',
          ACCENTS[index % ACCENTS.length]
        )}
      >
        <div className="installer-halo absolute inset-0" />
        <div className="relative h-full max-h-[212px] w-full max-w-[300px]" key={index}>
          <div className="installer-swap h-full w-full">
            <Illustration />
          </div>
        </div>
      </div>

      <div className="min-h-[100px]">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-[15px] font-semibold tracking-tight text-foreground" key={`t-${index}`}>
            {active.title}
          </h3>
          <span className="shrink-0 text-[10px] tabular-nums text-foreground/35">
            {index + 1}/{capabilities.length}
          </span>
        </div>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground" key={`b-${index}`}>
          {active.body}
        </p>
      </div>

      <div className="flex items-center gap-1.5">
        {capabilities.map((cap, i) => (
          <button
            aria-label={cap.title}
            aria-pressed={i === index}
            className={clsx(
              'h-1 cursor-pointer rounded-full transition-all duration-300',
              i === index ? 'w-6 bg-primary' : 'w-1.5 bg-foreground/20 hover:bg-foreground/35'
            )}
            key={cap.title}
            onClick={() => setIndex(i)}
            type="button"
          />
        ))}
      </div>
    </div>
  )
}
