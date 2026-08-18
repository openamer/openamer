import { cn } from '../../../utils'

import { Small } from './small'

export function Legend({
  children,
  className,
  label,
  sub,
  ...props
}: LegendProps) {
  return (
    <hgroup className={cn('flex flex-col gap-2', className)} {...props}>
      <Small>{label}</Small>
      {sub && <Small className="opacity-50">- {sub}</Small>}
      {children}
    </hgroup>
  )
}

interface LegendProps extends React.ComponentProps<'hgroup'> {
  label: React.ReactNode
  sub?: React.ReactNode
}
