import { forwardRef } from 'react'

import { cn } from '../../../utils'

import { Typography, type TypographyProps } from '.'

export const H2 = forwardRef<HTMLHeadingElement, TypographyProps<'h2'>>(
  ({ className, ...props }, ref) => {
    return (
      <Typography
        as="h2"
        className={cn('font-bold', className)}
        variant="lg"
        {...{ ref, ...props }}
      />
    )
  }
)
