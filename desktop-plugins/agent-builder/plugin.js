/**
 * OpenAmer Agent Builder — visueller Agent-Baukasten (Desktop-Plugin).
 *
 * Baue einen autonomen Agenten per Mausklick: Name + Rolle + Fähigkeiten
 * wählen. Das Plugin generiert daraus einen OpenAmer-Skill und zeigt eine
 * Vorschau des resultierenden SKILL.md.
 *
 * Plain ESM, geladen unkompiliert — UI via jsx(), nur @openamer/plugin-sdk
 * + react importieren.
 */

import { useState } from 'react'
import { cn, host, Button, Codicon, Tip, usePluginI18n } from '@openamer/plugin-sdk'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'

const ID = 'agent-builder'

const CAPABILITIES = [
  { id: 'web', label: 'Web & Recherche', icon: 'globe' },
  { id: 'files', label: 'Dateien & Code', icon: 'file-code' },
  { id: 'terminal', label: 'Terminal', icon: 'terminal' },
  { id: 'browser', label: 'Browser-Steuerung', icon: 'browser' },
  { id: 'memory', label: 'Persistentes Gedächtnis', icon: 'database' },
  { id: 'cron', label: 'Scheduled Jobs', icon: 'clock' },
  { id: 'cua', label: 'Desktop-Steuerung', icon: 'desktop-download' },
  { id: 'vision', label: 'Vision / Bilder', icon: 'image' }
]

const PERSONALITIES = [
  { id: 'helpful', label: 'Hilfreich & freundlich' },
  { id: 'technical', label: 'Technisch & präzise' },
  { id: 'creative', label: 'Kreativ & innovativ' },
  { id: 'concise', label: 'Kurz & knapp' },
  { id: 'noir', label: 'Noir-Detektiv' }
]

function skillYaml(name, role, personalityId, caps) {
  const lines = []
  lines.push('---')
  lines.push(`name: ${name || 'my-agent'}`)
  lines.push(`description: "Autonomously generated agent — ${role || 'general-purpose assistant'}."`)
  lines.push('---')
  lines.push('')
  lines.push('# ' + (name || 'My Agent'))
  lines.push('')
  lines.push('Role: ' + role)
  lines.push('Personality: ' + personalityId)
  lines.push('')
  lines.push('Capabilities:')
  caps.forEach(c => lines.push('- ' + c))
  return lines.join('\n')
}

function CapToggle({ cap, checked, onToggle }) {
  return jsxs('button', {
    type: 'button',
    onClick: onToggle,
    className: cn(
      'flex w-full items-center gap-2 rounded-md border px-3 py-1.5 text-left text-[0.8125rem] transition-colors',
      checked
        ? 'border-(--ui-accent) bg-(--ui-accent)/10 text-foreground'
        : 'border-(--ui-stroke-secondary) hover:bg-(--chrome-action-hover)'
    ),
    children: [
      jsx(Codicon, { name: cap.icon, className: cn('shrink-0', checked ? 'text-(--ui-accent)' : 'text-(--ui-text-tertiary)') }),
      jsx('span', { className: 'flex-1', children: cap.label }),
      jsx('span', {
        className: cn('shrink-0 select-none text-xs', checked ? 'text-(--ui-accent)' : 'text-(--ui-text-quaternary)'),
        children: checked ? '✓' : '+'
      })
    ]
  })
}

