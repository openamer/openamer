# OpenAmer auto-update watcher:
# waits for OpenAmer.exe to exit (user closes it), then runs `openamer update`
# and relaunches the desktop app. Run detached; logs to update-watcher.log.
$ErrorActionPreference = "Continue"
$log = "C:\Users\damir\openamer-repo\update-watcher.log"
$exe = "$env:OPENAMER_HOME\openamer-agent\venv\Scripts\openamer.exe"
$app = "$env:OPENAMER_HOME\openamer-agent\apps\desktop\release\win-unpacked\OpenAmer.exe"
$maxWaitSec = 43200  # give up after 12h

function Log($m) { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format s), $m) }

Log "watcher started; waiting for OpenAmer.exe to close (max ${maxWaitSec}s)"
$waited = 0
while ($waited -lt $maxWaitSec) {
    $procs = Get-Process -Name "OpenAmer" -ErrorAction SilentlyContinue
    if (-not $procs) { break }
    Start-Sleep -Seconds 5
    $waited += 5
}
if ($waited -ge $maxWaitSec) { Log "timeout waiting; exiting"; exit 1 }
Log "OpenAmer.exe closed; killing stale helpers if any"
Get-Process -Name "OpenAmer" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

Log "running openamer update"
& $exe update *>> $log
$rc = $LASTEXITCODE
Log "update exit code: $rc"

Log "relaunching desktop app"
Start-Process -FilePath $app
Log "watcher done"
