import React, { ReactNode } from 'react'

import { cn } from '../../utils'

import { Typography } from './typography'

export function Stats({ className, items, flip, ...props }: StatsProps) {
  return (
    <div className={cn('flex w-full flex-col gap-5', className)} {...props}>
      {items.map(({ label, value }) => {
        const valueText = (
          <Typography
            className="text-xs leading-[1.4] tracking-widest"
            expanded
          >
            {typeof value === 'string' ? value : value.node}
          </Typography>
        )
        const labelText = (
          <Typography className="leading-none tracking-[0.2em] opacity-60" mono>
            {typeof label === 'string' ? label : label.node}
          </Typography>
        )

        return (
          <div
            className="text-midground text-display grid grid-cols-[auto_1fr_auto] items-center gap-2.5"
            key={(typeof label === 'string' ? label : label.key ) + '@@@'+(typeof value === 'string' ? value : value.key)}
          >
            {flip ? labelText : valueText}

            <Typography
              className="min-w-0 overflow-hidden text-[13px] leading-[1.4] tracking-[0.4em] opacity-20"
              expanded
            >
              {'·'.repeat(100)}
            </Typography>

            {flip ? valueText : labelText}
          </div>
        )
      })}
    </div>
  )
}

interface StatsProps extends React.ComponentProps<'div'> {
  items: {
    label: string | {key: string, node: ReactNode}
    value: string | {key: string, node: ReactNode}
  }[]
  flip?: boolean
}
