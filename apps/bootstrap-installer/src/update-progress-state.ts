/**
 * Update-progress state rules for the bootstrap installer.
 *
 * Measured incident (2026-11-02, Windows): the update dialog read
 * "0 of 3 steps complete" for the WHOLE run, even though the Rust side had
 * already emitted `handoff=Succeeded`.
 *
 * Two independent causes, both real:
 *
 * 1. Rust auto-starts the update from `.setup()` (so the update runs even when
 *    the WebView never initialises), and the WebView frontend ALSO calls
 *    `start_update` on mount. The frontend's `startUpdate()` reset the whole
 *    store to `INITIAL`, wiping the stage states that had already arrived.
 * 2. The duplicate `start_update` invoke makes Rust re-emit the manifest
 *    (its documented recovery for a duplicate call). The manifest handler
 *    rebuilt the stage map with `state: null` for every stage, wiping the
 *    progress a second time.
 *
 * Both halves of the fix live here as pure functions, so they can be tested
 * without a browser, a Tauri runtime, or a live update.
 */

export type StageState = 'running' | 'succeeded' | 'skipped' | 'failed'

export interface StageInfo {
  name: string
  title: string
  category: string
  needs_user_input: boolean
}

export interface StageRecord {
  info: StageInfo
  state: StageState | null
  durationMs?: number
  startedAt?: number
  error?: string
}

export interface StageOrder {
  stageOrder: string[]
  stages: Record<string, StageRecord>
}

/** Terminal states — a stage in one of these has finished its work. */
const TERMINAL_STATES: readonly StageState[] = ['succeeded', 'skipped', 'failed']

export function isTerminal(state: StageState | null | undefined): boolean {
  return state !== null && state !== undefined && TERMINAL_STATES.includes(state)
}

/**
 * Count the finished stages.
 *
 * This is what the UI renders as "N of M steps complete". A stage that has
 * not reported yet (`null`) is NOT done — it is simply unknown.
 */
export function countDone(
  stageOrder: readonly string[],
  stages: Record<string, StageRecord>
): { done: number; total: number; fraction: number } {
  const total = stageOrder.length

  if (total === 0) {
    return { done: 0, total: 0, fraction: 0 }
  }

  let done = 0

  for (const name of stageOrder) {
    if (isTerminal(stages[name]?.state)) {
      done += 1
    }
  }

  return { done, total, fraction: done / total }
}

/**
 * Build the stage map for a (re-)emitted manifest.
 *
 * A manifest can arrive more than once: Rust re-emits it when a duplicate
 * `start_update` call finds an update already running. Blindly rebuilding the
 * map with `state: null` throws away the progress that was already reported
 * — which is exactly what made the dialog read "0 of 3 steps complete" for the
 * entire run.
 *
 * So: a stage we already know keeps its state; only a genuinely new stage
 * starts out unknown.
 */
export function mergeManifest(
  previous: StageOrder,
  manifestStages: readonly StageInfo[]
): StageOrder {
  const stages: Record<string, StageRecord> = {}
  const stageOrder: string[] = []

  for (const info of manifestStages) {
    const known = previous.stages[info.name]

    stages[info.name] = { info, state: known ? known.state : null }
    stageOrder.push(info.name)
  }

  return { stageOrder, stages }
}

/**
 * Should the frontend reset the store before invoking `start_update`?
 *
 * Only when no update is running yet. During an update the store holds live
 * progress that must survive the call.
 */
export function shouldResetBeforeStart(status: string): boolean {
  return status !== 'running'
}
