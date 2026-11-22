import type { AgentPluginRow } from '@/types/openamer'

// Pure plugin-list logic, kept out of the component so it is testable without
// a React tree. `runtime_status` is the backend loader's own verdict — the UI
// never infers state from a second source.

export const PLUGIN_STATUS_KEY = {
  disabled: 'pluginsStatusDisabled',
  enabled: 'pluginsStatusEnabled',
  inactive: 'pluginsStatusInactive'
} as const

export type PluginStatusKey = (typeof PLUGIN_STATUS_KEY)[AgentPluginRow['runtime_status']]

export const isPluginOn = (row: AgentPluginRow): boolean => row.runtime_status === 'enabled'

export const pluginStatusKey = (row: AgentPluginRow): PluginStatusKey => PLUGIN_STATUS_KEY[row.runtime_status]

export function pluginMatches(row: AgentPluginRow, rawNeedle: string): boolean {
  const needle = rawNeedle.trim().toLowerCase()

  if (!needle) {
    return true
  }

  return `${row.name} ${row.description} ${row.source}`.toLowerCase().includes(needle)
}
