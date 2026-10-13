import { forwardRef } from 'react'

import { cn } from '../../../utils'

import { Typography, type TypographyProps } from '.'

export const H1 = forwardRef<HTMLHeadingElement, TypographyProps<'h1'>>(
  ({ className, ...props }, ref) => {
    return (
      <Typography
        as="h1"
        className={cn('font-bold', className)}
        variant="xl"
        {...{ ref, ...props }}
      />
    )
  }
)
