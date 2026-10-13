'use client'

import { type ReactNode } from 'react'

import { cn } from '../../utils'

export function Segmented<T extends string>({
  className,
  onChange,
  options,
  size = 'sm',
  value
}: SegmentedProps<T>) {
  return (
    <div
      className={cn(
        'inline-flex border border-midground/15 bg-background/30',
        className
      )}
      role="radiogroup"
    >
      {options.map(opt => {
        const active = opt.value === value

        return (
          <button
            aria-checked={active}
            className={cn(
              'font-mondwest text-display tracking-[0.1em]',
              'transition-colors cursor-pointer whitespace-nowrap',
              'border-r border-midground/15 last:border-r-0',
              'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30',
              size === 'sm' && 'h-7 px-2.5 text-xs',
              size === 'md' && 'h-8 px-3 text-xs',
              active
                ? 'bg-midground text-background'
                : 'text-text-secondary hover:bg-midground/10 hover:text-midground'
            )}
            key={opt.value}
            onClick={() => onChange(opt.value)}
            role="radio"
            type="button"
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export function FilterGroup({ children, className, label }: FilterGroupProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="font-mondwest text-display text-xs tracking-[0.12em] text-text-tertiary">
        {label}
      </span>

      {children}
    </div>
  )
}

interface FilterGroupProps {
  children: ReactNode
  className?: string
  label: string
}

interface SegmentedOption<T extends string> {
  label: string
  value: T
}

interface SegmentedProps<T extends string> {
  className?: string
  onChange: (value: T) => void
  options: SegmentedOption<T>[]
  size?: 'md' | 'sm'
  value: T
}
