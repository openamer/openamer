import { expect, test } from 'vitest'

import {
  countDone,
  isTerminal,
  mergeManifest,
  shouldResetBeforeStart,
  type StageInfo,
  type StageOrder
} from '../apps/bootstrap-installer/src/update-progress-state'

const MANIFEST: StageInfo[] = [
  { name: 'handoff', title: 'Preparing to update', category: 'update', needs_user_input: false },
  {
    name: 'update',
    title: 'Downloading the latest version',
    category: 'update',
    needs_user_input: false
  },
  {
    name: 'rebuild',
    title: 'Rebuilding the desktop app',
    category: 'update',
    needs_user_input: false
  }
]

test('a stage with no reported state is not done', () => {
  const order = mergeManifest({ stageOrder: [], stages: {} }, MANIFEST)

  expect(countDone(order.stageOrder, order.stages)).toEqual({
    done: 0,
    total: 3,
    fraction: 0
  })
})

test('a re-emitted manifest keeps the state of stages that already ran', () => {
  // The measured incident: Rust emitted `handoff=Succeeded`, then the duplicate
  // start_update made it re-emit the manifest. The progress must survive.
  let order = mergeManifest({ stageOrder: [], stages: {} }, MANIFEST)

  order = {
    ...order,
    stages: {
      ...order.stages,
      handoff: { info: order.stages.handoff.info, state: 'succeeded' },
      update: { info: order.stages.update.info, state: 'running' }
    }
  }

  expect(countDone(order.stageOrder, order.stages).done).toBe(1)

  // Now the duplicate manifest arrives.
  const remerged = mergeManifest(order, MANIFEST)

  expect(remerged.stages.handoff.state).toBe('succeeded')
  expect(remerged.stages.update.state).toBe('running')
  expect(countDone(remerged.stageOrder, remerged.stages).done).toBe(1)
})

test('a manifest with a new stage adds it without disturbing the known ones', () => {
  const first = mergeManifest({ stageOrder: [], stages: {} }, MANIFEST)

  const withState: StageOrder = {
    ...first,
    stages: {
      ...first.stages,
      handoff: { info: first.stages.handoff.info, state: 'succeeded' }
    }
  }

  const second = mergeManifest(withState, [
    ...MANIFEST,
    {
      name: 'install',
      title: 'Installing the update',
      category: 'update',
      needs_user_input: false
    }
  ])

  expect(second.stageOrder).toEqual(['handoff', 'update', 'rebuild', 'install'])
  expect(second.stages.handoff.state).toBe('succeeded')
  expect(second.stages.install.state).toBeNull()
})

test('every terminal stage counts as done', () => {
  for (const state of ['succeeded', 'skipped', 'failed'] as const) {
    expect(isTerminal(state)).toBe(true)
  }

  expect(isTerminal('running')).toBe(false)
  expect(isTerminal(null)).toBe(false)
  expect(isTerminal(undefined)).toBe(false)
})

test('a failed stage still counts as a finished step', () => {
  const order = mergeManifest({ stageOrder: [], stages: {} }, MANIFEST)

  const failed: StageOrder = {
    ...order,
    stages: {
      ...order.stages,
      update: { info: order.stages.update.info, state: 'failed' }
    }
  }

  expect(countDone(failed.stageOrder, failed.stages).done).toBe(1)
})

test('the frontend resets the store only when no update is running', () => {
  expect(shouldResetBeforeStart('idle')).toBe(true)
  expect(shouldResetBeforeStart('failed')).toBe(true)
  // During an update the store holds live progress that must survive.
  expect(shouldResetBeforeStart('running')).toBe(false)
})
