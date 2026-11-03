import { cn } from '../lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// Canonical OpenAmer O/A monogram, shared by setup and update screens.
// Keep public/openamer-logo.png in sync with docs/assets/openamer-logo.png.
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span className={cn('inline-flex size-14 shrink-0 items-center justify-center bg-white', className)} {...props}>
      <img alt="OpenAmer" className="size-full object-contain" src={assetPath('openamer-logo.png')} />
    </span>
  )
}
