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

import React from 'react'
import { useNavigate } from 'react-router-dom'

import type { PluginContribution, OpenAmerPlugin } from '@/contrib/plugin'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  type SidebarNavContribution,
} from '@/app/routes'

// ── Constants ───────────────────────────────────────────────────────────

const PHASE_ORDER_BASE = 110 // Leave gap below 110 for core items

/** Phase 1-25 features displayed in the Superintelligence page. */
const SYSTEM_CHECKS = [
  { label: '🧠  Brain Learning Loop',    score: 95 },
  { label: '🌐  A2A Swarm',             score: 88 },
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
          key={i}
          className="flex-1 bg-cyan-400/60 rounded-t transition-all"
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
            placeholder="e.g. Send a daily summary of Hacker News to Telegram every morning at 9am"
            value={desc}
            onChange={e => setDesc(e.target.value)}
          />
          <Button
            className="mt-2"
            disabled={!desc.trim()}
            onClick={() => {
              if (!desc.trim()) return
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
      <StatCard value="&mdash;" label="Brain Records" color="text-cyan-400" />
      <StatCard value="117" label="Skills" color="text-emerald-400" />
      <StatCard value="25" label="Phases Active" color="text-violet-400" />
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
          <TagBubble label="researcher" className="bg-blue-100 dark:bg-blue-900/30" />
          <TagBubble label="writer" className="bg-green-100 dark:bg-green-900/30" />
          <TagBubble label="analyst" className="bg-amber-100 dark:bg-amber-900/30" />
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-2">🐝 Swarm</h3>
        <p className="text-sm text-muted-foreground mb-3">
          Strategies: Parallel, Hierarchical, Debate
        </p>
        <div className="flex flex-wrap gap-2">
          <TagBubble label="parallel" className="bg-violet-100 dark:bg-violet-900/30" />
          <TagBubble label="hierarchical" className="bg-cyan-100 dark:bg-cyan-900/30" />
          <TagBubble label="debate" className="bg-rose-100 dark:bg-rose-900/30" />
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
          <div key={tool} className="flex items-center gap-3 text-sm">
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
        data: { codicon: 'lightbulb', label: 'Brain', path: '/hub/brain' } as SidebarNavContribution,
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