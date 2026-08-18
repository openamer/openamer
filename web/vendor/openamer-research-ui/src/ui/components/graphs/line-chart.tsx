'use client'

import * as Plot from '@observablehq/plot'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { cn } from '../../../utils'

import {
  accessor,
  CHART_MARGINS,
  CHART_STYLE,
  type ChartProps,
  Crosshair,
  type CrosshairState,
  type DataPoint,
  setupCrosshair,
  stylePlot,
  useDims,
  withChartBlend
} from './utils'

export const LineChart = withChartBlend(
  <T extends DataPoint>({
    backgroundColor: _,
    className,
    color: strokeColor,
    curve = 'natural',
    data = [],
    formatTooltip,
    formatX: formatXProp,
    formatY: formatYProp,
    series = 'series' as keyof T,
    showArea = false,
    x = 'label' as keyof T,
    xTicks,
    y = 'value' as keyof T,
    yDomain = [0, 0.5],
    yTicks = 4,
    ...props
  }: LineChartProps<T> & { backgroundColor?: string; color?: string }) => {
    const ref = useRef<HTMLDivElement>(null)
    const plotRef = useRef<HTMLDivElement>(null)
    const [hovered, setHovered] = useState<null | T>(null)
    const [crosshair, setCrosshair] = useState<CrosshairState>({ x: null })
    const dims = useDims(ref)

    const formatX = useCallback(
      (v: unknown) =>
        formatXProp?.(v) ??
        ((v as number) >= 1e3 ? `${(v as number) / 1e3}k` : `${v}`),
      [formatXProp]
    )

    const formatY = useCallback(
      (v: number) => formatYProp?.(v) ?? `${Math.round(v * 100)}%`,
      [formatYProp]
    )

    const getX = useMemo(() => accessor<T, unknown>(x), [x])
    const getY = useMemo(() => accessor<T, number>(y), [y])
    const getZ = useCallback((d: T) => d[series], [series])

    useEffect(() => {
      if (
        !ref.current ||
        !plotRef.current ||
        !data.length ||
        !dims.h ||
        !dims.w
      ) {
        return
      }

      plotRef.current.innerHTML = ''

      const hasSeries = data.some(d => d[series] !== undefined)

      const seriesIdx = hasSeries
        ? data.reduce(
            (acc, d, i) => ((acc[d[series] as string] ??= i), acc),
            {} as Record<string, number>
          )
        : {}

      const n = Object.keys(seriesIdx).length

      const opacity = (d: T) => {
        if (!hasSeries) {
          return 1
        }

        if (hovered) {
          return d[series] === hovered[series] ? 1 : 0.2
        }

        return 1 - (seriesIdx[d[series] as string] / Math.max(n - 1, 1)) * 0.2
      }

      const lineOpts = {
        curve,
        x: getX as (d: T) => unknown,
        y: getY,
        ...(hasSeries && { z: getZ as (d: T) => unknown })
      }

      const plot = Plot.plot({
        ...CHART_MARGINS,
        height: dims.h,
        marks: [
          ...(showArea
            ? [
                Plot.areaY(data, {
                  ...lineOpts,
                  fill: strokeColor,
                  fillOpacity: 0.15,
                  y1: yDomain[0]
                })
              ]
            : []),
          Plot.lineY(data, {
            ...lineOpts,
            stroke: 'transparent',
            strokeWidth: 16
          }),
          Plot.lineY(data, {
            ...lineOpts,
            stroke: strokeColor,
            strokeOpacity: opacity,
            strokeWidth: 1.5
          })
        ],
        style: { ...CHART_STYLE, fontStretch: 'expanded' },
        width: dims.w,
        x: { label: null, tickFormat: formatX, ticks: xTicks },
        y: {
          domain: yDomain,
          grid: true,
          label: null,
          tickFormat: formatY,
          ticks: yTicks
        }
      })

      plot.addEventListener('input', () => setHovered(plot.value as null | T))
      stylePlot(plot as HTMLElement)

      plot.querySelectorAll('g[aria-label="line"] path').forEach(el =>
        Object.assign((el as SVGPathElement).style, {
          transition: 'stroke-opacity 0.2s'
        })
      )

      plotRef.current.appendChild(plot)

      const cleanup = setupCrosshair(
        ref.current,
        data,
        d => getX(d) as number,
        getY,
        yDomain,
        d => formatTooltip?.(d) ?? `${formatX(getX(d))}: ${formatY(getY(d))}`,
        setCrosshair,
        hasSeries ? d => getZ(d) : undefined
      )

      return () => {
        cleanup()
        plot.parentNode && plot.remove()
      }
    }, [
      curve,
      data,
      dims.h,
      dims.w,
      formatTooltip,
      formatX,
      formatY,
      getX,
      getY,
      getZ,
      hovered,
      series,
      showArea,
      strokeColor,
      xTicks,
      yDomain,
      yTicks
    ])

    return (
      <div
        className={cn('relative aspect-4/1 w-full overflow-clip', className)}
        ref={ref}
        {...props}
      >
        <div className="absolute inset-0" ref={plotRef} />

        <Crosshair
          color={strokeColor}
          containerWidth={dims.w}
          height={dims.h}
          {...crosshair}
        />
      </div>
    )
  }
)

interface LineChartProps<T extends DataPoint> extends ChartProps<T> {
  curve?: 'basis' | 'catmull-rom' | 'linear' | 'natural' | 'step'
  series?: keyof T
  showArea?: boolean
}
