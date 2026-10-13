'use client'

import { type ButtonHTMLAttributes, forwardRef } from 'react'

import { cn } from '../../utils'

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(function Switch(
  { checked, className, disabled, id, onCheckedChange, ...props },
  ref
) {
  return (
    <button
      aria-checked={checked}
      className={cn(
        'peer inline-flex h-5 w-9 shrink-0 items-center border transition-colors cursor-pointer',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30',
        'disabled:cursor-not-allowed disabled:opacity-50',
        checked
          ? 'bg-midground/15 border-midground/30'
          : 'bg-background border-midground/20',
        className
      )}
      disabled={disabled}
      id={id}
      onClick={() => onCheckedChange(!checked)}
      ref={ref}
      role="switch"
      type="button"
      {...props}
    >
      <span
        aria-hidden
        className={cn(
          'pointer-events-none block h-3.5 w-3.5 transition-transform',
          checked
            ? 'translate-x-4 bg-midground'
            : 'translate-x-0.5 bg-midground/40'
        )}
      />
    </button>
  )
})

interface SwitchProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}
