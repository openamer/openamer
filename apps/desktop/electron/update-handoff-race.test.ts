import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'

import ts from 'typescript'
import { afterEach, test, vi } from 'vitest'

import { createBackendConnectionState } from './backend-connection-state'
import { readLiveUpdateMarker, waitForUpdateRelease, writeUpdateMarker } from './update-marker'

afterEach(() => vi.useRealTimers())

// Exercise the actual Electron function bodies without booting Electron or
// mutating the user's installation. AST extraction avoids source snapshots.
function mainFunction(name: string, globals: Record<string, unknown>) {
  const sourcePath = new URL('./main.ts', import.meta.url)

  const source = fs.readFileSync(sourcePath, 'utf8')

  const ast = ts.createSourceFile('main.ts', source, ts.ScriptTarget.Latest, true)
  const declaration = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name)
  assert.ok(declaration, `production function ${name} must exist`)

  const compiled = ts.transpileModule(declaration.getText(ast), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 }
  }).outputText

  const context: Record<string, unknown> = { ...globals, Date, setTimeout }
  const fn = vm.runInNewContext(`${compiled}; ${name}`, context)

  return { fn, context }
}

test('production startup gate blocks reconnect before any updater marker exists', async () => {
  vi.useFakeTimers()

  const { fn, context } = mainFunction('waitForUpdateToFinish', {
    IS_WINDOWS: true,
    updateInFlight: true,
    bootstrapRecoveryInFlight: false,
    isQuittingForHandoff: false,
    OPENAMER_HOME: 'unused',
    UPDATE_WAIT_POLL_MS: 10,
    UPDATE_WAIT_TIMEOUT_MS: 1000,
    readLiveUpdateMarker: () => null,
    waitForUpdateRelease,
    advanceBootProgress: async () => {},
    rememberLog: () => {}
  })

  let spawned = false

  const reconnect = fn().then(() => {
    spawned = true
  })

  await vi.advanceTimersByTimeAsync(30)
  assert.equal(spawned, false, 'local teardown must block even without an updater marker')
  context.updateInFlight = false
  await vi.advanceTimersByTimeAsync(10)
  await reconnect
  assert.equal(spawned, true, 'an aborted update must allow reconnect again')
})

test('production teardown retires its process owner before delivering SIGTERM', async () => {
  const state = createBackendConnectionState<{ pid: number; killed: boolean; kill: () => void }, string>()
  let teardownRestartEvents = 0
  const attempt = state.startAttempt()

  const child = {
    pid: 123,
    killed: false,
    kill: () => {
      if (state.clearForCurrentProcess(owner)) {teardownRestartEvents += 1}
    }
  }

  const owner = state.attachProcess(attempt, child)
  assert.ok(owner)

  const { fn } = mainFunction('releaseBackendLock', {
    IS_WINDOWS: true,
    backendConnectionState: state,
    backendPool: new Map(),
    stopAllPoolBackends: () => {},
    forceKillProcessTree: () => {},
    venvOpenAmerShimPath: () => 'unused',
    isShimLocked: () => false,
    rememberLog: () => {}
  })

  assert.equal((await fn('unused', 'test')).unlocked, true)
  assert.equal(teardownRestartEvents, 0, 'intentional shutdown must not broadcast a reconnect-triggering exit')
  assert.equal(state.isCurrentAttempt(attempt), false)
})

