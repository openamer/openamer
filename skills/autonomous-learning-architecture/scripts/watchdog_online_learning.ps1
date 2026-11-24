# Watchdog for online_learning.py --loop
# Twin-process model: venv (parent) + uv (child) = 1 daemon instance
# Kill only when 3+ processes (2+ pairs) — else it's a single healthy daemon.
#
# This is the CRON-SAFE variant (no heredoc, no $_ mangling, no execute_code):
# write_file → powershell -ExecutionPolicy Bypass -File "<path>"
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "watchdog_online_learning.ps1"
# Returns: NOT_RUNNING | RUNNING:pid1,pid2 | DUPLICATES_KEEPING:pid1,pid2\nKILLED:pid3\n...

# ACHTUNG $procId vs $pid: $pid ist PowerShell-readonly (automatische Variable).
# @() erzwingt Array — sonst gibt $processes.Count 0 bei Single-Result.
$processes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*online_learning*loop*' })

if ($processes.Count -eq 0) {
    Write-Output "NOT_RUNNING"
    exit 1
} elseif ($processes.Count -le 2) {
    $procIds = ($processes | ForEach-Object { $_.ProcessId }) -join ","
    Write-Output "RUNNING:$procIds"
    exit 0
} else {
    # Sort by CreationDate, not ProcessId! Keep oldest pair.
    $sorted = $processes | Sort-Object CreationDate
    $keepProcIds = @($sorted[0].ProcessId)
    if ($sorted.Count -ge 2) { $keepProcIds += $sorted[1].ProcessId }
    $killProcs = $sorted | Where-Object { $_.ProcessId -notin $keepProcIds }
    Write-Output "DUPLICATES_KEEPING:$($keepProcIds -join ',')"
    foreach ($p in $killProcs) {
        $procId = $p.ProcessId
        Write-Output "KILL:$procId"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        if ($?) {
            Write-Output "KILLED:$procId"
        } else {
            Write-Output "KILL_FAILED:$procId"
        }
    }
    exit 2
}