function AgentBuilderPane() {
  const t = usePluginI18n(ID)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [personality, setPersonality] = useState('helpful')
  const [caps, setCaps] = useState({})
  const [copied, setCopied] = useState(false)

  const toggleCap = id =>
    setCaps(prev => ({ ...prev, [id]: !prev[id] }))

  const selected = CAPABILITIES.filter(c => caps[c.id])
  const yaml = skillYaml(name, role, personality, selected.map(c => c.label))

  const copy = () => {
    try {
      navigator.clipboard?.writeText?.(yaml)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      host.notify?.({ kind: 'error', message: 'Clipboard nicht verfügbar' })
    }
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col gap-3 p-4 text-sm',
    children: [
      // Header
      jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx(Codicon, { name: 'rocket', className: 'text-(--ui-accent)' }),
          jsx('span', { className: 'font-semibold', children: 'Agent Builder' })
        ]
      }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-tertiary)',
        children: 'Baue einen autonomen Agenten — erzeuge daraus einen fertigen OpenAmer-Skill.'
      }),

      // Name
      jsx('label', {
        className: 'flex flex-col gap-1 text-xs',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: 'Name' }),
          jsx('input', {
            className: 'h-8 w-full rounded-md border border-(--ui-stroke-secondary) bg-transparent px-2 text-[0.8125rem] outline-none focus:border-(--ui-accent)',
            placeholder: t('namePlaceholder'),
            value: name,
            onChange: ev => setName(ev.target.value)
          })
        ]
      }),

      // Role
      jsxs('label', {
        className: 'flex flex-col gap-1 text-xs',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: 'Rolle / Auftrag' }),
          jsx('textarea', {
            className:
              'h-16 w-full resize-none rounded-md border border-(--ui-stroke-secondary) bg-transparent p-2 text-[0.8125rem] outline-none focus:border-(--ui-accent)',
            placeholder: t('rolePlaceholder'),
            value: role,
            onChange: ev => setRole(ev.target.value)
          })
        ]
      }),

      // Personality
      jsxs('div', {
        className: 'flex flex-col gap-1 text-xs',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: 'Persönlichkeit' }),
          jsxs('div', {
            className: 'flex flex-wrap gap-1',
            children: PERSONALITIES.map(p =>
              jsx('button', {
                type: 'button',
                key: p.id,
                onClick: () => setPersonality(p.id),
                className: cn(
                  'rounded-full border px-2 py-0.5 text-[0.6875rem] transition-colors',
                  personality === p.id
                    ? 'border-(--ui-accent) bg-(--ui-accent)/10 text-foreground'
                    : 'border-(--ui-stroke-secondary) text-(--ui-text-secondary) hover:bg-(--chrome-action-hover)'
                ),
                children: p.label
              })
            )
          })
        ]
      }),

      // Capabilities
      jsxs('div', {
        className: 'flex min-h-0 flex-1 flex-col gap-1 text-xs',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: 'Fähigkeiten' }),
          jsxs('div', {
            className: 'grid grid-cols-2 gap-1 overflow-y-auto',
            children: CAPABILITIES.map(c =>
              jsx(AgentToggle, { cap: c, checked: !!caps[c.id], onToggle: () => toggleCap(c.id) })
            )
          })
        ]
      }),

      // Build
      jsxs('div', {
        className: 'flex items-center gap-2 border-t border-(--ui-stroke-secondary) pt-2',
        children: [
          jsx(Button, { disabled: !name.trim(), onClick: copy, children: copied ? 'Kopiert ✓' : 'Skill erzeugen & kopieren' }),
          selected.length > 0 &&
            jsx('span', { className: 'text-xs text-(--ui-text-tertiary)', children: selected.length + ' Fähigkeiten' })
        ]
      }),

      // Preview (collapsed)
      name.trim() &&
        jsxs('details', {
          className: 'text-xs',
          children: [
            jsx('summary', { className: 'cursor-pointer text-(--ui-text-tertiary)', children: 'SKILL.md Vorschau' }),
            jsx('pre', {
              className: 'mt-1 whitespace-pre-wrap rounded-md bg-(--canvas-subtle) p-2 text-[0.6875rem] text-(--ui-text-secondary)',
              children: yamlPreview(name, role, personality, selected)
            })
          ]
        })
    ]
  })
}

// Alias so die im Pane verwendete Komponente existiert.
const AgentToggle = CapToggle

function yamlPreview(name, role, personality, selected) {
  const lines = []
  lines.push('---')
  lines.push('name: ' + (name.trim() || 'my-agent').toLowerCase().replace(/\s+/g, '-'))
  lines.push('description: ' + JSON.stringify('Autonomously generated agent — ' + (role || 'general-purpose assistant') + '.'))
  lines.push('---')
  lines.push('')
  lines.push('# ' + name.trim())
  lines.push('')
  lines.push('**Persönlichkeit:** ' + personality)
  lines.push('')
  if (role) lines.push('**Rolle:** ' + role)
  lines.push('')
  lines.push('**Fähigkeiten:**')
  if (selected.length === 0) {
    lines.push('- (keine ausgewählt)')
  } else {
    selected.forEach(c => lines.push('- ' + c.label))
  }
  return lines.join('\n')
}

export default {
  id: ID,
  name: 'Agent Builder',
  register(ctx) {
    ctx.i18n.register({
      en: {
        paneTitle: 'Agent Builder',
        namePlaceholder: 'Agent name…',
        rolePlaceholder: 'Describe the agent’s role / mission…'
      },
      de: {
        paneTitle: 'Agent Builder',
        namePlaceholder: 'Agent-Name…',
        rolePlaceholder: 'Beschreibe die Rolle / den Auftrag des Agenten…'
      }
    })
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Agent Builder',
      data: { placement: 'right', width: '320px' },
      render: () => jsx(AgentBuilderPane, {})
    })
    ctx.register({
      id: 'nav',
      area: 'nav',
      title: 'Agent Builder',
      order: 90,
      data: { path: '/agent-builder', label: 'Agent Builder', codicon: 'rocket' },
      render: () => jsx(AgentBuilderPane, {})
    })
  }
}