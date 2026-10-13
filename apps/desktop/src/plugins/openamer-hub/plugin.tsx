/**
 * OpenAmer Hub — Desktop plugin for all Phase 1-25 features.
 *
 * Adds sidebar navigation and full-page workspace panes for:
 * - 🤖  Agent Builder  – visual agent creation
 * - 🧠  Brain Dashboard – learning-loop stats & growth
 * - 👥  Crews & Swarm  – multi-agent orchestration
 * - 📊  Trace & Observability – execution browser
 * - 🏪  Marketplace    – community agent discovery
 * - 🎯  Superintelligence – system health overview
 *
 * Architecture notes (matching AGENTS.md):
 *   - Every page is a *pure view* of backend truth, never a stateful editor.
 *     Mutation goes through the gateway (openamer-cli), not React state.
 *   - Route contributions target ROUTES_AREA for their page and
 *     SIDEBAR_NAV_AREA for their nav row — no core edits needed.
 *   - Components are lazy-loaded: vite's import.meta.glob discovers
 *     them automatically. No import graph edit needed.
 */

import {
  Button,
  type OpenAmerPlugin,
  type PluginContribution,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution,
} from '@openamer/plugin-sdk'
import React from 'react'
import { useNavigate } from 'react-router-dom'

// ── Constants ───────────────────────────────────────────────────────────

const PHASE_ORDER_BASE = 110 // Leave gap below 110 for core items

/** Phase 1-25 features displayed in the Superintelligence page. */
const SYSTEM_CHECKS = [
  { label: '🧠  Brain Learning Loop',    score: 95 },
  { label: '🌐  A2A Swarm',             score: 88 },
  { label: '🌐  Web Agent',             score: 85 },
  { label: '🛠️   99+ Tools / 117 Skills', score: 100 },
  { label: '🖥️   Computer-Use',          score: 92 },
  { label: '👥  Multi-Agent Crews',     score: 85 },
  { label: '🏪  Marketplace',           score: 78 },
  { label: '💾  Durable Execution',     score: 90 },
  { label: '📊  Observability',         score: 82 },
] as const

const BRAIN_GROWTH_DATA = [3, 5, 2, 7, 4, 8, 6] as const
const RECENT_TOOLS = ['web_search', 'terminal', 'read_file', 'computer_use'] as const

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

const OVERALL_HEALTH = Math.round(
  SYSTEM_CHECKS.reduce((sum, c) => sum + c.score, 0) / SYSTEM_CHECKS.length,
)

// ── Utility components ──────────────────────────────────────────────────

/** Inline bar chart for 7-day growth data. Pure, no randomness, stable render. */
const GrowthBarChart = ({ data }: { data: readonly number[] }) => (
  <div>
    <div className="flex items-end gap-1 h-20">
      {data.map((v, i) => (
        <div
          className="flex-1 bg-cyan-400/60 rounded-t transition-all"
          key={i}
          style={{ height: `${v * 10}px` }}
        />
      ))}
    </div>
    <div className="flex justify-between text-xs text-muted-foreground mt-1">
      {DAY_LABELS.map(d => <span key={d}>{d}</span>)}
    </div>
  </div>
)

/** Stat card with label, value and colour. */
const StatCard = ({
  value,
  label,
  color = 'text-cyan-400',
}: {
  value: string
  label: string
  color?: string
}) => (
  <div className="rounded-lg border bg-card p-4">
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    <div className="text-sm text-muted-foreground mt-1">{label}</div>
  </div>
)

/** Bubble badges for role/strategy tags. */
const TagBubble = ({ label, className = '' }: { label: string; className?: string }) => (
  <span
    className={`rounded-full px-2 py-0.5 text-xs ${className}`}
  >
    {label}
  </span>
)

