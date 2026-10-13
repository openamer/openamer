'use client'

import { useEffect } from 'react'

import { useSmoothControls } from '../../../hooks/use-smooth-controls'
import { colorMix } from '../../../utils/color'

import fillerBg from '../../../assets/filler-bg0.webp'

import { BLEND_MODES } from './blend-modes'
import { $lightMode, LENS_0, LENS_5I, type LensPreset, toggleLens } from './lens'

const LAYER = 'pointer-events-none fixed inset-0'

export function Lens({ dark, initial }: LensProps) {
  // `initial` lets the host (e.g. Storybook) seed the Leva/atom state with
  // the *exact* lens preset the user selected, avoiding a one-cycle lag
  // where useSmoothControls emits old colors for the first paint (and, on
  // Storybook's fast iframe reload, sometimes never catches up because
  // useControls' ready-gate swallows the instant color writes).
  const base = initial?.Lens ?? (dark ? LENS_0.Lens : LENS_5I.Lens)

  const lens = useSmoothControls(
    'Lens',
    {
      bgBlend: { options: BLEND_MODES, value: base.bgBlend as 'multiply' },
      bgColor: { value: base.bgColor },
      bgOpacity: { max: 1, min: 0, step: 0.01, value: base.bgOpacity },
      fgBlend: { options: BLEND_MODES, value: 'difference' as const },
      fgColor: { value: base.fgColor },
      fgOpacity: { max: 1, min: 0, step: 0.01, value: base.fgOpacity },
      fillerBlend: { options: BLEND_MODES, value: 'difference' as const },
      fillerOpacity: { max: 1, min: 0, step: 0.01, value: base.fillerOpacity },
      mgColor: { value: base.mgColor },
      mgOpacity: { max: 1, min: 0, step: 0.01, value: base.mgOpacity }
    },
    { collapsed: false }
  )

  useEffect(() => {
    $lightMode.set(!dark)
  }, [dark])

  useEffect(() => {
    const s = document.documentElement.style

    for (const [name, color, alpha] of [
      ['foreground', lens.fgColor, lens.fgOpacity],
      ['midground', lens.mgColor, lens.mgOpacity],
      ['background', lens.bgColor, lens.bgOpacity]
    ] as [string, string, number][]) {
      s.setProperty(`--${name}`, colorMix(color, alpha))
      s.setProperty(`--${name}-base`, color)
      s.setProperty(`--${name}-alpha`, `${alpha}`)
    }
  }, [lens])

  useEffect(() => {
    const handle = (e: KeyboardEvent) => e.key === 'x' && toggleLens()
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [])

  // NOTE: z-index is inlined because Tailwind's JIT sometimes doesn't emit
  // these non-default utilities (e.g. in Storybook's isolated content
  // scan), which silently collapses the overlay stack to DOM order and
  // breaks the mix-blend-mode inversion — producing a muddy warm wash
  // instead of the intended clean black/white inversion.
  return (
    <>
      <div
        className={LAYER}
        style={{
          backgroundColor: colorMix(lens.fgColor, lens.fgOpacity),
          mixBlendMode: lens.fgBlend,
          zIndex: 100
        }}
      />

      <div
        className={LAYER}
        style={{
          mixBlendMode: lens.fillerBlend,
          opacity: lens.fillerOpacity,
          zIndex: 2
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt=""
          className="h-[150dvh] w-auto min-w-dvw object-cover object-top-left invert"
          fetchPriority="low"
          height={1024}
          src={fillerBg.src}
          width={1024}
        />
      </div>

      <div
        className={LAYER}
        style={{
          backgroundColor: colorMix(lens.bgColor, lens.bgOpacity),
          mixBlendMode: lens.bgBlend,
          zIndex: 1
        }}
      />
    </>
  )
}

interface LensProps {
  dark?: boolean
  /**
   * Exact preset to seed the internal Leva controls with. When omitted the
   * component falls back to `LENS_0` / `LENS_5I` based on `dark`. Pass the
   * actual preset from a host (e.g. Storybook toolbar) to guarantee the
   * first-paint colors match the selected lens without needing a followup
   * `applyLens` that can be lost in useSmoothControls' startup window.
   */
  initial?: LensPreset
}
