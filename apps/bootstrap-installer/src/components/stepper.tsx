import clsx from 'clsx'
import { Check } from 'lucide-react'

import { cn } from '../lib/utils'

/*
 * Stepper — the "where am I" line an OS installer always has.
 *
 * Steps are passed in rather than derived from a fixed total: an install runs
 * four (language, welcome, install, ready) and an update runs three (update,
 * install, ready). Baking a number into the component made the update path
 * claim a step it never shows.
 */
export interface StepperProps {
  className?: string
  current: number
  steps: string[]
}

export function Stepper({ className, current, steps }: StepperProps) {
  return (
    <ol aria-label="Setup progress" className={cn('flex items-center gap-2 text-[11px]', className)}>
      {steps.map((label, i) => {
        const state = i < current ? 'past' : i === current ? 'active' : 'future'

        return (
          <li className="flex items-center gap-2" key={`${label}-${i}`}>
            {i > 0 && (
              <span
                aria-hidden="true"
                className={cn('h-px w-6', state === 'future' ? 'bg-foreground/15' : 'bg-foreground/35')}
              />
            )}
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className={clsx(
                  'flex size-4 items-center justify-center rounded-full border text-[9px] font-semibold tabular-nums',
                  state === 'past' && 'border-foreground/30 bg-foreground/10 text-foreground/60',
                  state === 'active' && 'border-primary bg-primary/15 text-primary',
                  state === 'future' && 'border-foreground/15 text-foreground/35'
                )}
              >
                {state === 'past' ? <Check className="text-current" size={9} /> : i + 1}
              </span>
              <span
                className={clsx(
                  'whitespace-nowrap tracking-tight',
                  state === 'active' && 'font-medium text-foreground',
                  state === 'past' && 'text-foreground/55',
                  state === 'future' && 'text-foreground/35'
                )}
              >
                {label}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
