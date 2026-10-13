import { cn } from '../../utils'

/**
 * Themeable card primitive. Themes can restyle every card by setting CSS
 * custom properties:
 *
 *   --component-card-clip-path
 *   --component-card-border-image
 *   --component-card-background
 *   --component-card-box-shadow
 *
 * All are optional — unset vars compute to their CSS initial value.
 */
const CARD_STYLE: React.CSSProperties = {
  background: 'var(--component-card-background)',
  borderImage: 'var(--component-card-border-image)',
  boxShadow: 'var(--component-card-box-shadow)',
  clipPath: 'var(--component-card-clip-path)'
}

export function Card({
  className,
  style,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'border border-midground/15 bg-background-base/80 text-midground w-full',
        className
      )}
      style={{ ...CARD_STYLE, ...style }}
      {...props}
    />
  )
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 p-4 border-b border-midground/15',
        className
      )}
      {...props}
    />
  )
}

export function CardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        'font-expanded text-sm font-bold tracking-[0.08em] uppercase',
        className
      )}
      {...props}
    />
  )
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn('font-mondwest text-xs text-midground/60', className)}
      {...props}
    />
  )
}

export function CardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />
}
