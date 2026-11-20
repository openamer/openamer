// Upstream-Derived: apps/desktop/src/components/page-loader.tsx @ 51c68d4ab (MIT)
import type { ComponentProps } from 'react'

import { BrandLoader } from '@/components/ui/brand-loader'
import { cn } from '@/lib/utils'

interface PageLoaderProps extends Omit<ComponentProps<'div'>, 'children'> {
  label?: string
}

export function PageLoader({
  'aria-label': ariaLabel,
  className,
  label = 'Loading',
  role = 'status',
  ...props
}: PageLoaderProps) {
  return (
    <div
      {...props}
      aria-label={ariaLabel ?? label}
      className={cn('grid h-full place-items-center', className)}
      role={role}
    >
      <BrandLoader className="size-10 opacity-90" decorative />
    </div>
  )
}
