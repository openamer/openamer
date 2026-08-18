import { cva, type VariantProps } from 'class-variance-authority'
import { createElement } from 'react'

import { cn, type PolyProps, polyRef } from '../../../utils'

const typographyVariants = cva('font-sans', {
  variants: {
    compressed: { true: 'font-compressed' },
    courier: { true: 'font-courier' },
    expanded: { true: 'font-expanded' },
    mondwest: { true: 'font-mondwest tracking-[0.1875rem]' },
    mono: { true: 'font-mono' },
    sans: { true: 'font-sans' },
    variant: {
      lg: 'text-[2.625rem] leading-[1] tracking-[0.0525rem]',
      md: 'text-[2.625rem] leading-[1] tracking-[0.0525rem]',
      sm: 'leading-1.4 text-[.9375rem] tracking-[0.1875rem]',
      xl: 'text-[4.5rem] leading-[1] tracking-[0.135rem]'
    }
  }
})

export const Typography = polyRef<'span', OwnProps>(
  (
    {
      as,
      className,
      compressed,
      courier,
      expanded,
      mondwest,
      mono,
      variant,
      ...rest
    },
    ref
  ) => {
    const fonts = { compressed, courier, expanded, mondwest, mono }
    const fontVariant = { ...fonts, sans: !Object.values(fonts).some(Boolean) }

    return createElement((as ?? 'span') as React.ElementType, {
      ...rest,
      className: cn(typographyVariants({ ...fontVariant, variant }), className),
      ref
    })
  }
)

type OwnProps = VariantProps<typeof typographyVariants>

export type TypographyProps<T extends React.ElementType = 'span'> = PolyProps<
  T,
  OwnProps
>
