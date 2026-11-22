import { describe, expect, it } from 'vitest'

import type { AgentPluginRow } from '@/types/openamer'

import { isPluginOn, pluginMatches, pluginStatusKey } from './plugins'

const row = (over: Partial<AgentPluginRow> = {}): AgentPluginRow => ({
  auth_command: '',
  auth_required: false,
  can_remove: false,
  can_update_git: false,
  dashboard_manifest: null,
  description: 'Drive a live TouchDesigner session',
  has_dashboard_manifest: false,
  name: 'touchdesigner-mcp',
  path: 'C:/plugins/touchdesigner-mcp',
  runtime_status: 'inactive',
  source: 'git',
  user_hidden: false,
  version: '1.0.0',
  ...over
})

describe('plugin list logic', () => {
  it('only an explicit enabled verdict reads as on', () => {
    expect(isPluginOn(row({ runtime_status: 'enabled' }))).toBe(true)
    expect(isPluginOn(row({ runtime_status: 'disabled' }))).toBe(false)
    // inactive = discovered but never enabled — must not look switched on
    expect(isPluginOn(row({ runtime_status: 'inactive' }))).toBe(false)
  })

  it('maps each runtime status to its own label key', () => {
    expect(pluginStatusKey(row({ runtime_status: 'enabled' }))).toBe('pluginsStatusEnabled')
    expect(pluginStatusKey(row({ runtime_status: 'disabled' }))).toBe('pluginsStatusDisabled')
    expect(pluginStatusKey(row({ runtime_status: 'inactive' }))).toBe('pluginsStatusInactive')
  })

  it('matches name, description and source, case- and space-insensitively', () => {
    expect(pluginMatches(row(), '')).toBe(true)
    expect(pluginMatches(row(), '   ')).toBe(true)
    expect(pluginMatches(row(), 'TOUCH')).toBe(true)
    expect(pluginMatches(row(), 'touchdesigner')).toBe(true)
    expect(pluginMatches(row(), 'session')).toBe(true)
    expect(pluginMatches(row(), 'git')).toBe(true)
    expect(pluginMatches(row(), 'kanban')).toBe(false)
  })
})
