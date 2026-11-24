# Orphaned process fleets: classify by ancestor ROOT, not by name

Measured 2026-10-31 on this box. A "why is there no free RAM" question ended with
**119 `gateway` processes**, of which **118 were garbage** holding **3.6 GB**. Free
RAM went 7.5 → 9.5 GB after the cleanup, which is what let the nightly training
start at all.

Windows has no orphan reaping: when the parent dies, the child keeps running and is
re-parented to nothing the process table can name. A test suite that spawns real
services therefore *accumulates* them, one per run, forever.

## The shape

`Get-CimInstance` grouped by start time showed the pattern immediately — every
gateway had a `python.exe` parent of a few MB (the venv trampoline), whose own
parent was a **pytest** process from the run 20 seconds earlier:

```
pid   ppid   mb  start     exe
 8404   4328  28  19:01:37  python.exe     <- gateway
 4328  12032   1  19:01:37  python.exe     <- venv trampoline
12032          -  ...       pytest         <- the run, long gone
```

Counting by name says "119 gateways". Counting by **root of the ancestor chain**
says "1 belongs to the desktop app, 118 are debris".

## Recipe — walk the chain, classify the root

```powershell
$procs = Get-CimInstance Win32_Process
$byId = @{}
foreach ($p in $procs) { $byId[[int]$p.ProcessId] = $p }
$rows = @()
foreach ($p in $procs) {
  if ("$($p.CommandLine)" -notlike '*openamer_cli.main*gateway*') { continue }
  $chain = @(); $cur = [int]$p.ParentProcessId; $isTest = $false; $root = ''
  for ($i = 0; $i -lt 8; $i++) {
    $a = $byId[$cur]
    if (-not $a) { $root = '(weg)'; break }              # chain ends at a dead pid
    $chain += $a.Name
    if ("$($a.CommandLine)" -like '*pytest*') { $isTest = $true }
    if ($a.Name -eq 'explorer.exe' -or $a.Name -eq 'services.exe' -or $a.Name -like 'OpenAmer*') {
      $root = $a.Name; break                             # a legitimate owner
    }
    $cur = [int]$a.ParentProcessId
  }
  if (-not $root) { $root = if ($chain.Count) { $chain[-1] } else { '(weg)' } }
  $rows += [pscustomobject]@{ pid=[int]$p.ProcessId; test=$isTest; root=$root }
}
$rows | Group-Object root | Select-Object Name, Count
```

Result on this host: `(weg) 94`, `python.exe 24`, `OpenAmer.exe 1`.

- `(weg)` = the chain runs into a pid that no longer exists. Nothing legitimate can
  own these; they are orphans.
- `pytest` anywhere in the chain = spawned by a test run that has finished.
- `OpenAmer.exe` / `explorer.exe` / `services.exe` = **keep**. This is the one the
  desktop app is actually using.

## Kill only what cannot be owned

```powershell
# keep = chain reaches OpenAmer*/explorer/services; everything else goes
foreach ($k in $kill) { Stop-Process -Id $k -Force -ErrorAction SilentlyContinue }
```

Two passes are enough; do **not** kill by name alone (`*gateway*` also matches the
one that serves the app) and do not use `-match` on a path fragment in a
one-liner that kills — the query process matches its own command line and kills
itself (see the SELF_MARKERS traps in the parent skill).

## Verify as one claim, not two

| check | before | after |
|---|---|---|
| free RAM | 7.5 GB | 9.5 GB |
| gateway processes | 119 | 3 (cron legitimately respawned two) |
| `:8081 /health` | `{"status":"alive","tools":10}` | unchanged |
| `:8901 /health` | `OK` | unchanged |
| Chrome processes (user's) | 41 | 41 — untouched |

Report the reclaimed bytes **and** the untouched user processes together; a kill on
the box where the agent lives is only safe if you prove the collateral is zero.

## Prevention, not just cleanup

- The test-side cause is the **live guard** not catching `python -m openamer_cli.main
  gateway …` (it anchors on binary names and script paths, not on `-m <module>`).
  Until that matcher covers the module form, every full-suite run leaks a handful of
  real gateways.
- A service that is started by tests should also carry its own reaper: exit when the
  parent pid disappears (`psutil.pid_exists(ppid)` in a watchdog thread). Windows will
  never do it for you.
- Before concluding "the machine is out of RAM", count processes **per install root**
  and look for a fleet of identical command lines — a fleet is debris, not load.
