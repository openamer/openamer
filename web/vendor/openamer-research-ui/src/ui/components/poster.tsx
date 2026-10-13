'use client'

import { useEffect, useState } from 'react'

import fillerBg from '../../assets/filler-bg0.webp'
import { cn } from '../../utils'

import { Blink } from './blink'
import { ImageDistortion } from './image-distortion'
import { Typography } from './typography'
import { Small } from './typography/small'

import type { AutoPlayPattern } from './image-distortion'

const ASPECT_CONFIG: Record<
  PosterAspect,
  { defaultLayout: 'split' | 'stacked'; height: number; width: number }
> = {
  landscape: { defaultLayout: 'split', height: 1080, width: 1920 },
  portrait: { defaultLayout: 'split', height: 1350, width: 1080 },
  square: { defaultLayout: 'split', height: 1080, width: 1080 },
  story: { defaultLayout: 'stacked', height: 1920, width: 1080 },
  wide: { defaultLayout: 'split', height: 900, width: 1600 }
}

const DEFAULT_SRC =
  (fillerBg as { src?: string }).src ?? (fillerBg as unknown as string)

function useUtcClock() {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
    const id = setInterval(() => setNow(new Date()), 1000)

    return () => clearInterval(id)
  }, [])

  return now ? now.toISOString().slice(11, 19) : '--:--:--'
}

function CornerMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'pointer-events-none absolute block size-4 opacity-50',
        className
      )}
    >
      <span className="absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-current" />

      <span className="absolute top-0 left-1/2 h-full w-px -translate-x-1/2 bg-current" />
    </span>
  )
}

function ChannelDot() {
  return (
    <span className="flex items-center gap-1.5">
      <span className="bg-midground size-1.5 animate-pulse rounded-full" />

      <Small className="opacity-70">REC</Small>
    </span>
  )
}

function ScanlineOverlay() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 opacity-20 mix-blend-overlay"
      style={{
        backgroundImage:
          'repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(255,255,255,0.08) 2px, rgba(255,255,255,0.08) 3px)'
      }}
    />
  )
}

/**
 * Social-ready glitchy card built around the haptic-distortion image
 * component. The poster runs the sword-guy distortion on an auto-animated
 * slash pattern so it can be screen-recorded as a GIF without a human
 * moving a cursor.
 *
 * Two variants, matching actual use cases:
 * - `'vibe'` (default): full-bleed distorted image with just registration
 *   marks and a tiny "OpenAmer Agent" mark in the corner — mirrors the
 *   overlay on the OpenAmer agent website.
 * - `'dispatch'`: broadcast-card layout with sidebar copy, numbered tags,
 *   and chrome — for when the poster needs to carry information.
 */
