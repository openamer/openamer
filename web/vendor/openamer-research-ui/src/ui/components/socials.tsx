import { cn } from '../../utils'

export function Socials({ className, items, onNavigate, ...rest }: SocialsProps) {
  return (
    <div className={cn('flex items-center gap-3', className)} {...rest}>
      {items.map(({ external = true, href, icon: Icon, label, onClick }) => (
        <a
          className="opacity-60 transition-opacity hover:opacity-100"
          href={href}
          key={label}
          onClick={e => {
            onClick?.(e)
            onNavigate?.()
          }}
          rel={external ? 'noopener noreferrer' : undefined}
          target={external ? '_blank' : undefined}
          title={label}
        >
          <Icon />
        </a>
      ))}
    </div>
  )
}

export interface SocialLink {
  external?: boolean
  href: string
  icon: React.ComponentType<{ className?: string }>
  label: string
  onClick?: React.MouseEventHandler
}

interface SocialsProps extends React.HTMLAttributes<HTMLDivElement> {
  items: SocialLink[]
  /**
   * Called *in addition* to each link's `onClick` after a click — useful in
   * mobile drawer / dialog contexts where clicking a link should also close
   * the surrounding overlay.
   */
  onNavigate?: () => void
}
