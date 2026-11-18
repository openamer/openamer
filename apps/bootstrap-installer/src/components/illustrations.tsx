/*
 * Installer illustrations — hand-written SVG, no bitmaps.
 *
 * Why SVG instead of screenshots: a setup window has to look right on a 4K
 * display and on a 1366×768 laptop, in light and dark, and it ships inside the
 * binary (tauri CSP allows `img-src 'self' data:` only). Vector art scales,
 * themes itself from `currentColor`, and adds ~4 kB instead of ~400 kB.
 *
 * What they may NOT do: pretend to be screenshots of features. Every drawing
 * here is an abstraction of a property the product actually has (local models,
 * 186 locales, tool use, skills that accrue) — no fake UI, no invented menu.
 */

const VIEWBOX = '0 0 240 180'

function Frame({
  children,
  label,
  viewBox = VIEWBOX
}: {
  children: React.ReactNode
  label: string
  viewBox?: string
}) {
  return (
    <svg
      aria-label={label}
      className="h-full w-full"
      fill="none"
      role="img"
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox={viewBox}
    >
      {children}
    </svg>
  )
}

/** Strands: the brand mark's DNA helix, drawn as two phase-shifted sine waves. */
export function HelixIllustration({ label = 'DNA helix' }: { label?: string }) {
  const CX = 120
  const AMP = 30
  const TOP = 10
  const HEIGHT = 160
  const TURNS = 2.25
  const STEPS = 64

  const strand = (phase: number): string => {
    let d = ''

    for (let i = 0; i <= STEPS; i += 1) {
      const t = i / STEPS
      const x = CX + AMP * Math.sin(2 * Math.PI * TURNS * t + phase)
      const y = TOP + HEIGHT * t
      d += `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
    }

    return d
  }

  // Base pairs sit where the strands are far apart; the opacity follows the
  // separation, so the rungs read as depth rather than as a ladder.
  const rungs = Array.from({ length: 13 }, (_, i) => {
    const t = (i + 0.5) / 13
    const x1 = CX + AMP * Math.sin(2 * Math.PI * TURNS * t)
    const x2 = CX + AMP * Math.sin(2 * Math.PI * TURNS * t + Math.PI)
    const separation = Math.abs(x2 - x1) / (2 * AMP)

    return { d: `M${x1.toFixed(1)} ${(TOP + HEIGHT * t).toFixed(1)}H${x2.toFixed(1)}`, i, separation }
  })

  return (
    <Frame label={label}>
      <path d={strand(0)} stroke="currentColor" strokeOpacity="0.92" strokeWidth="2.6" />
      <path d={strand(Math.PI)} stroke="currentColor" strokeOpacity="0.5" strokeWidth="2.6" />
      {rungs.map(({ d, i, separation }) => (
        <path
          className="installer-rung"
          d={d}
          key={d}
          stroke="currentColor"
          strokeOpacity={0.2 + separation * 0.4}
          strokeWidth="1.7"
          style={{ animationDelay: `${i * 0.14}s` }}
        />
      ))}
    </Frame>
  )
}

/** Local-first: a compute die with a closed loop around it. */
export function LocalComputeIllustration({
  label = 'Local compute',
  tight = false
}: {
  label?: string
  tight?: boolean
}) {
  return (
    <Frame label={label} viewBox={tight ? '62 32 116 116' : VIEWBOX}>
      <rect height="72" rx="10" stroke="currentColor" strokeOpacity="0.55" strokeWidth="1.8" width="72" x="84" y="54" />
      <rect height="34" rx="6" stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.4" width="34" x="103" y="73" />
      <circle cx="120" cy="90" fill="currentColor" fillOpacity="0.5" r="6" />
      {[0, 1, 2, 3].map(i => (
        <g key={i} stroke="currentColor" strokeOpacity="0.4" strokeWidth="1.6">
          <path d={`M${96 + i * 16} 54v-12`} />
          <path d={`M${96 + i * 16} 126v12`} />
        </g>
      ))}
      {[0, 1, 2, 3].map(i => (
        <g key={i} stroke="currentColor" strokeOpacity="0.4" strokeWidth="1.6">
          <path d={`M84 ${66 + i * 16}h-12`} />
          <path d={`M156 ${66 + i * 16}h12`} />
        </g>
      ))}
      <circle
        className="installer-pulse"
        cx="120"
        cy="90"
        r="46"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeWidth="1.2"
      />
      <circle
        className="installer-pulse installer-pulse-late"
        cx="120"
        cy="90"
        r="46"
        stroke="currentColor"
        strokeOpacity="0.18"
        strokeWidth="1.2"
      />
    </Frame>
  )
}

/** 186 locales: a globe circled by scripts, each in its own writing system. */
export function WorldScriptsIllustration({ label = 'Languages' }: { label?: string }) {
  return (
    <Frame label={label}>
      <circle cx="120" cy="92" r="52" stroke="currentColor" strokeOpacity="0.5" strokeWidth="1.8" />
      <ellipse cx="120" cy="92" rx="22" ry="52" stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.3" />
      <ellipse cx="120" cy="92" rx="42" ry="52" stroke="currentColor" strokeOpacity="0.2" strokeWidth="1.2" />
      <path d="M70 76h100M70 108h100" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.2" />
      <path d="M120 40v104" stroke="currentColor" strokeOpacity="0.18" strokeWidth="1.2" />
      {[
        { glyph: '日', x: 24, y: 44 },
        { glyph: 'ह', x: 196, y: 62 },
        { glyph: 'ع', x: 30, y: 124 },
        { glyph: 'ქ', x: 198, y: 132 },
        { glyph: 'ß', x: 58, y: 22 },
        { glyph: '한', x: 176, y: 168 }
      ].map(({ glyph, x, y }) => (
        <text
          fill="currentColor"
          fillOpacity="0.55"
          fontFamily="'Segoe UI', system-ui, sans-serif"
          fontSize="17"
          key={glyph}
          textAnchor="middle"
          x={x}
          y={y}
        >
          {glyph}
        </text>
      ))}
    </Frame>
  )
}

/** Tools: a terminal window mid-run. */
export function ToolRunIllustration({ label = 'Tools' }: { label?: string }) {
  return (
    <Frame label={label}>
      <rect height="104" rx="10" stroke="currentColor" strokeOpacity="0.5" strokeWidth="1.8" width="152" x="44" y="38" />
      <path d="M44 60h152" stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.4" />
      {[0, 1, 2].map(i => (
        <circle cx={58 + i * 12} cy="49" fill="currentColor" fillOpacity="0.35" key={i} r="2.6" />
      ))}
      <path d="M60 78l10 8-10 8" stroke="currentColor" strokeOpacity="0.75" strokeWidth="1.8" />
      <path d="M84 94h44" stroke="currentColor" strokeOpacity="0.45" strokeWidth="3" />
      <path d="M60 112h76" stroke="currentColor" strokeOpacity="0.28" strokeWidth="3" />
      <path d="M60 128h56" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <rect
        className="installer-caret"
        fill="currentColor"
        fillOpacity="0.8"
        height="11"
        rx="1.5"
        width="7"
        x="146"
        y="106"
      />
    </Frame>
  )
}

/** Skills: a small graph where one node is lit — the one being learned now. */
export function SkillGraphIllustration({ label = 'Skills' }: { label?: string }) {
  const nodes = [
    { r: 7, x: 120, y: 40 },
    { r: 5, x: 66, y: 76 },
    { r: 5, x: 174, y: 76 },
    { r: 6, x: 92, y: 128 },
    { r: 6, x: 150, y: 128 },
    { r: 4, x: 40, y: 132 },
    { r: 4, x: 200, y: 132 }
  ]

  return (
    <Frame label={label}>
      <g stroke="currentColor" strokeOpacity="0.28" strokeWidth="1.2">
        <path d="M120 40 66 76M120 40l54 36M66 76l26 52M174 76l-24 52M92 128h58M66 76l-26 56M174 76l26 56" />
      </g>
      {nodes.map((n, i) => (
        <circle
          className={i === 4 ? 'installer-node installer-node-lit' : 'installer-node'}
          cx={n.x}
          cy={n.y}
          fill="currentColor"
          fillOpacity={i === 4 ? 0.85 : 0.3}
          key={`${n.x}-${n.y}`}
          r={n.r}
          style={{ animationDelay: `${i * 0.22}s` }}
        />
      ))}
    </Frame>
  )
}

/** Success: a check inside a burst, the one place celebration is allowed. */
export function ReadyIllustration({ label = 'Ready' }: { label?: string }) {
  const rays = [0, 45, 90, 135, 180, 225, 270, 315].map((deg, i) => {
    const rad = (deg * Math.PI) / 180
    const x1 = 120 + Math.cos(rad) * 56
    const y1 = 90 + Math.sin(rad) * 56
    const x2 = 120 + Math.cos(rad) * 68
    const y2 = 90 + Math.sin(rad) * 68

    return { d: `M${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}`, deg, i }
  })

  return (
    <Frame label={label} viewBox="48 18 144 144">
      <circle cx="120" cy="90" fill="currentColor" fillOpacity="0.08" r="46" />
      <circle className="installer-ring" cx="120" cy="90" r="46" stroke="currentColor" strokeOpacity="0.4" strokeWidth="1.6" />
      <path d="M100 92l14 14 28-30" stroke="currentColor" strokeOpacity="0.95" strokeWidth="3.2" />
      {rays.map(({ d, deg, i }) => (
        <path
          className="installer-ray"
          d={d}
          key={deg}
          stroke="currentColor"
          strokeOpacity="0.3"
          strokeWidth="1.6"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </Frame>
  )
}

/** Progress: a determinate ring, because an OS setup should never show a lie. */
export function ProgressRing({ pct }: { pct: number }) {
  const r = 54
  const c = 2 * Math.PI * r
  const clamped = Math.max(0, Math.min(100, pct))

  return (
    <svg aria-hidden="true" className="size-full" fill="none" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} stroke="currentColor" strokeOpacity="0.14" strokeWidth="6" />
      <circle
        className="transition-[stroke-dashoffset] duration-500 ease-out"
        cx="70"
        cy="70"
        r={r}
        stroke="currentColor"
        strokeDasharray={c}
        strokeDashoffset={c - (clamped / 100) * c}
        strokeLinecap="round"
        strokeWidth="6"
        transform="rotate(-90 70 70)"
      />
    </svg>
  )
}
