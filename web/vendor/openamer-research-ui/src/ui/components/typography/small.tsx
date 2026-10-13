import { forwardRef } from 'react'

import { Typography, type TypographyProps } from '.'

export const Small = forwardRef<HTMLSpanElement, TypographyProps<any>>(
  (props, ref) => {
    return (
      <Typography as="small" mondwest variant="sm" {...{ ref, ...props }} />
    )
  }
)
