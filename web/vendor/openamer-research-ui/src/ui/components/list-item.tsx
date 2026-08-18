'use client'

import { forwardRef, type ButtonHTMLAttributes } from 'react'

import { cn } from '../../utils'

export const ListItem = forwardRef<HTMLButtonElement, ListItemProps>(
  function ListItem(
    { active = false, children, className, type = 'button', ...props },
    ref
  ) {
    return (
      <button
        className={cn(
          'group relative flex w-full items-center gap-2 px-3 py-2 text-left',
          'font-courier text-sm transition-colors cursor-pointer',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground/30',
          'disabled:cursor-not-allowed disabled:text-text-disabled',
          active
            ? 'bg-midground/10 text-midground'
            : 'text-text-secondary hover:text-midground hover:bg-midground/5',
          className
        )}
        data-active={active || undefined}
        ref={ref}
        type={type}
        {...props}
      >
        {children}
      </button>
    )
  }
)

interface ListItemProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
}
