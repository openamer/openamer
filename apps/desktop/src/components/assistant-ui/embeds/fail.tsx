// Upstream-Derived: apps/desktop/src/components/assistant-ui/embeds/fail.tsx @ 81ac562bf (MIT)
export function EmbedFail({ label }: { label: string }) {
  return (
    <span className="grid min-h-32 w-full place-items-center p-4">
      <span className="text-xs font-medium text-(--ui-red)">Failed to load {label} embed</span>
    </span>
  )
}
