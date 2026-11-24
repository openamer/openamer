# Watchdog for online_learning.py --loop daemon
# Detects twin-process chains (venv parent → uv child), kills only genuine duplicates
#
# TWO-STRATEGY TWIN DETECTION:
#  1. PRIMARY: ParentProcessId chain (existing, reliable when chain is intact)
#  2. FALLBACK: Group-by-CreationDate-second (new 08.09 — catches cases where
#     ParentProcessId chain is broken by intermediate processes)
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File "path\to\watchdog-online-learning.ps1"
# Exit codes:
#   0 = running (single chain or twins) — outputs RUNNING_CHAIN:pid(count)
#   0 = not running — outputs NOT_RUNNING
#   2 = duplicate chains found and killed — outputs MULTIPLE_CHAINS:N|KEEP_ROOT:PID|KILL:PID1,PID2

$proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'online_learning.*--loop' }

if (-not $proc) {
    Write-Host "NOT_RUNNING"
    exit 0
}

# --- STRATEGY 1: ParentProcessId chain (primary) ---
# Build PID lookup map
$pidMap = @{}
foreach ($p in $proc) { $pidMap[$p.ProcessId] = $p }

# Identify processes that are children of another online_learning process (twin chain)
$childrenPids = @()
foreach ($p in $proc) {
    if ($pidMap.ContainsKey($p.ParentProcessId)) {
        $childrenPids += $p.ProcessId
    }
}

$roots = $proc | Where-Object { $_.ProcessId -notin $childrenPids }
$chains = @($roots).Count

if ($chains -eq 1) {
    Write-Host "RUNNING_CHAIN:$($roots[0].ProcessId)($(@($proc).Count) PIDs)"
    exit 0
}

# --- STRATEGY 2: Group-by-creation-second (fallback) ---
# If ParentProcessId chain found NO chain (each PID is its own root),
# the chain may be broken by intermediate processes. Use same-second grouping.
if ($chains -eq @($proc).Count) {
    $byDate = @{}
    foreach ($p in $proc) {
        $key = $p.CreationDate.ToString("yyyyMMddHHmmss")
        if (-not $byDate.ContainsKey($key)) { $byDate[$key] = @() }
        $byDate[$key] += $p
    }
    # One time-group = twins, treat as single chain → exit 0
    if ($byDate.Keys.Count -eq 1) {
        Write-Host "RUNNING_CHAIN:FALLBACK_TIME($(@($proc).Count) PIDs)"
        exit 0
    }
    # Multiple time-groups = real duplicates → proceed to kill
}

# Multiple independent chains or time-groups — real duplicates beyond the intended twin design.
# Keep the oldest root chain, kill the rest (including their children).
$rootByCreation = $roots | Sort-Object CreationDate
$keepRoot = $rootByCreation[0].ProcessId
$killRoots = $rootByCreation[1..($chains-1)] | Select-Object -ExpandProperty ProcessId

$killAll = @()
$procById = @{}
foreach ($p in $proc) { $procById[$p.ProcessId] = $p }

foreach ($kr in $killRoots) {
    $killAll += $kr
    foreach ($p in $proc) {
        if ($p.ParentProcessId -eq $kr) { $killAll += $p.ProcessId }
    }
}

Write-Host "MULTIPLE_CHAINS:$chains|KEEP_ROOT:$keepRoot|KILL:$(($killAll -join ','))"
exit 2