export function Poster({
  aspect = 'square',
  autoPlay = 'slash',
  body,
  border = true,
  channel,
  children,
  className,
  cornerMarks = true,
  eyebrow,
  headline = ['An Agent', 'That Grows', 'With You.'],
  layout,
  scale = 1,
  seal = 'MIT · 2026',
  signature,
  src = DEFAULT_SRC,
  tags,
  tint,
  tintStrength,
  variant = 'vibe',
  ...rest
}: PosterProps) {
  const config = ASPECT_CONFIG[aspect]
  const resolvedLayout = layout ?? config.defaultLayout

  // Use aspect-ratio + max-width/height so the poster fluidly fits any parent
  // (storybook iframe, a tweet preview, an embed) without getting clipped,
  // but caps at the intended export width for screen-recording. `maxHeight`
  // uses an absolute `dvh`-based value rather than `%` because `%` inside a
  // flex container can cause the browser to clamp height without re-running
  // aspect-ratio on width, producing a subtly wrong shape. An absolute cap
  // leaves aspect-ratio fully in charge: once the height binds, width is
  // re-derived correctly. `calc(100dvh - 8rem)` = viewport minus a typical
  // host's vertical padding (e.g. Storybook's `p-8` = 4rem on each side),
  // so the poster + padding fit within the viewport without ever producing
  // scrollbars. Container queries tie all internal typography to the
  // actual rendered width so headline/metadata scales along with the canvas.
  const outerProps = {
    // `text-midground` (not `text-foreground`) is the readable on-canvas
    // color across every lens. `--foreground` is really the lens's inversion
    // layer color: on dark lenses it has `fgOpacity: 0` and resolves to
    // fully-transparent via `color-mix`, which would make text invisible.
    // `--midground` always has opacity 1 and picks up each lens's accent.
    className: cn(
      'text-midground relative overflow-hidden font-sans',
      border && 'border border-current/25',
      className
    ),
    style: {
      aspectRatio: `${config.width} / ${config.height}`,
      background: 'var(--background)',
      containerType: 'inline-size' as const,
      fontSize: `${(16 / config.width) * 100}cqi`,
      maxHeight: 'calc(100dvh - 8rem)',
      maxWidth: '100%',
      width: `${config.width * scale}px`
    },
    ...rest
  }

  if (variant === 'vibe') {
    return (
      <div {...outerProps}>
        <VibeContent
          autoPlay={autoPlay}
          channel={channel}
          cornerMarks={cornerMarks}
          signature={signature}
          src={src}
          tint={tint}
          tintStrength={tintStrength}
        />
      </div>
    )
  }

  const headlineLines = Array.isArray(headline) ? headline : [headline]

  return (
    <div {...outerProps} className={cn('flex flex-col', outerProps.className)}>
      <DispatchHeader channel={channel} />

      <div
        className={cn(
          'relative min-h-0 min-w-0 flex-1',
          resolvedLayout === 'split'
            ? 'grid grid-cols-[3fr_2fr]'
            : 'grid grid-rows-[3fr_2fr]'
        )}
      >
        <div
          className={cn(
            'relative overflow-hidden border-current/20',
            resolvedLayout === 'split' ? 'border-r' : 'border-b'
          )}
          style={{ backgroundColor: 'var(--background)' }}
        >
          <ImageDistortion
            autoPlay={autoPlay}
            src={src}
            tint={tint}
            tintStrength={tintStrength}
          />

          {cornerMarks && (
            <>
              <CornerMark className="top-3 left-3" />
              <CornerMark className="top-3 right-3" />
              <CornerMark className="bottom-3 left-3" />
              <CornerMark className="right-3 bottom-3" />
            </>
          )}

          <ScanlineOverlay />

          <Small className="absolute bottom-4 left-4 z-1 opacity-80">
            OpenAmer Agent
          </Small>
        </div>

        <aside className="relative flex min-w-0 flex-col justify-between gap-8 p-8">
          <div className="flex flex-col gap-5">
            {eyebrow && (
              <div className="flex items-center gap-2">
                <span className="bg-midground/80 h-px flex-1" />

                <Small className="opacity-80">{eyebrow}</Small>
              </div>
            )}

            {children ?? (
              <>
                <Typography
                  as="h1"
                  className="text-[2.75em] leading-[0.95] font-bold tracking-[-0.01em]"
                  expanded
                >
                  {headlineLines.map((line, i) => (
                    <span className="block" key={`${line}-${i}`}>
                      {line}
                    </span>
                  ))}
                </Typography>

                {body && (
                  <p className="text-[1.0625em] leading-[1.5] tracking-normal normal-case opacity-60">
                    {body}
                  </p>
                )}
              </>
            )}
          </div>

          {tags && tags.length > 0 && (
            <ul className="flex flex-col gap-2 border-t border-current/15 pt-4">
              {tags.map((tag, i) => (
                <li
                  className="flex items-baseline justify-between gap-3"
                  key={`${tag}-${i}`}
                >
                  <Small className="font-courier opacity-40">
                    {String(i + 1).padStart(3, '0')}
                  </Small>

                  <Small className="opacity-80">{tag}</Small>

                  <span className="mx-1 h-px flex-1 translate-y-[-3px] border-b border-dotted border-current/25" />

                  <Small className="font-courier opacity-40">
                    {String(i + 1).padStart(2, '0')}/
                    {String(tags.length).padStart(2, '0')}
                  </Small>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <footer className="flex items-center justify-between gap-4 border-t border-current/20 px-6 py-3">
        <Small className="opacity-70">
          {signature}

          <Blink />
        </Small>

        <Small className="font-courier opacity-40">{seal}</Small>
      </footer>
    </div>
  )
}

function DispatchHeader({ channel }: { channel: React.ReactNode }) {
  const clock = useUtcClock()

  return (
    <header className="flex items-center justify-between gap-4 border-b border-current/20 px-6 py-3">
      <div className="flex items-center gap-3">
        <span className="bg-midground size-2 rounded-sm opacity-70" />

        <Small className="opacity-70">{channel}</Small>
      </div>

      <div className="flex items-center gap-4">
        <ChannelDot />

        <Small className="font-courier opacity-50">{clock} UTC</Small>
      </div>
    </header>
  )
}

interface VibeContentProps {
  autoPlay: AutoPlayPattern
  channel: React.ReactNode
  cornerMarks: boolean
  signature: React.ReactNode
  src: string
  tint?: string
  tintStrength?: { active: number; inactive: number }
}

function VibeContent({
  autoPlay,
  channel,
  cornerMarks,
  signature,
  src,
  tint,
  tintStrength
}: VibeContentProps) {
  // Absolute-inset-0 guarantees this fills the poster even when the outer
  // container uses aspect-ratio-derived height in a browser that doesn't
  // propagate that as a definite height for percentage-based children.
  return (
    <div className="absolute inset-0">
      <ImageDistortion
        autoPlay={autoPlay}
        src={src}
        tint={tint}
        tintStrength={tintStrength}
      />

      {cornerMarks && (
        <>
          <CornerMark className="top-5 left-5" />
          <CornerMark className="top-5 right-5" />
          <CornerMark className="bottom-5 left-5" />
          <CornerMark className="right-5 bottom-5" />
        </>
      )}

      <ScanlineOverlay />

      {channel && (
        <Small className="absolute top-5 left-10 z-1 text-[0.75em] opacity-70">
          {channel}
        </Small>
      )}

      <Small className="absolute right-10 bottom-5 z-1 text-[0.75em] opacity-80">
        {signature}
      </Small>
    </div>
  )
}

export type PosterAspect =
  | 'landscape'
  | 'portrait'
  | 'square'
  | 'story'
  | 'wide'

export type PosterVariant = 'dispatch' | 'vibe'

export interface PosterProps {
  /** Output aspect ratio. Picks sensible defaults for common social formats. */
  aspect?: PosterAspect
  /** Distortion choreography pattern. Default: `'slash'`. */
  autoPlay?: AutoPlayPattern
  /** (`dispatch` only) Descriptive copy under the headline. */
  body?: React.ReactNode
  /** Show the thin outer frame around the poster. Default `true`. */
  border?: boolean
  /** Tiny broadcast-station label. Optional in `vibe`; shown in header in `dispatch`. */
  channel?: React.ReactNode
  /** (`dispatch` only) Override the sidebar content (takes precedence over headline/body). */
  children?: React.ReactNode
  className?: string
  /** Show the small `+` die-line registration marks in the image corners. Default `true`. */
  cornerMarks?: boolean
  /** (`dispatch` only) Small tagline above the headline. */
  eyebrow?: React.ReactNode
  /** (`dispatch` only) Big expanded-typography headline. Pass an array of strings to stack lines. */
  headline?: string[] | string
  /** (`dispatch` only) Force stacked vs split layout. Default inferred from `aspect`. */
  layout?: 'split' | 'stacked'
  /** Render scale. 1 = full canvas (1080px+ base width). */
  scale?: number
  /** (`dispatch` only) Small legal / signature line at the bottom-right. */
  seal?: React.ReactNode
  /**
   * Signature mark. In `vibe` this is the small "OpenAmer Agent" overlay in the
   * bottom-right. In `dispatch` this is the URL / CTA in the footer.
   */
  signature?: React.ReactNode
  /** Override the poster image. Defaults to the OpenAmer "filler-bg0" asset. */
  src?: string
  /** (`dispatch` only) Ranked list of features / pricing tiers rendered as a numbered sidebar list. */
  tags?: string[]
  /** Shader tint overlay. Great for tier-colored variants. */
  tint?: string
  /** Active / inactive tint strength — defaults match `ImageDistortion`. */
  tintStrength?: { active: number; inactive: number }
  /** Layout variant. `'vibe'` (default) is full-bleed image; `'dispatch'` is the broadcast-card with sidebar copy. */
  variant?: PosterVariant
}
