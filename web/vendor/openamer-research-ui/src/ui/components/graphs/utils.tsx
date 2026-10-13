'use client'

import {
  type ComponentType,
  type HTMLAttributes,
  type RefObject,
  useEffect,
  useState
} from 'react'

import { useSmoothControls } from '../../../hooks/use-smooth-controls'
import {
  type BlendColors,
  type BlendModeProps
} from '../blend-mode'

export const accessor = <T, R>(key: ((d: T) => R) | keyof T) =>
  typeof key === 'function' ? key : (d: T) => d[key] as R

export const CHART_MARGINS = {
  marginBottom: 24,
  marginLeft: 36,
  marginRight: 12,
  marginTop: 8
} as const

export const CHART_STYLE = {
  background: 'transparent',
  color: 'var(--midground)',
  fontFamily: 'var(--font-mono), monospace',
  fontSize: '11px',
  overflow: 'hidden'
} as const

export const stylePlot = (plot: HTMLElement) => {
  plot.querySelectorAll('[aria-label*="grid"] line').forEach(el =>
    Object.assign((el as SVGLineElement).style, {
      stroke: 'currentColor',
      strokeDasharray: '2,4',
      strokeOpacity: '0.3'
    })
  )

  plot.querySelectorAll('text').forEach(el =>
    Object.assign((el as SVGTextElement).style, {
      fontSize: '11px',
      fontWeight: '600'
    })
  )

  plot
    .querySelectorAll('[aria-label*="label"] text')
    .forEach(el => ((el as SVGTextElement).style.opacity = '0.4'))

  const svg = plot.querySelector('svg')
  svg && (svg.style.display = 'block')
}

export const useDims = (ref: RefObject<HTMLElement | null>) => {
  const [dims, setDims] = useState({ h: 0, w: 0 })

  useEffect(() => {
    if (!ref.current) {
      return
    }

    const update = () => {
      const { height: h, width: w } = ref.current!.getBoundingClientRect()
      const [rh, rw] = [Math.round(h), Math.round(w)]

      rh &&
        rw &&
        setDims(st => (st.h === rh && st.w === rw ? st : { h: rh, w: rw }))
    }

    update()

    const ro = new ResizeObserver(update)
    ro.observe(ref.current)

    return () => ro.disconnect()
  }, [ref])

  return dims
}

export const Crosshair = ({
  color = 'var(--foreground)',
  containerWidth,
  height,
  points,
  x
}: CrosshairState & {
  color?: string
  containerWidth: number
  height: number
}) => {
  if (x === null) {
    return null
  }

  const nearRight = x > containerWidth * 0.7

  return (
    <>
      <div
        className="pointer-events-none absolute top-0 w-px"
        style={{ background: color, height, left: x, opacity: 0.4 }}
      />

      {points?.map((pt, i) => (
        <div
          className="pointer-events-none absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          key={i}
          style={{ background: color, left: x, top: pt.dotY }}
        />
      ))}

      {points?.map((pt, i) => (
        <div
          className="tooltip absolute -translate-y-1/2"
          key={i}
          style={{
            left: nearRight ? undefined : x + 12,
            right: nearRight ? containerWidth - x + 12 : undefined,
            top: pt.dotY
          }}
        >
          {pt.tooltip}
        </div>
      ))}
    </>
  )
}

export const setupCrosshair = <T extends DataPoint>(
  container: HTMLElement,
  data: T[],
  getX: (d: T) => number,
  getY: (d: T) => number,
  yDomain: [number, number],
  formatTooltip: (d: T) => string,
  onUpdate: (state: CrosshairState) => void,
  getZ?: (d: T) => unknown
) => {
  if (!data.length) {
    return () => {}
  }

  const { marginBottom, marginLeft, marginRight, marginTop } = CHART_MARGINS

  const seriesMap = data.reduce((m, d) => {
    const key = getZ?.(d) ?? '__single__'
    m.set(key, [...(m.get(key) ?? []), d])

    return m
  }, new Map<unknown, T[]>())

  const sortedSeries = [...seriesMap.values()].map(s =>
    [...s].sort((a, b) => getX(a) - getX(b))
  )

  const allX = data.map(getX)
  const [xMin, xMax] = [Math.min(...allX), Math.max(...allX)]

  const onMove = (e: MouseEvent) => {
    const rect = container.getBoundingClientRect()
    const [localX, localY] = [e.clientX - rect.left, e.clientY - rect.top]

    if (
      localX < 0 ||
      localX > rect.width ||
      localY < 0 ||
      localY > rect.height
    ) {
      return onUpdate({ x: null })
    }

    const [chartLeft, chartRight] = [marginLeft, rect.width - marginRight]
    const [chartTop, chartBottom] = [marginTop, rect.height - marginBottom]

    if (localX < chartLeft || localX > chartRight) {
      return onUpdate({ x: null })
    }

    const pct = (localX - chartLeft) / (chartRight - chartLeft)
    const xVal = xMin + pct * (xMax - xMin)

    const points = sortedSeries.map(sorted => {
      const idx = sorted.findIndex(d => getX(d) >= xVal)

      const [closest, yVal] =
        idx <= 0
          ? [sorted[0], getY(sorted[0])]
          : idx >= sorted.length
            ? [sorted.at(-1)!, getY(sorted.at(-1)!)]
            : (() => {
                const [left, right] = [sorted[idx - 1], sorted[idx]]
                const t = (xVal - getX(left)) / (getX(right) - getX(left))

                return [
                  t < 0.5 ? left : right,
                  getY(left) + t * (getY(right) - getY(left))
                ] as const
              })()

      const yPct = (yVal - yDomain[0]) / (yDomain[1] - yDomain[0])

      return {
        dotY: chartBottom - yPct * (chartBottom - chartTop),
        tooltip: formatTooltip(closest)
      }
    })

    onUpdate({ points, x: localX })
  }

  document.addEventListener('mousemove', onMove)

  return () => document.removeEventListener('mousemove', onMove)
}

export const withChartBlend = <P extends BlendModeProps>(
  Component: ComponentType<P>
) => {
  const Wrapped = (props: Omit<P, keyof BlendColors>) => {
    const { color } = useSmoothControls(
      'Charts',
      { color: { value: '#709fea' } },
      { collapsed: true }
    )

    return <Component {...(props as P)} color={color} />
  }

  Wrapped.displayName = `withChartBlend(${Component.displayName ?? Component.name})`

  return Wrapped
}

export type DataPoint = Record<string, unknown>

export interface CrosshairPoint {
  dotY: number
  tooltip: string
}

export interface CrosshairState {
  points?: CrosshairPoint[]
  x: null | number
}

export interface ChartProps<T = DataPoint>
  extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  data?: T[]
  formatTooltip?: (d: T) => string
  formatX?: (v: unknown) => string
  formatY?: (v: number) => string
  height?: number
  x?: ((d: T) => unknown) | keyof T
  xTicks?: number | number[]
  y?: ((d: T) => number) | keyof T
  yDomain?: [number, number]
  yTicks?: number | number[]
}