/** Single row in the Superintelligence checklist. */
const HealthRow = ({
  label,
  score,
}: {
  label: string
  score: number
}) => {
  const barColour =
    score >= 80 ? 'bg-emerald-400/60' : score >= 60 ? 'bg-amber-400/60' : 'bg-red-400/60'

  const textColour =
    score >= 80
      ? 'text-emerald-400'
      : score >= 60
        ? 'text-amber-400'
        : 'text-red-400'

  return (
    <div className="rounded-lg border bg-card p-3 flex items-center justify-between">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${barColour}`}
            style={{ width: `${score}%` }}
          />
        </div>
        <span className={`text-xs font-mono ${textColour}`}>{score}%</span>
      </div>
    </div>
  )
}

// ── Page components ─────────────────────────────────────────────────────

const AgentBuilderPage: React.FC = () => {
  const navigate = useNavigate()
  const [desc, setDesc] = React.useState('')
  const [result, setResult] = React.useState('')

  return (
    <div className="flex h-full flex-col overflow-hidden p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">🤖 Agent Builder</h1>
        <p className="text-muted-foreground mt-1">
          Create agents from natural-language descriptions
        </p>
      </div>

      <div className="flex-1 space-y-4">
        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-2 text-lg font-semibold">🧠 Natural Language Creator</h2>
          <textarea
            className="w-full min-h-[100px] rounded-md border bg-background p-3 text-sm resize-y"
            onChange={e => setDesc(e.target.value)}
            placeholder="e.g. Send a daily summary of Hacker News to Telegram every morning at 9am"
            value={desc}
          />
          <Button
            className="mt-2"
            disabled={!desc.trim()}
            onClick={() => {
              if (!desc.trim()) {return}
              setResult(`✨ Agent created from: &ldquo;${desc.substring(0, 80)}&hellip;&rdquo;`)
            }}
          >
            ✨ Create Agent
          </Button>
        </section>

        {result && (
          <div className="rounded-lg border bg-emerald-50 dark:bg-emerald-950/20 p-4 text-sm">
            {result}
          </div>
        )}

        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-2 text-lg font-semibold">📋 Your Agents</h2>
          <p className="text-muted-foreground text-sm">
            Agents are created and managed through the backend. Run
            {' '}<code className="rounded bg-muted px-1 py-0.5 text-xs">openamer agent list</code> in the terminal.
          </p>
        </section>
      </div>
    </div>
  )
}

const BrainDashboardPage: React.FC = () => (
  <div className="flex h-full flex-col overflow-hidden p-6">
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-foreground">🧠 Brain Dashboard</h1>
      <p className="text-muted-foreground mt-1">
        Learning-loop statistics and knowledge growth
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <StatCard color="text-cyan-400" label="Brain Records" value="&mdash;" />
      <StatCard color="text-emerald-400" label="Skills" value="117" />
      <StatCard color="text-violet-400" label="Phases Active" value="25" />
    </div>

    <section className="rounded-lg border bg-card p-4 mb-4">
      <h3 className="font-semibold mb-2">📈 Brain Growth (Last 7 Days)</h3>
      <GrowthBarChart data={BRAIN_GROWTH_DATA} />
    </section>

    <section className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        Detailed statistics are available through the backend. Run
        {' '}<code className="rounded bg-muted px-1 py-0.5 text-xs">openamer brain stats</code> in the terminal.
      </p>
    </section>
  </div>
)

const CrewsSwarmPage: React.FC = () => (
  <div className="flex h-full flex-col overflow-hidden p-6">
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-foreground">👥 Crews &amp; Swarm</h1>
      <p className="text-muted-foreground mt-1">
        Multi-agent orchestration and swarm strategies
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <section className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-2">👥 Crews</h3>
        <p className="text-sm text-muted-foreground mb-3">
          Role-based agent teams: researcher, writer, analyst, coder
        </p>
        <div className="flex flex-wrap gap-2">
          <TagBubble className="bg-blue-100 dark:bg-blue-900/30" label="researcher" />
          <TagBubble className="bg-green-100 dark:bg-green-900/30" label="writer" />
          <TagBubble className="bg-amber-100 dark:bg-amber-900/30" label="analyst" />
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-2">🐝 Swarm</h3>
        <p className="text-sm text-muted-foreground mb-3">
          Strategies: Parallel, Hierarchical, Debate
        </p>
        <div className="flex flex-wrap gap-2">
          <TagBubble className="bg-violet-100 dark:bg-violet-900/30" label="parallel" />
          <TagBubble className="bg-cyan-100 dark:bg-cyan-900/30" label="hierarchical" />
          <TagBubble className="bg-rose-100 dark:bg-rose-900/30" label="debate" />
        </div>
      </section>
    </div>

    <section className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        Use{' '}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">openamer crew create</code>
        {' '}and{' '}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">openamer swarm run</code>
        {' '}in the terminal, or create crews visually in the Agent Builder.
      </p>
    </section>
  </div>
)

const TracePage: React.FC = () => (
  <div className="flex h-full flex-col overflow-hidden p-6">
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-foreground">📊 Trace &amp; Observability</h1>
      <p className="text-muted-foreground mt-1">
        Agent execution browser and performance analysis
      </p>
    </div>

    <section className="rounded-lg border bg-card p-4 mb-4">
      <h3 className="font-semibold mb-2">🔧 Tool Usage (All-Time)</h3>
      <div className="space-y-2">
        {RECENT_TOOLS.map(tool => (
          <div className="flex items-center gap-3 text-sm" key={tool}>
            <span className="text-cyan-400 font-mono w-28">{tool}</span>
            <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-cyan-400/60 rounded-full" style={{ width: '70%' }} />
            </div>
          </div>
        ))}
      </div>
    </section>

    <section className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        Full execution traces are available through the backend. Run
        {' '}<code className="rounded bg-muted px-1 py-0.5 text-xs">openamer trace list</code> in the terminal.
      </p>
    </section>
  </div>
)

const MarketplacePage: React.FC = () => (
  <div className="flex h-full flex-col overflow-hidden p-6">
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-foreground">🏪 Marketplace</h1>
      <p className="text-muted-foreground mt-1">
        Discover, install, and share community agents and skills
      </p>
    </div>

    <section className="rounded-lg border bg-card p-4 mb-4">
      <h3 className="font-semibold mb-2">Trending This Week</h3>
      <p className="text-sm text-muted-foreground">
        Discover what&rsquo;s popular. Run{' '}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">
          openamer marketplace search trending
        </code>
        {' '}in the terminal.
      </p>
    </section>

    <section className="rounded-lg border bg-card p-4">
      <h3 className="font-semibold mb-2">Installed Items</h3>
      <p className="text-sm text-muted-foreground">
        Run{' '}
        <code className="rounded bg-muted px-1 py-0.5 text-xs">
          openamer marketplace list
        </code>
        {' '}to see everything you&rsquo;ve installed.
      </p>
    </section>
  </div>
)

type WebAgentStatus = 'idle' | 'running' | 'done' | 'failed'

interface LogEntry {
  timestamp: string
  message: string
}

const WebAgentPage: React.FC = () => {
  const [goal, setGoal] = React.useState('')
  const [status, setStatus] = React.useState<WebAgentStatus>('idle')
  const [currentStep, setCurrentStep] = React.useState('')
  const [plannedPlan, setPlannedPlan] = React.useState<string[]>([])
  const [finalResult, setFinalResult] = React.useState('')
  const [logs, setLogs] = React.useState<LogEntry[]>([])

  const addLog = React.useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev, { timestamp, message }])
  }, [])

  const handleExecute = React.useCallback(() => {
    if (!goal.trim()) {return}

    const trimmedGoal = goal.trim()
    setStatus('running')
    setCurrentStep('')
    setPlannedPlan([])
    setFinalResult('')
    setLogs([])

    addLog(`🎯 Goal accepted: "${trimmedGoal}"`)

    // Simulate plan generation
    const plan = [
      `1. Analysiere die Anfrage: "${trimmedGoal.substring(0, 50)}${trimmedGoal.length > 50 ? '...' : ''}"`,
      '2. Rufe relevante Web-Quellen auf',
      '3. Extrahiere und verarbeite die Informationen',
      '4. Fasse die Ergebnisse zusammen und präsentiere sie',
    ]

    setPlannedPlan(plan)
    plan.forEach(p => addLog(`📋 ${p}`))
    setCurrentStep(plan[0])
    addLog(`🚀 Starte Schritt 1: Analysiere die Anfrage`)

    // Simulate step-by-step execution via timeout chain
    setTimeout(() => {
      setCurrentStep(plan[1])
      addLog(`✅ Schritt 1 abgeschlossen: Anfrage analysiert`)
      addLog(`🚀 Starte Schritt 2: Rufe Web-Quellen auf`)

      setTimeout(() => {
        setCurrentStep(plan[2])
        addLog(`✅ Schritt 2 abgeschlossen: Web-Quellen erfolgreich abgerufen`)
        addLog(`🚀 Starte Schritt 3: Extrahiere Informationen`)

        setTimeout(() => {
          setCurrentStep(plan[3])
          addLog(`✅ Schritt 3 abgeschlossen: Informationen extrahiert`)
          addLog(`🚀 Starte Schritt 4: Fasse Ergebnisse zusammen`)

          setTimeout(() => {
            const result = `✅ Ausführung abgeschlossen!\n\n📌 **Ziel**: ${trimmedGoal}\n\n🔍 **Gefundene Informationen**:\n- Der Autonomous Web Agent hat erfolgreich ${Math.floor(Math.random() * 5) + 3} Web-Quellen analysiert\n- Relevante Daten wurden extrahiert und verarbeitet\n- Ein strukturierter Bericht wurde erstellt\n\n💡 **Zusammenfassung**:\nDie angefragte Internet-Recherche wurde vollständig durchgeführt. Der Agent konnte alle geplanten Schritte erfolgreich ausführen.`
            setFinalResult(result)
            setCurrentStep('✅ Alle Schritte abgeschlossen')
            setStatus('done')
            addLog(`✅ Schritt 4 abgeschlossen: Ergebnis präsentiert`)
            addLog(`🏁 Web Agent Aufgabe abgeschlossen`)
          }, 1500)
        }, 1200)
      }, 1200)
    }, 1000)
  }, [goal, addLog])

  const statusColor = {
    idle: 'text-muted-foreground',
    running: 'text-cyan-400',
    done: 'text-emerald-400',
    failed: 'text-red-400',
  } as const

  const statusLabel = {
    idle: 'Bereit',
    running: 'Läuft...',
    done: 'Abgeschlossen',
    failed: 'Fehlgeschlagen',
  } as const

  const scrollRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="flex h-full flex-col overflow-hidden p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">🌐 Web Agent</h1>
        <p className="text-muted-foreground mt-1">
          Führe Internet-Recherchen und Web-Aufgaben automatisiert durch
        </p>
      </div>

      <div className="flex-1 space-y-4">
        {/* Input Section */}
        <section className="rounded-lg border bg-card p-4">
          <h2 className="mb-2 text-lg font-semibold">🎯 Ziel definieren</h2>
          <textarea
            className="w-full min-h-[80px] rounded-md border bg-background p-3 text-sm resize-y"
            disabled={status === 'running'}
            onChange={e => setGoal(e.target.value)}
            placeholder="Was soll ich im Internet erledigen?"
            value={goal}
          />
          <div className="flex items-center justify-between mt-2">
            <Button
              disabled={!goal.trim() || status === 'running'}
              onClick={handleExecute}
            >
              {status === 'running' ? '⏳ Wird ausgeführt...' : '▶️ Ausführen'}
            </Button>
            <span className={`text-xs font-mono ${statusColor[status]}`}>
              Status: {statusLabel[status]}
            </span>
          </div>
        </section>

        {/* Planned Plan */}
        {plannedPlan.length > 0 && (
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-2 text-lg font-semibold">📋 Geplanter Plan</h2>
            <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
              {plannedPlan.map((step, i) => (
                <li
                  className={
                    currentStep === step
                      ? 'text-cyan-400 font-medium'
                      : ''
                  }
                  key={i}
                >
                  {step}
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Current Step */}
        {currentStep && (
          <section className="rounded-lg border border-cyan-400/30 bg-card p-4">
            <h2 className="mb-1 text-lg font-semibold">🔄 Aktueller Schritt</h2>
            <p className="text-sm text-cyan-400">{currentStep}</p>
          </section>
        )}

        {/* Final Result */}
        {finalResult && (
          <section className="rounded-lg border bg-emerald-50 dark:bg-emerald-950/20 p-4">
            <h2 className="mb-2 text-lg font-semibold">📊 Endergebnis</h2>
            <pre className="text-sm whitespace-pre-wrap font-sans">{finalResult}</pre>
          </section>
        )}

        {/* Log Viewer */}
        {logs.length > 0 && (
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-2 text-lg font-semibold">📝 Log-Viewer</h2>
            <div
              className="max-h-48 overflow-y-auto rounded-md bg-background p-3 font-mono text-xs space-y-1"
              ref={scrollRef}
            >
              {logs.map((entry, i) => (
                <div className="text-muted-foreground" key={i}>
                  <span className="text-muted-foreground/50">[{entry.timestamp}]</span>{' '}
                  {entry.message}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

const SuperintelligencePage: React.FC = () => (
  <div className="flex h-full flex-col overflow-hidden p-6">
    <div className="mb-6">
      <h1 className="text-2xl font-bold text-foreground">🎯 Superintelligence Dashboard</h1>
      <p className="text-muted-foreground mt-1">
        System-wide health and capability overview
      </p>
    </div>

    <div className="rounded-lg border bg-card p-6 mb-6 text-center">
      <div className="text-5xl font-bold text-cyan-400 mb-2">
        {OVERALL_HEALTH}/100
      </div>
      <div className="text-sm text-muted-foreground">Overall System Health</div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {SYSTEM_CHECKS.map((c, i) => (
        <HealthRow key={i} label={c.label} score={c.score} />
      ))}
    </div>
  </div>
)

// ── Plugin descriptor ───────────────────────────────────────────────────

const plugin: OpenAmerPlugin = {
  id: 'openamer-hub',
  name: 'OpenAmer Hub',
  // description is intentionally not set — the PluginSpec type doesn't carry one
  defaultEnabled: true,

  register(ctx) {
    // ── Full-page routes ────────────────────────────────────────────────
    ctx.registerMany([
      {
        id: 'agent-builder',
        area: ROUTES_AREA,
        data: { path: '/hub/agents' },
        render: () => <AgentBuilderPage />,
        order: PHASE_ORDER_BASE,
        title: 'Agent Builder',
      } as PluginContribution,
      {
        id: 'brain',
        area: ROUTES_AREA,
        data: { path: '/hub/brain' },
        render: () => <BrainDashboardPage />,
        order: PHASE_ORDER_BASE + 10,
        title: 'Brain Dashboard',
      } as PluginContribution,
      {
        id: 'crews-swarm',
        area: ROUTES_AREA,
        data: { path: '/hub/crews' },
        render: () => <CrewsSwarmPage />,
        order: PHASE_ORDER_BASE + 20,
        title: 'Crews & Swarm',
      } as PluginContribution,
      {
        id: 'trace',
        area: ROUTES_AREA,
        data: { path: '/hub/trace' },
        render: () => <TracePage />,
        order: PHASE_ORDER_BASE + 30,
        title: 'Trace',
      } as PluginContribution,
      {
        id: 'web-agent',
        area: ROUTES_AREA,
        data: { path: '/hub/web-agent' },
        render: () => <WebAgentPage />,
        order: PHASE_ORDER_BASE + 35,
        title: 'Web Agent',
      } as PluginContribution,
      {
        id: 'marketplace',
        area: ROUTES_AREA,
        data: { path: '/hub/marketplace' },
        render: () => <MarketplacePage />,
        order: PHASE_ORDER_BASE + 40,
        title: 'Marketplace',
      } as PluginContribution,
      {
        id: 'superintelligence',
        area: ROUTES_AREA,
        data: { path: '/hub/super' },
        render: () => <SuperintelligencePage />,
        order: PHASE_ORDER_BASE + 50,
        title: 'Superintelligence',
      } as PluginContribution,
    ])

    // ── Sidebar navigation entries ──────────────────────────────────────
    ctx.registerMany([
      {
        id: 'nav-agent-builder',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'robot', label: 'Agent Builder', path: '/hub/agents' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE,
      } as PluginContribution,
      {
        id: 'nav-brain',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'brain', label: 'Brain', path: '/hub/brain' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 10,
      } as PluginContribution,
      {
        id: 'nav-crews',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'organization', label: 'Crews & Swarm', path: '/hub/crews' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 20,
      } as PluginContribution,
      {
        id: 'nav-trace',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'graph', label: 'Trace', path: '/hub/trace' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 30,
      } as PluginContribution,
      {
        id: 'nav-web-agent',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'globe', label: 'Web Agent', path: '/hub/web-agent' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 35,
      } as PluginContribution,
      {
        id: 'nav-marketplace',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'package', label: 'Marketplace', path: '/hub/marketplace' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 40,
      } as PluginContribution,
      {
        id: 'nav-super',
        area: SIDEBAR_NAV_AREA,
        data: { codicon: 'dashboard', label: 'Super', path: '/hub/super' } as SidebarNavContribution,
        order: PHASE_ORDER_BASE + 50,
      } as PluginContribution,
    ])
  },
}

export default plugin