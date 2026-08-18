'use client'

import { createElement } from 'react'

import { cn, type PolyProps, polyRef } from '../../../utils'

export const FitText = polyRef<'span', OwnProps>(
  (
    { as, children, className, max, min = '1em', style: baseStyle, ...rest },
    ref
  ) => {
    if (typeof children !== 'string') {
      return null
    }

    const style = {
      '--fit-max': max ?? 'infinity * 1px',
      '--fit-min': min,
      ...baseStyle
    } as React.CSSProperties

    return createElement(
      (as ?? 'span') as React.ElementType,
      { ...rest, className: cn('fit-text', className), ref, style },
      <>
        <span>
          <span>{children}</span>
        </span>

        <span aria-hidden="true">{children}</span>
      </>
    )
  }
)

interface OwnProps {
  children: string
  max?: string
  min?: string
}

export type FitTextProps<T extends React.ElementType = 'span'> = PolyProps<
  T,
  OwnProps
>
