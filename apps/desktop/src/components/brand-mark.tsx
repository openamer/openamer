import { cn } from '@/lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// Brand badge: the OpenAmer eye mark (openamer.png — same art as the taskbar
// icon), identical in light/dark. Fills the tile (softly rounded); size via
// className (default size-14).
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'inline-flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-md bg-white',
        className
      )}
      {...props}
    >
      <img
        alt=""
        className="size-full object-contain"
        src={assetPath('openamer.png')}
      />
    </span>
  )
}
