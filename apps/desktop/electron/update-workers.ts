import { execFile } from 'node:child_process'
import path from 'node:path'

/** Read-only inventory: never terminate a task to make an update succeed. */
export function activeUpdateWorkers(installRoot: string, powershell: string): Promise<number[]> {
  const root = path.win32.resolve(installRoot).replace(/'/g, "''")
  const script = `$ErrorActionPreference = 'Stop'; $root = '${root}\\'; @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe','openamer.exe') -and $_.CommandLine -and $_.CommandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and $_.CommandLine -match 'work kanban task [a-zA-Z0-9_]+' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress`

  return new Promise((resolve, reject) => {
    execFile(powershell, ['-NoProfile', '-NonInteractive', '-Command', script], {
      windowsHide: true, timeout: 15000, encoding: 'utf8'
    }, (error, stdout) => {
      if (error) { reject(new Error('Cannot inspect active development workers; update was not started.'));

 return }

      try {
        const value = JSON.parse(stdout.trim() || '[]')
        const pids = Array.isArray(value) ? value : [value]

        if (pids.some(pid => !Number.isInteger(pid) || pid <= 0)) { throw new Error('Invalid worker inventory') }
        resolve(pids)
      } catch { reject(new Error('Invalid development worker inventory; update was not started.')) }
    })
  })
}

export async function waitForUpdateWorkers({ inspect, onWait, timeoutMs = 10 * 60 * 1000, pollMs = 1000 }: {
  inspect: () => Promise<number[]>
  onWait: (pids: number[]) => void
  timeoutMs?: number
  pollMs?: number
}): Promise<void> {
  const deadline = Date.now() + timeoutMs

  while (true) {
    const pids = await inspect()

    if (!pids.length) { return }
    onWait(pids)

    if (Date.now() >= deadline) {
      throw new Error('Development workers are still running. Update deferred without stopping their work.')
    }

    await new Promise(resolve => setTimeout(resolve, pollMs))
  }
}
