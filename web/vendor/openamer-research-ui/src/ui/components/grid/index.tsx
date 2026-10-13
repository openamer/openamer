import { createElement } from 'react'

import { cn, polyRef } from '../../../utils'

export const Grid = polyRef<'div'>(({ as, className, ...rest }, ref) =>
  createElement((as ?? 'div') as React.ElementType, {
    ...rest,
    className: cn('g', className),
    ref
  })
)

export const Cell = polyRef<'div'>(({ as, className, ...rest }, ref) =>
  createElement((as ?? 'div') as React.ElementType, {
    ...rest,
    className: cn('gc', className),
    ref
  })
)
