import clsx from 'clsx'
import { Check } from 'lucide-react'

import { cn } from '../lib/utils'

/*
 * Stepper — the "where am I" line an OS installer always has.
 *
 * Three steps, not four: welcome / install / ready. The failure screen keeps the
 * same stepper with step 2 marked as the one that stopped, so a person never
 * loses their place. Update mode collapses to two visible steps because there is
 * no provider onboarding afterwards.
 */
export interface StepperProps {
  className?: string
  current: 0 | 1 | 2
  labels: { done: string; install: string; update: string; welcome: string }
  update?: boolean
}

export function Stepper({ className, current, labels, update = false }: StepperProps) {
  const steps = [
    { key: 'welcome', label: update ? labels.update : labels.welcome },
    { key: 'install', label: labels.install },
    { key: 'done', label: labels.done }
  ]

  return (
    <ol aria-label="Setup progress" className={cn('flex items-center gap-2 text-[11px]', className)}>
      {steps.map((step, i) => {
        const state = i < current ? 'past' : i === current ? 'active' : 'future'

        return (
          <li className="flex items-center gap-2" key={step.key}>
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
                  'tracking-tight',
                  state === 'active' && 'font-medium text-foreground',
                  state === 'past' && 'text-foreground/55',
                  state === 'future' && 'text-foreground/35'
                )}
              >
                {step.label}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
