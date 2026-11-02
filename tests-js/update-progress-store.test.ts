/// <reference types="vite/client" />
import { expect, test, vi } from 'vitest'

import { $bootstrap, initialize } from '../apps/bootstrap-installer/src/store'

const transport = vi.hoisted(() => ({
  listener: undefined as ((event: { payload: Record<string, unknown> }) => void) | undefined
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (command: string) => command === 'get_mode' ? 'install' : 'test-path')
}))

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async (_channel: string, listener: typeof transport.listener) => {
    transport.listener = listener

    return () => {}
  })
}))

test('a duplicate manifest preserves the live stage and its log buffer', async () => {
  await initialize()

  const emit = (payload: Record<string, unknown>) => {
    expect(transport.listener).toBeDefined()
    transport.listener?.({ payload })
  }

  const manifest = {
    type: 'manifest',
    protocolVersion: 1,
    stages: [{ name: 'update', title: 'Update', category: 'update', needs_user_input: false }]
  }

  emit(manifest)
  emit({ type: 'stage', name: 'update', state: 'running' })
  emit({ type: 'log', stage: 'update', line: 'Still working', stream: 'stdout' })
  const previous = $bootstrap.get()

  emit(manifest)

  expect($bootstrap.get().currentStage).toBe('update')
  expect($bootstrap.get().logs).toEqual(previous.logs)
  expect($bootstrap.get().stages.update.startedAt).toBe(previous.stages.update.startedAt)
})
