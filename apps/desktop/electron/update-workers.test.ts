import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

import ts from 'typescript'
import { afterEach, test, vi } from 'vitest'

import { activeUpdateWorkers, waitForUpdateWorkers } from './update-workers'

afterEach(() => vi.useRealTimers())

test('workers finish naturally before update proceeds', async () => {
  let reads = 0
  const waits: number[][] = []
  await waitForUpdateWorkers({
    inspect: async () => (++reads === 1 ? [42] : []),
    onWait: pids => waits.push(pids),
    pollMs: 1
  })
  assert.deepEqual(waits, [[42]])
  assert.equal(reads, 2)
})

test('bounded wait fails closed and does not terminate a worker', async () => {
  await assert.rejects(
    waitForUpdateWorkers({ inspect: async () => [42], onWait: () => {}, timeoutMs: 0 }),
    /deferred without stopping/
  )
})

test('inventory failure is not interpreted as no active workers', async () => {
  await assert.rejects(activeUpdateWorkers('C:\\fixture', 'missing-powershell-executable'), /Cannot inspect/)
})

test('production update waits before any backup or backend teardown', async () => {
  const source = fs.readFileSync(new URL('./main.ts', import.meta.url), 'utf8')
  const ast = ts.createSourceFile('main.ts', source, ts.ScriptTarget.Latest, true)
  const node = ast.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'applyUpdates')!
  const code = ts.transpileModule(node.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const events: string[] = []

  const context = {
    updateInFlight: false,
    IS_WINDOWS: true,
    IS_MAC: false,
    process: { pid: 1, env: {} },
    path,
    resolveUpdaterBinary: () => 'updater',
    emitUpdateProgress: () => {},
    repairMacUpdaterHelper: () => {},
    resolveUpdateRoot: () => 'root',
    readDesktopUpdateConfig: () => ({}),
    resolveHealedBranch: async () => 'main',
    DEFAULT_UPDATE_BRANCH: 'main',
    OPENAMER_HOME: 'home',
    readLiveUpdateMarker: () => null,
    writeUpdateMarker: () => {},
    claimUpdateWorkerDrain: () => {
      events.push('claim')
    },
    releaseUpdateWorkerDrain: () => {
      events.push('release')
    },
    activeUpdateWorkers: async () => [42],
    windowsPowerShellPath: () => 'powershell',
    waitForUpdateWorkers: async () => {
      events.push('wait')
      throw new Error('still working')
    },
    preflightStateDb: () => {
      events.push('backup')
      throw new Error('backup should not run')
    },
    releaseBackendLockForUpdate: async () => {
      events.push('teardown')

      return { unlocked: true }
    },
    rememberLog: () => {}
  }

  const fn = vm.runInNewContext(`${code}; applyUpdates`, context)
  await assert.rejects(fn(), /still working/)
  assert.deepEqual(events, ['claim', 'wait', 'release'])
  assert.equal(context.updateInFlight, false)
})
