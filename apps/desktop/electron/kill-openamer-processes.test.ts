import assert from 'node:assert/strict'

import { test } from 'vitest'

import {
  computeAncestorChain,
  killOtherOpenAmerProcesses,
  listOpenAmerProcessesViaPowerShell
} from './kill-openamer-processes'

test('killOtherOpenAmerProcesses is a no-op off Windows', () => {
  const killed: number[] = []

  const result = killOtherOpenAmerProcesses('C:\\root', {
    isWindows: false,
    listOpenAmerProcesses: () => [
      { pid: 1, parentPid: 0 },
      { pid: 2, parentPid: 0 }
    ],
    killProcessTree: (pid: number) => killed.push(pid)
  })

  assert.deepEqual(result, [])
  assert.deepEqual(killed, [])
})

test('killOtherOpenAmerProcesses tree-kills every non-ancestor pid', () => {
  const killed: number[] = []

  const result = killOtherOpenAmerProcesses('C:\\root', {
    isWindows: true,
    listOpenAmerProcesses: () => [
      { pid: 111, parentPid: 0 },
      { pid: 222, parentPid: 0 },
      { pid: 333, parentPid: 0 }
    ],
    killProcessTree: (pid: number) => killed.push(pid)
  })

  assert.deepEqual(result, [111, 222, 333])
  assert.deepEqual(killed, [111, 222, 333])
})

test('killOtherOpenAmerProcesses skips the app ancestor chain', () => {
  // self pid = 1000; its ancestors are 900 -> 800 -> 700. Those must be
  // skipped (they exit on their own); the detached sibling 500 is killed.
  const killed: number[] = []

  const result = killOtherOpenAmerProcesses('C:\\root', {
    isWindows: true,
    selfPid: 1000,
    listOpenAmerProcesses: () => [
      { pid: 1000, parentPid: 900 },
      { pid: 900, parentPid: 800 },
      { pid: 800, parentPid: 700 },
      { pid: 700, parentPid: 0 },
      { pid: 500, parentPid: 0 }
    ],
    killProcessTree: (pid: number) => killed.push(pid)
  })

  assert.deepEqual(result, [500])
  assert.deepEqual(killed, [500])
})

test('killOtherOpenAmerProcesses returns empty when no pids match', () => {
  const killed: number[] = []

  const result = killOtherOpenAmerProcesses('C:\\root', {
    isWindows: true,
    listOpenAmerProcesses: () => [],
    killProcessTree: (pid: number) => killed.push(pid)
  })

  assert.deepEqual(result, [])
  assert.deepEqual(killed, [])
})

test('computeAncestorChain walks parent links and excludes self', () => {
  const processes = [
    { pid: 10, parentPid: 9 },
    { pid: 9, parentPid: 8 },
    { pid: 8, parentPid: 0 },
    { pid: 7, parentPid: 0 }
  ]

  const ancestors = computeAncestorChain(10, processes)

  assert.deepEqual([...ancestors].sort(), [8, 9])
})

test('computeAncestorChain returns empty when pid has no parent in the set', () => {
  const processes = [{ pid: 10, parentPid: 0 }]

  assert.deepEqual([...computeAncestorChain(10, processes)], [])
})

test('computeAncestorChain is bounded against cycles', () => {
  const processes = [
    { pid: 1, parentPid: 2 },
    { pid: 2, parentPid: 1 }
  ]

  const ancestors = computeAncestorChain(1, processes)

  // The walk terminates on the cycle (revisiting an already-seen ancestor)
  // rather than looping forever; both pids end up in the set.
  assert.deepEqual([...ancestors].sort(), [1, 2])
})

test('listOpenAmerProcessesViaPowerShell returns an array of pid/parentPid objects', () => {
  // The real function shells out to PowerShell; on a machine without it (or
  // with no matching processes) it returns []. Assert the shape contract.
  const result = listOpenAmerProcessesViaPowerShell('C:\\nonexistent', process.pid)

  assert.ok(Array.isArray(result))

  for (const info of result) {
    assert.ok(Number.isInteger(info.pid))
    assert.ok(Number.isInteger(info.parentPid))
  }
})