test('real updater PID marker keeps startup blocked after local handoff ends', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'openamer-real-update-gate-'))
  const updater = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { windowsHide: true })

  try {
    await once(updater, 'spawn')
    assert.ok(updater.pid)
    let localHandoff = true
    let spawned = false

    const reconnect = waitForUpdateRelease({
      isBlocked: () => localHandoff || Boolean(readLiveUpdateMarker(home)),
      pollMs: 5,
      timeoutMs: 5000
    }).then(() => {
      spawned = true
    })

    writeUpdateMarker(home, updater.pid)
    localHandoff = false
    await new Promise(resolve => setTimeout(resolve, 30))
    assert.equal(spawned, false, 'a genuinely live updater process must keep the gate closed')
    const exited = once(updater, 'exit')
    updater.kill()
    await exited
    await reconnect
    assert.equal(spawned, true)
  } finally {
    if (updater.exitCode === null) {updater.kill()}
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('the updater marker takes over without a spawn gap after local handoff', async () => {
  vi.useFakeTimers()
  let localHandoff = true
  let updaterMarker = false
  let spawned = false

  const reconnect = waitForUpdateRelease({
    isBlocked: () => localHandoff || updaterMarker,
    pollMs: 10,
    timeoutMs: 1000
  }).then(() => {
    spawned = true
  })

  updaterMarker = true
  localHandoff = false
  await vi.advanceTimersByTimeAsync(50)
  assert.equal(spawned, false)
  updaterMarker = false
  await vi.advanceTimersByTimeAsync(10)
  await reconnect
  assert.equal(spawned, true)
})

test('a timeout never launches a backend under a still-running update', async () => {
  vi.useFakeTimers()
  let spawned = false

  const reconnect = waitForUpdateRelease({ isBlocked: () => true, pollMs: 10, timeoutMs: 30 }).then(() => {
    spawned = true
  })

  const rejected = assert.rejects(reconnect, /update.*still in progress/i)
  await vi.advanceTimersByTimeAsync(40)
  await rejected
  assert.equal(spawned, false)
})

test.runIf(process.platform === 'win32')(
  'Windows teardown unlocks a real running shim without a reconnect respawn',
  async () => {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), 'openamer-native-handoff-'))
    const shim = path.join(home, 'openamer.exe')
    fs.copyFileSync(process.execPath, shim)
    const child = spawn(shim, ['-e', 'setInterval(() => {}, 1000)'], { windowsHide: true })
    let exited: Promise<unknown> | undefined

    try {
      await once(child, 'spawn')
      const state = createBackendConnectionState<typeof child, string>()
      const attempt = state.startAttempt()
      const owner = state.attachProcess(attempt, child)
      assert.ok(owner)
      let exitNotifications = 0
      child.on('exit', () => {
        if (state.clearForCurrentProcess(owner)) {exitNotifications += 1}
      })
      exited = once(child, 'exit')
      const { fn: isLocked } = mainFunction('isShimLocked', { IS_WINDOWS: true, fs })
      assert.equal(isLocked(shim), true, 'the real executable must be Windows write-locked while running')
      let localHandoff = true
      let reconnected = false

      const reconnect = waitForUpdateRelease({ isBlocked: () => localHandoff, pollMs: 5, timeoutMs: 5000 }).then(() => {
        reconnected = true
      })

      const { fn: release } = mainFunction('releaseBackendLock', {
        IS_WINDOWS: true,
        backendConnectionState: state,
        backendPool: new Map(),
        stopAllPoolBackends: () => {},
        forceKillProcessTree: (pid: number) => {
          if (pid === child.pid) {child.kill('SIGKILL')}
        },
        venvOpenAmerShimPath: () => shim,
        isShimLocked: isLocked,
        rememberLog: () => {}
      })

      assert.equal((await release(home, 'native-test')).unlocked, true)
      await exited
      assert.equal(isLocked(shim), false, 'the updater can now write its own executable')
      assert.equal(exitNotifications, 0, 'intentional teardown is not a backend crash')
      assert.equal(reconnected, false, 'unlocking the shim must not reopen the startup gate prematurely')
      localHandoff = false
      await reconnect
      assert.equal(reconnected, true)
    } finally {
      if (child.exitCode === null) {child.kill()}

      if (exited) {await exited}
      fs.rmSync(home, { recursive: true, force: true })
    }
  }
)

test('recovery refuses handoff when the environment stays locked and clears its local gate', async () => {
  let updaterSpawns = 0

  const { fn, context } = mainFunction('handOffWindowsBootstrapRecovery', {
    IS_WINDOWS: true,
    IS_PACKAGED: true,
    bootstrapRecoveryInFlight: false,
    isQuittingForHandoff: false,
    resolveUpdaterBinary: () => 'fixture-updater.exe',
    resolveUpdateRoot: () => 'fixture-root',
    readDesktopUpdateConfig: () => ({ branch: 'main' }),
    directoryExists: () => false,
    fileExists: () => true,
    path,
    chooseUpdaterArgs: () => ['--update'],
    releaseBackendLockForUpdate: async () => ({ unlocked: false }),
    spawnUpdaterProcess: () => { updaterSpawns += 1 }
  })

  await assert.rejects(fn('test'), /could not release the running installation/)
  assert.equal(updaterSpawns, 0)
  assert.equal(context.bootstrapRecoveryInFlight, false)
  assert.equal(context.isQuittingForHandoff, false)
})

test('recovery spawn failure releases its gate instead of stranding reconnects', async () => {
  const { fn, context } = mainFunction('handOffWindowsBootstrapRecovery', {
    IS_WINDOWS: true,
    IS_PACKAGED: true,
    bootstrapRecoveryInFlight: false,
    isQuittingForHandoff: false,
    OPENAMER_HOME: 'fixture-home',
    process: { env: {} },
    resolveUpdaterBinary: () => 'fixture-updater.exe',
    resolveUpdateRoot: () => 'fixture-root',
    readDesktopUpdateConfig: () => ({ branch: 'main' }),
    directoryExists: () => false,
    fileExists: () => true,
    path,
    chooseUpdaterArgs: () => ['--update'],
    pathWithOpenAmerManagedNode: () => 'fixture-path',
    releaseBackendLockForUpdate: async () => ({ unlocked: true }),
    spawnUpdaterProcess: () => { throw new Error('injected spawn failure') }
  })

  await assert.rejects(fn('test'), /injected spawn failure/)
  assert.equal(context.bootstrapRecoveryInFlight, false)
  assert.equal(context.isQuittingForHandoff, false)
})

test('a prepared attempt invalidated by update teardown is rejected before spawning', () => {
  const state = createBackendConnectionState<object, string>()
  const prepared = state.startAttempt()
  assert.equal(state.isCurrentAttempt(prepared), true)
  state.invalidate()
  assert.equal(state.isCurrentAttempt(prepared), false)
  assert.equal(state.isCurrentAttempt(state.startAttempt()), true)
})
