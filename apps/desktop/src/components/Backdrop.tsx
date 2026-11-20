import { useStore } from '@nanostores/react'
import { Leva, useControls } from 'leva'
import { type CSSProperties, useEffect, useState } from 'react'

import { $backdrop } from '@/store/backdrop'

// One backdrop in the tree; the flag only distinguishes mount from a real drag.
let radiusSliderArmed = false

const BLEND_MODES = [
  'normal',
  'multiply',
  'screen',
  'overlay',
  'darken',
  'lighten',
  'color-dodge',
  'color-burn',
  'hard-light',
  'soft-light',
  'difference',
  'exclusion',
  'hue',
  'saturation',
  'color',
  'luminosity'
] as const

type BlendMode = (typeof BLEND_MODES)[number]
const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

export function Backdrop() {
  const [controlsOpen, setControlsOpen] = useState(false)
  const on = useStore($backdrop)

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return
    }

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null

      const editing =
        target?.isContentEditable ||
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement

      if (editing || event.repeat || event.altKey || event.ctrlKey || event.metaKey) {
        return
      }

      if (event.shiftKey && event.code === 'KeyY') {
        setControlsOpen(open => !open)
      }
    }

    window.addEventListener('keydown', onKeyDown)

    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const shape = useControls(
    'UI / Shape',
    // 0.85 is the styles.css `:root` default and what every theme inherits.
    // This used to default to 0.2, which overwrote the theme on every mount and
    // flattened the whole app (a 57px composer rendered at a 4.8px radius).
    { radiusScalar: { value: 0.85, min: 0, max: 2, step: 0.1, label: 'radius scalar' } },
    { collapsed: true }
  )

  useEffect(() => {
    // The theme owns `--radius-scalar` (themes/context.tsx). This slider is a
    // debug override, so the mount run only arms it — writing on mount is what
    // flattened the whole app to 0.2 before.
    if (!radiusSliderArmed) {
      radiusSliderArmed = true

      return
    }

    document.documentElement.style.setProperty('--radius-scalar', String(shape.radiusScalar))
  }, [shape.radiusScalar])

  const statue = useControls(
    'Backdrop / Statue',
    {
      enabled: { value: true, label: 'on' },
      opacity: { value: 0.025, min: 0, max: 1, step: 0.005 },
      blendMode: { value: 'difference' as BlendMode, options: BLEND_MODES, label: 'blend' },
      invert: { value: true, label: 'invert color' },
      saturate: { value: 1, min: 0, max: 3, step: 0.05, label: 'saturate' },
      brightness: { value: 1, min: 0, max: 2, step: 0.05, label: 'brightness' },
      objectPosition: {
        value: 'top left',
        options: ['top left', 'top right', 'bottom left', 'bottom right', 'center', 'top', 'bottom', 'left', 'right'],
        label: 'position'
      },
      scale: { value: 160, min: 100, max: 300, step: 5, label: 'height (dvh)' }
    },
    { collapsed: true }
  )

  return (
    <>
      <Leva collapsed hidden={!import.meta.env.DEV || !controlsOpen} titleBar={{ title: 'backdrop', drag: true }} />

      {on && statue.enabled && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-2"
          style={{
            mixBlendMode: statue.blendMode as CSSProperties['mixBlendMode'],
            opacity: statue.opacity
          }}
        >
          <img
            alt=""
            className="w-auto min-w-dvw object-cover"
            fetchPriority="low"
            src={assetPath('ds-assets/filler-bg0.jpg')}
            style={{
              height: `${statue.scale}dvh`,
              objectPosition: statue.objectPosition,
              filter: `invert(calc(${statue.invert ? 1 : 0} * var(--backdrop-invert-mul, 1))) saturate(${statue.saturate}) brightness(${statue.brightness})`
            }}
          />
        </div>
      )}
    </>
  )
}
