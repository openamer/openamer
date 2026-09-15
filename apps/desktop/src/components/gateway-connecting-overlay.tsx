import { useStore } from '@nanostores/react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import { $desktopBoot } from '@/store/boot'
import { $gatewaySwitching } from '@/store/gateway-switch'
import { $gatewayState } from '@/store/session'

// Exit choreography (ms): overlay fades out.
const OVERLAY_OUT_MS = 520
// Preview-only: how long to "connect" for, and the pause before replaying.
const PREVIEW_CONNECT_MS = 3000
const PREVIEW_REPLAY_MS = 1100

type Phase = 'live' | 'overlay-out' | 'gone'

// Neural network node positions (relative 0..1)
const NODES = [
  { x: 0.2, y: 0.3 },
  { x: 0.35, y: 0.15 },
  { x: 0.5, y: 0.25 },
  { x: 0.3, y: 0.5 },
  { x: 0.5, y: 0.45 },
  { x: 0.65, y: 0.35 },
  { x: 0.2, y: 0.7 },
  { x: 0.4, y: 0.75 },
  { x: 0.55, y: 0.65 },
  { x: 0.7, y: 0.55 },
  { x: 0.5, y: 0.85 },
  { x: 0.7, y: 0.75 },
  { x: 0.8, y: 0.3 },
  { x: 0.8, y: 0.6 },
  { x: 0.85, y: 0.45 },
  { x: 0.1, y: 0.5 },
  { x: 0.65, y: 0.15 },
  { x: 0.45, y: 0.55 }
]

// Connections between nodes [from, to]
const CONNECTIONS: [number, number][] = [
  [0, 1],
  [0, 3],
  [1, 2],
  [1, 4],
  [2, 5],
  [2, 12],
  [3, 4],
  [3, 6],
  [4, 5],
  [4, 7],
  [5, 8],
  [5, 12],
  [6, 7],
  [6, 9],
  [7, 8],
  [7, 10],
  [8, 9],
  [8, 11],
  [9, 11],
  [9, 13],
  [10, 11],
  [10, 14],
  [11, 13],
  [12, 17],
  [13, 14],
  [14, 11],
  [15, 3],
  [15, 6],
  [16, 1],
  [16, 2],
  [17, 4],
  [17, 7]
]

