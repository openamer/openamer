import type { SVGProps } from 'react'

import { cn } from '../../../utils'

export function HamburgerIcon({
  className,
  open = false,
  ...props
}: HamburgerIconProps) {
  return (
    <svg
      className={cn('size-5', className)}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
      {...props}
    >
      <line
        className="origin-center transition-transform duration-200 ease-out"
        style={{ transform: open ? 'rotate(45deg)' : 'translateY(-4px)' }}
        x1={4}
        x2={20}
        y1={12}
        y2={12}
      />

      <line
        className="transition-opacity duration-200 ease-out"
        style={{ opacity: open ? 0 : 1 }}
        x1={4}
        x2={20}
        y1={12}
        y2={12}
      />

      <line
        className="origin-center transition-transform duration-200 ease-out"
        style={{ transform: open ? 'rotate(-45deg)' : 'translateY(4px)' }}
        x1={4}
        x2={20}
        y1={12}
        y2={12}
      />
    </svg>
  )
}

interface HamburgerIconProps extends SVGProps<SVGSVGElement> {
  open?: boolean
}
