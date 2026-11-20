/**
 * In-app update mutual-exclusion marker (#50238).
 *
 * The Tauri updater writes OPENAMER_HOME/.openamer-update-in-progress for the whole
 * duration of an `--update` run (see apps/bootstrap-installer/src-tauri/src/
 * update.rs `UpdateMarkerGuard`). The marker body is two lines: the updater's
 * pid and the unix-seconds it started.
 *
 * Why: if the user relaunches the desktop mid-update — the window vanished with
 * no progress and looks crashed — a fresh instance must NOT spawn its own local
 * backend. That backend re-locks the venv shim, the updater's straggler cleanup
 * (`force_kill_other_openamer`, taskkill /IM openamer.exe) kills it, the launch
 * fails with the 45s "backend didn't come up" timeout, and the user relaunches
 * into the same trap — an infinite respawn/kill loop. The desktop gates local
 * backend startup on this marker and parks until the update finishes.
 *
 * This module holds the PURE, side-effect-light logic (path, pid liveness,
 * parse + staleness) so it is unit-testable without booting Electron. The
 * polling/boot-progress wrapper lives in main.ts where the boot-progress and
 * log sinks are.
 */

import fs from 'fs'
import path from 'path'

// Even with a live-looking PID, never treat a marker older than this as a live
// update. A full update (git pull + pip + desktop rebuild) is minutes, not tens
// of minutes; past this the marker is almost certainly stale (e.g. the OS
// recycled the pid onto an unrelated process), so the gate self-heals.
export const UPDATE_MARKER_MAX_AGE_MS = 20 * 60 * 1000

export function markerPath(openamerHome) {
  return path.join(openamerHome, '.openamer-update-in-progress')
}

// True only if a host process with this pid is currently alive. Signal 0 does
// not deliver a signal — it just probes existence/permission. ESRCH => dead;
// EPERM => alive but owned by another user (still "alive" for our purposes).
// Injectable `kill` keeps it unit-testable.
export function isPidAlive(pid, kill: typeof process.kill = process.kill.bind(process)) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return false
  }

  try {
    kill(pid, 0)

    return true
  } catch (err) {
    return Boolean(err && err.code === 'EPERM')
  }
}

/**
 * Read + interpret the marker.
 *
 * Returns `{ pid, ageMs }` only when an update is GENUINELY still running
 * (parseable pid that is alive, within the age ceiling). Returns `null` for
 * every "no live update" case — absent, unreadable, malformed, dead pid, or
 * past the ceiling — and, when a stale marker file exists, deletes it so it
 * cannot strand future launches.
 *
 * Pure-ish: file I/O against the given path, plus an injectable pid probe and
 * clock for tests.
 */
export function readLiveUpdateMarker(
  openamerHome,
  {
    kill,
    now = Date.now,
    maxAgeMs = UPDATE_MARKER_MAX_AGE_MS
  }: {
    now?: () => number
    maxAgeMs?: number
    kill?: typeof process.kill
  } = {}
) {
  const file = markerPath(openamerHome)
  let raw

  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return null // absent or unreadable => no live update
  }

  const [pidLine, startedLine] = String(raw).split('\n')
  const pid = Number.parseInt((pidLine || '').trim(), 10)
  const startedAt = Number.parseInt((startedLine || '').trim(), 10)
  const ageMs = Number.isFinite(startedAt) ? now() - startedAt * 1000 : Infinity
  const alive = Number.isInteger(pid) && isPidAlive(pid, kill)

  if (!alive || ageMs > maxAgeMs) {
    try {
      fs.unlinkSync(file)
    } catch {
      void 0
    }

    return null
  }

  return { pid, ageMs }
}

/**
 * Write the update-in-progress marker *from the desktop* before handing off
 * to the detached updater.
 *
 * The Tauri-based openamer-setup.exe takes several seconds to initialise its
 * window and reach the Rust `run_update` entry point where it writes the
 * marker itself. During that gap the desktop's `app.quit()` teardown kills
 * the backend child, the renderer's WebSocket drops, and the renderer
 * immediately calls `ensureBackend()` → `waitForUpdateToFinish()`. Because
 * the updater hasn't written the marker yet, the gate sees no live update
 * and spawns a *new* backend — which re-locks `.pyd` files in the venv.
 * When the updater finally reaches the venv-rebuild stage it finds those
 * files locked and the update bricks.
 *
 * Fix: the desktop writes the marker itself, using the spawned updater's
 * PID, immediately after `spawn()`. The updater's `UpdateMarkerGuard` will
 * later overwrite it with its own PID — that's fine, the marker body is
 * the same format and `readLiveUpdateMarker` only cares that *some* live
 * pid owns it. When the updater finishes it deletes the marker as before.
 * If the updater never starts (spawn failure) the marker still contains a
 * real PID, so `readLiveUpdateMarker` will self-heal once that PID exits.
 */
export function writeUpdateMarker(openamerHome, pid, { now = Date.now } = {}) {
  const file = markerPath(openamerHome)
  const startedAt = Math.floor(now() / 1000)

  try {
    fs.writeFileSync(file, `${pid}\n${startedAt}\n`, 'utf8')
  } catch {
    // Best-effort: if we can't write the marker, proceed anyway. The
    // updater will write its own when it reaches run_update.
  }
}

/** Reserve the existing marker before waiting for autonomous workers. */
export function claimUpdateWorkerDrain(home: string, pid: number): void {
  if (readLiveUpdateMarker(home)) {
    throw new Error('Another update is already in progress.')
  }
  fs.writeFileSync(markerPath(home), `${pid}\n${Math.floor(Date.now() / 1000)}\n`, { encoding: 'utf8', flag: 'wx' })
}

/** Never remove the updater's successor marker or another owner's reservation. */
export function releaseUpdateWorkerDrain(home: string, pid: number): void {
  try {
    const file = markerPath(home)

    if (Number(fs.readFileSync(file, 'utf8').split('\n')[0]) === pid) {
      fs.unlinkSync(file)
    }
  } catch {
    /* Missing is already released; an unreadable marker remains fail-safe. */
  }
}

/** Wait for both in-process teardown and the detached updater to release startup.
 * A missing on-disk marker is not permission to respawn during local teardown.
 * Never fall through on timeout: that would re-lock the environment mid-update.
 */
export async function waitForUpdateRelease({
  isBlocked,
  onWait,
  pollMs = 1000,
  timeoutMs = UPDATE_MARKER_MAX_AGE_MS
}: {
  isBlocked: () => boolean
  onWait?: () => void | Promise<void>
  pollMs?: number
  timeoutMs?: number
}): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  let waited = false

  while (isBlocked()) {
    if (Date.now() >= deadline) {
      throw new Error('OpenAmer update is still in progress; backend startup remains paused.')
    }

    waited = true
    await onWait?.()
    await new Promise(resolve => setTimeout(resolve, pollMs))
  }

  return waited
}
