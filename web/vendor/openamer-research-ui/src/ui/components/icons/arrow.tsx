import type { SVGProps } from 'react'

import { cn } from '../../../utils'

export function ArrowIcon({
  className,
  direction = 'down',
  ...props
}: ArrowIconProps) {
  return (
    <svg
      className={cn(
        direction === 'up' && 'rotate-180',
        direction === 'left' && 'rotate-90',
        direction === 'right' && '-rotate-90',
        'origin-center',
        className
      )}
      fill="none"
      viewBox="0 0 13 15"
      {...props}
    >
      <path
        clipRule="evenodd"
        d="M5 15V0h2.50075v15z"
        fill="currentColor"
        fillRule="evenodd"
      />

      <path
        clipRule="evenodd"
        d="M10 12.5007H2.5V9.99998H10zM12.4976 9.99951H9.99805v-2.4996h2.49955zM2.4996 9.99951H0v-2.4996h2.4996z"
        fill="currentColor"
        fillRule="evenodd"
      />
    </svg>
  )
}

interface ArrowIconProps extends SVGProps<SVGSVGElement> {
  direction?: 'down' | 'left' | 'right' | 'up'
}
