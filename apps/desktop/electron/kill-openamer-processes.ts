/**
 * kill-openamer-processes.ts
 *
 * On Windows, closing the desktop app (the X button) must also tear down every
 * OTHER OpenAmer process that holds the install tree / venv shim locked — the
 * detached `session_to_brain.py --watch` watcher, the `openamer.exe` launcher
 * shim, and any stray `openamer serve` backend. The `before-quit` handler only
 * knows about the backend child it spawned; these siblings are spawned
 * detached (`proc.unref()`) or by other entry points, so they survive quit and
 * keep `openamer update` from replacing the venv (WinError 32 / access-denied).
 *
 * We enumerate processes whose command line references the OpenAmer INSTALL
 * ROOT (the `openamer-agent` tree that `openamer update` replaces — NOT the
 * whole OPENAMER_HOME, which also contains the CDP Chrome profile and the
 * uv-based helper scripts that don't lock the venv shim) and tree-kill them,
 * excluding the current process and its ancestor chain.
 *
 * The ancestor chain matters: the Electron app is a descendant of the
 * `openamer.exe` launcher shim (openamer.exe -> venv python -> uv python ->
 * OpenAmer.exe). A `taskkill /T` on the shim would reap the app itself
 * mid-`before-quit`. The ancestors exit on their own once the app quits (each
 * parent waits on its child), so we leave them alone and only tree-kill the
 * detached siblings that would otherwise survive.
 *
 * Extracted into its own dependency-free module (no electron import) so the
 * PID-filtering and kill orchestration can be unit-tested with injected deps,
 * matching the backend-child.ts / windows-child-options.ts pattern.
 */

import { execFileSync } from 'node:child_process'

export interface OpenAmerProcessInfo {
  pid: number
  parentPid: number
}

export interface KillOpenAmerProcessesDeps {
  /** Defaults to the real platform check; injectable for tests. */
  isWindows?: boolean
  /** The current process pid (defaults to process.pid); injectable for tests. */
  selfPid?: number
  /** Enumerate processes whose command line references `installRoot`, excluding `selfPid`. */
  listOpenAmerProcesses: (installRoot: string, selfPid: number) => OpenAmerProcessInfo[]
  /** Tree-kill a pid (taskkill /PID <pid> /T /F). */
  killProcessTree: (pid: number) => void
}

/**
 * Enumerate processes whose command line references `installRoot`. Returns pid
 * + parentPid for every match INCLUDING the current process, so the caller can
 * walk the ancestor chain from selfPid (the app's parent shim also references
 * the install root and must be skipped, not killed). Uses PowerShell
 * `Get-CimInstance Win32_Process` (the modern replacement for the deprecated
 * `wmic`); the root is passed via an environment variable to avoid PowerShell
 * quoting/escaping hazards with backslash paths.
 */
export function listOpenAmerProcessesViaPowerShell(installRoot: string, _selfPid: number): OpenAmerProcessInfo[] {
  const script = [
    '$root = $env:OPENAMER_KILL_ROOT',
    'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($root) } | ForEach-Object { "{0}:{1}" -f $_.ProcessId, $_.ParentProcessId }'
  ].join('; ')

  let out = ''

  try {
    out = execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', script], {
      env: {
        ...process.env,
        OPENAMER_KILL_ROOT: installRoot
      },
      encoding: 'utf8',
      windowsHide: true
    })
  } catch {
    // PowerShell unavailable or the query failed — return empty and let the
    // caller's shim-unlock wait be the real gate.
    return []
  }

  const result: OpenAmerProcessInfo[] = []

  for (const line of out.split(/\r?\n/)) {
    const trimmed = line.trim()
    const match = /^(\d+):(\d+)$/.exec(trimmed)

    if (match) {
      result.push({ pid: Number(match[1]), parentPid: Number(match[2]) })
    }
  }

  return result
}

/**
 * Tree-kill a pid via `taskkill /PID <pid> /T /F`. Best-effort: a process that
 * already exited (or is unkillable) is swallowed — the caller's shim-unlock
 * wait is the real gate.
 */
export function killProcessTreeViaTaskkill(pid: number): void {
  if (!Number.isInteger(pid) || pid <= 0) {
    return
  }

  try {
    execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true
    })
  } catch {
    // Already gone, or no permission — best effort.
  }
}

/**
 * Compute the ancestor chain of `pid` (itself excluded) by walking parentPid
 * links through `pidToParent`. Returns the set of ancestor pids.
 */
export function computeAncestorChain(pid: number, processes: OpenAmerProcessInfo[]): Set<number> {
  const pidToParent = new Map<number, number>()

  for (const info of processes) {
    pidToParent.set(info.pid, info.parentPid)
  }

  const ancestors = new Set<number>()
  let cursor = pidToParent.get(pid)

  // Guard against cycles / runaway with a bounded walk.
  let steps = 0

  while (cursor !== undefined && cursor > 0 && steps < 64) {
    if (ancestors.has(cursor)) {
      break
    }

    ancestors.add(cursor)
    cursor = pidToParent.get(cursor)
    steps += 1
  }

  return ancestors
}

/**
 * Kill every OpenAmer process (other than the current one and its ancestors)
 * whose command line references `installRoot`. Returns the list of PIDs that
 * were killed so the caller can log them. No-op off Windows.
 */
export function killOtherOpenAmerProcesses(installRoot: string, deps: KillOpenAmerProcessesDeps): number[] {
  const isWindows = deps.isWindows ?? process.platform === 'win32'

  if (!isWindows) {
    return []
  }

  const selfPid = deps.selfPid ?? process.pid
  const processes = deps.listOpenAmerProcesses(installRoot, selfPid)
  const ancestors = computeAncestorChain(selfPid, processes)

  const killed: number[] = []

  for (const info of processes) {
    // Skip the current process and its ancestor chain — those exit on their own
    // once the app quits, and tree-killing them would reap the app
    // mid-before-quit.
    if (info.pid === selfPid || ancestors.has(info.pid)) {
      continue
    }

    deps.killProcessTree(info.pid)
    killed.push(info.pid)
  }

  return killed
}
