'use client'

import { Glitch } from './glitch'
import { Greys } from './greys'
import { Lens } from './lens-layers'
import { Noise } from './noise'
import { Vignette } from './vignette'

import type { LensPreset } from './lens'

export { BLEND_MODES } from './blend-modes'
export { Glitch } from './glitch'
export { Greys } from './greys'
export { Lens } from './lens-layers'
export { Noise } from './noise'
export { Vignette } from './vignette'
export {
  $lightMode,
  applyLens,
  lens0,
  lens5i,
  LENS_0,
  LENS_5I,
  LENSES,
  toggleLens
} from './lens'
export type { LensPreset } from './lens'

const LAYER = 'pointer-events-none fixed inset-0'

export function Overlays({ dark, initial }: OverlaysProps) {
  return (
    <>
      <Lens dark={dark} initial={initial} />

      <Noise className={LAYER} style={{ zIndex: 101 }} />
      <Vignette className={LAYER} style={{ zIndex: 99 }} />
      <Greys className={LAYER} style={{ zIndex: 200 }} />
      <Glitch className={LAYER} style={{ zIndex: 201 }} />
    </>
  )
}

interface OverlaysProps {
  dark?: boolean
  initial?: LensPreset
}