// Dev affordance: load with `?connecting=1` to force a looping preview.
function forcedPreview(): boolean {
  if (!import.meta.env.DEV || typeof window === 'undefined') {
    return false
  }

  try {
    return new URLSearchParams(window.location.search).get('connecting') === '1'
  } catch {
    return false
  }
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

function NeuralNetwork() {
  const [tick, setTick] = useState(0)
  const w = 600
  const h = 400
  const cx = (x: number) => x * w
  const cy = (y: number) => y * h

  useEffect(() => {
    const id = window.setInterval(() => setTick(t => t + 1), 120)

    return () => window.clearInterval(id)
  }, [])

  const pulsePhase = (tick % 20) / 20
  const pulseEdge = Math.floor(pulsePhase * CONNECTIONS.length)
  const pulseEdgeNext = (pulseEdge + 1) % CONNECTIONS.length
  const pulseProgress = (pulsePhase * CONNECTIONS.length) % 1

  return (
    <svg aria-hidden="true" className="w-[600px] h-[400px]" viewBox={`0 0 ${w} ${h}`}>
      <defs>
        <linearGradient id="nn-glow" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="#00b4d8" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#48cae4" stopOpacity="0.05" />
        </linearGradient>
        <filter id="nn-glow-filter">
          <feGaussianBlur result="blur" stdDeviation="3" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <ellipse cx={w / 2} cy={h / 2} fill="url(#nn-glow)" rx={w * 0.5} ry={h * 0.5} />

      {CONNECTIONS.map(([from, to], i) => {
        const f = NODES[from]
        const t = NODES[to]
        const isPulsing = i === pulseEdge || i === pulseEdgeNext
        const opacity = isPulsing ? 0.6 + 0.4 * Math.sin(tick * 0.3 + i) : 0.15
        const width = isPulsing ? 2.5 : 1

        return (
          <line
            key={`conn-${i}`}
            stroke={isPulsing ? '#48cae4' : '#00b4d8'}
            strokeOpacity={opacity}
            strokeWidth={width}
            style={{ transition: 'stroke-opacity 0.3s, stroke-width 0.3s' }}
            x1={cx(f.x)}
            x2={cx(t.x)}
            y1={cy(f.y)}
            y2={cy(t.y)}
          />
        )
      })}

      {(() => {
        const [from, to] = CONNECTIONS[pulseEdge]
        const f = NODES[from]
        const t = NODES[to]
        const px = cx(f.x) + (cx(t.x) - cx(f.x)) * pulseProgress
        const py = cy(f.y) + (cy(t.y) - cy(f.y)) * pulseProgress

        return <circle cx={px} cy={py} fill="#90e0ef" filter="url(#nn-glow-filter)" r={4} />
      })()}

      {/* OpenAmer eye icon in center */}
      <g transform={`translate(${w / 2}, ${h / 2})`}>
        {/* Outer ring */}
        <circle
          cx={0}
          cy={0}
          fill="none"
          r={28}
          stroke="#00b4d8"
          strokeOpacity={0.6 + 0.4 * Math.sin(tick * 0.04)}
          strokeWidth={2}
          style={{ transition: 'stroke-opacity 0.3s' }}
        />
        {/* Inner eye */}
        <ellipse
          cx={0}
          cy={0}
          fill="#48cae4"
          fillOpacity={0.3 + 0.2 * Math.sin(tick * 0.03)}
          rx={18}
          ry={12}
          style={{ transition: 'fill-opacity 0.3s' }}
        />
        {/* Pupil */}
        <circle cx={0} cy={0} fill="#90e0ef" filter="url(#nn-glow-filter)" r={5} />
      </g>

      {/* Nodes */}
      {NODES.map((node, i) => {
        const isActive = Math.sin(tick * 0.05 + i * 0.7) > 0.3
        const r = isActive ? 4.5 : 3

        return (
          <circle
            cx={cx(node.x)}
            cy={cy(node.y)}
            fill={isActive ? '#48cae4' : '#00b4d8'}
            fillOpacity={isActive ? 0.9 : 0.4}
            key={`node-${i}`}
            r={r}
            style={{ transition: 'r 0.4s, fill-opacity 0.4s' }}
          />
        )
      })}
    </svg>
  )
}

export function GatewayConnectingOverlay() {
  const gatewayState = useStore($gatewayState)
  const boot = useStore($desktopBoot)
  const gatewaySwitching = useStore($gatewaySwitching)
  const [previewing] = useState(forcedPreview)
  const reduce = prefersReducedMotion()
  const [phase, setPhase] = useState<Phase>('live')
  const coldBootDoneRef = useRef(false)

  if (!boot.running && boot.progress >= 100 && !boot.error) {
    coldBootDoneRef.current = true
  }

  const initialBootActive = boot.visible || boot.running || boot.progress < 100

  const connecting =
    !coldBootDoneRef.current && !gatewaySwitching && gatewayState !== 'open' && !boot.error && initialBootActive

  const shownRef = useRef(false)

  if (previewing || connecting) {
    shownRef.current = true
  }

  useEffect(() => {
    if (phase !== 'live') {
      return
    }

    if (previewing) {
      const id = window.setTimeout(() => setPhase('overlay-out'), PREVIEW_CONNECT_MS)

      return () => window.clearTimeout(id)
    }

    if (gatewayState === 'open' && shownRef.current) {
      setPhase(reduce ? 'gone' : 'overlay-out')
    }
  }, [phase, previewing, gatewayState, reduce])

  useEffect(() => {
    if (phase === 'overlay-out') {
      const id = window.setTimeout(() => setPhase('gone'), OVERLAY_OUT_MS)

      return () => window.clearTimeout(id)
    }

    if (phase === 'gone' && previewing) {
      const id = window.setTimeout(() => setPhase('live'), PREVIEW_REPLAY_MS)

      return () => window.clearTimeout(id)
    }
  }, [phase, previewing])

  if (boot.error && !previewing) {
    return null
  }

  if (phase === 'gone' && !previewing) {
    return null
  }

  if (!previewing && !connecting && !shownRef.current) {
    return null
  }

  const overlayHidden = phase === 'overlay-out' || phase === 'gone'

  return (
    <div
      className={cn(
        'fixed inset-0 z-[1200] grid place-items-center bg-(--ui-chat-surface-background) transition-opacity duration-500 ease-out',
        overlayHidden ? 'pointer-events-none opacity-0' : 'opacity-100'
      )}
    >
      <div className="flex flex-col items-center gap-8">
        {/* Neural network animation */}
        <div
          className={cn(
            'transition-all duration-500 ease-out',
            overlayHidden ? 'scale-95 opacity-0' : 'scale-100 opacity-100'
          )}
        >
          <NeuralNetwork />
        </div>

        {/* Text */}
        <div className="flex flex-col items-center gap-2">
          <span
            className={cn(
              'font-mono text-xs tracking-[0.3em] uppercase transition-all duration-300 ease-out',
              'text-(--theme-primary)',
              overlayHidden ? 'translate-y-2 opacity-0' : 'translate-y-0 opacity-100'
            )}
          >
            CONNECTING TO
          </span>
          <span
            className={cn(
              'font-mono text-sm tracking-[0.4em] font-bold uppercase transition-all duration-300 delay-75 ease-out',
              'text-(--theme-primary)',
              overlayHidden ? 'translate-y-2 opacity-0' : 'translate-y-0 opacity-100'
            )}
          >
            OPENAMER
          </span>

          {/* Animated dots */}
          <div className="flex gap-1.5 mt-3">
            {[0, 1, 2].map(i => (
              <div
                className="w-1.5 h-1.5 rounded-full bg-(--theme-primary)"
                key={i}
                style={{
                  animation: reduce ? 'none' : `nn-pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
                  opacity: reduce ? 0.5 : undefined
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
