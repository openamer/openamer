import { cn } from '../../utils'

import { BlendMode, type BlendModeProps } from './blend-mode'

const BASE_CN =
  'inline-flex items-center font-compressed text-display px-2 py-1 leading-none tracking-[0.2em]'

const TONE_CLASSES: Record<Exclude<Tone, 'default'>, string> = {
  destructive:
    'border border-destructive/30 bg-destructive/15 text-destructive',
  outline: 'border border-midground/30 bg-transparent text-midground/80',
  secondary: 'border border-midground/15 bg-midground/8 text-midground',
  success: 'border border-success/30 bg-success/15 text-success',
  warning: 'border border-warning/30 bg-warning/15 text-warning'
}

export const Badge = ({
  className,
  style,
  tone = 'default',
  ...props
}: BadgeProps) => {
  // `tone="default"` keeps the original Lens-aware BlendMode treatment so
  // existing brand-style consumers (openamernet-web etc.) render unchanged.
  if (tone === 'default') {
    return (
      <BlendMode
        as="span"
        background="mg/0.075"
        className={cn(BASE_CN, className)}
        color="mg"
        style={{ opacity: 'var(--midground-alpha)', ...style }}
        {...(props as BlendModeProps<'span'>)}
      />
    )
  }

  // Semantic tones bypass BlendMode and use --color-* tokens directly so
  // red stays red and green stays green regardless of the active Lens.
  return (
    <span
      className={cn(BASE_CN, TONE_CLASSES[tone], className)}
      style={style}
      {...(props as React.HTMLAttributes<HTMLSpanElement>)}
    />
  )
}

type Tone =
  | 'default'
  | 'destructive'
  | 'outline'
  | 'secondary'
  | 'success'
  | 'warning'

interface BadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'color'> {
  tone?: Tone
}
