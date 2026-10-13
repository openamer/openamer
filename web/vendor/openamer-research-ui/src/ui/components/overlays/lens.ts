'use client'

import { atom } from 'nanostores'

import { setControlValue } from '../../../hooks/use-smooth-controls'

export const LENS_0 = {
  Globe: { innerColor: '#170d02', innerOpacity: 0.1, outerColor: '#FFAC02' },
  Lens: {
    bgBlend: 'difference',
    bgColor: '#041C1C',
    bgOpacity: 1,
    fgColor: '#FFFFFF',
    fgOpacity: 0,
    fillerOpacity: 0.033,
    mgColor: '#ffe6cb',
    mgOpacity: 1
  }
}

export const LENS_5I = {
  Globe: { innerColor: '#170d02', innerOpacity: 0.3, outerColor: '#FFAC02' },
  Lens: {
    bgBlend: 'multiply',
    bgColor: '#170d02',
    bgOpacity: 1,
    fgColor: '#FFFFFF',
    fgOpacity: 1,
    fillerOpacity: 0.06,
    mgColor: '#FFAC02',
    mgOpacity: 1
  }
}

export const lens0 = (
  l?: Partial<typeof LENS_0.Lens>,
  g?: Partial<typeof LENS_0.Globe>
): LensPreset => ({
  Globe: { ...LENS_0.Globe, ...g },
  Lens: { ...LENS_0.Lens, ...l }
})

// The OpenAmer light-mode look is produced by a fullscreen opaque-white
// `mix-blend-mode: difference` foreground layer that inverts everything.
// Colored lenses that want a "white + accent" look MUST be built from
// LENS_5I, not LENS_0 — otherwise `bgBlend: 'difference'` + an opaque
// colored bg + active fg inversion land halfway between dark and light
// mode and produce a muddy warm wash instead of a clean inversion.
export const lens5i = (
  l?: Partial<typeof LENS_5I.Lens>,
  g?: Partial<typeof LENS_5I.Globe>
): LensPreset => ({
  Globe: { ...LENS_5I.Globe, ...g },
  Lens: { ...LENS_5I.Lens, ...l }
})

// Accent colors are the *pre-inversion* source; after the difference FG
// layer they read as their visual complement. e.g. `#FFAC02` (orange)
// renders as blue #0053FD on screen — that's the default LENS_5I accent.
export const LENSES: [string, LensPreset][] = [
  ['0', LENS_0],
  ['1', lens0({ bgColor: '#0A1F1F' })],
  ['2', lens0({ bgColor: '#0E0313', mgColor: '#e6cbff' })],
  ['3', lens5i({ mgColor: '#FFAC02' })],
  ['4', lens5i({ bgColor: '#0E0313', mgColor: '#FF5500' })],
  ['5', lens0({ bgColor: '#1540B1', bgOpacity: 0.7 })],
  ['5i', LENS_5I],
  ['6', lens5i({ bgColor: '#170D02', mgColor: '#00E5FF' })]
]

export const applyLens = (preset: LensPreset, animate = false) =>
  Object.entries(preset).forEach(([g, v]) =>
    Object.entries(v).forEach(([k, val]) =>
      setControlValue(g, k, val, { animate })
    )
  )

export const $lightMode = atom(true)

export const toggleLens = () => {
  const isLight = $lightMode.get()
  const next = isLight ? LENS_0 : LENS_5I

  $lightMode.set(!isLight)
  applyLens(next, true)
}

export interface LensPreset {
  Globe: typeof LENS_0.Globe
  Lens: typeof LENS_0.Lens
}
