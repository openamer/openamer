/*
 * Backdrop — the canvas every setup screen sits on.
 *
 * Three layers, all CSS, no images: two soft radial glows (one cool, one warm —
 * the palette's own two poles) and a very faint dot grid that gives the empty
 * space texture without reading as a pattern. `aria-hidden` because it carries
 * no information; the illustrations carry the meaning.
 */
export function Backdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-background" />
      <div className="installer-dots absolute inset-0 opacity-[0.35]" />
      <div className="installer-glow-cool absolute -top-40 -left-32 size-[38rem] rounded-full" />
      <div className="installer-glow-warm absolute -right-40 -bottom-48 size-[34rem] rounded-full" />
      <div className="absolute inset-0 bg-linear-to-b from-background/0 via-background/0 to-background/60" />
    </div>
  )
}
