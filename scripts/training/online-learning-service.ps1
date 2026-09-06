param([string]$action = "status")
$ErrorActionPreference = "SilentlyContinue"
$Scripts = "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\scripts"
$Py      = "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\venv\Scripts\python.exe"
$Learn   = Join-Path $Scripts "training\online_learning.py"
$Home    = "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent"

function Get-RunningPid {
  $m = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match 'online_learning' -and $_.CommandLine -match '--loop' -and $_.CommandLine -notmatch 'hermes|emilija'
  }
  if ($m) { return $m.ProcessId } else { return "" }
}

if ($action -eq "status") {
  $pid = Get-RunningPid
  if ($pid -ne "") {
    Write-Output "Online-Learning: LAEUFT (PID $pid)"
  } else {
    Write-Output "Online-Learning: laeuft NICHT"
    $stats = & $Py $Learn "--stats" 2>&1 | Select-Object -First 8
    Write-Output $stats
  }
  Write-Output ""
  Write-Output "Nutze: online-learning-service.ps1 start stop status"
}
elseif ($action -eq "start") {
  $pid = Get-RunningPid
  if ($pid -ne "") { Write-Output "Laeuft bereits (PID $pid)" }
  else {
    Write-Output "Starte Online-Learning-Daemon (loop, CPU)"
    $env:OPENAMER_HOME = $Home
    $env:VIRTUAL_ENV = "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\venv"
    Start-Process -FilePath $Py -ArgumentList @($Learn, "--loop") -WorkingDirectory (Split-Path $Learn) -WindowStyle Hidden -RedirectStandardOutput "$env:USERPROFILE\.online-learning.out.log" -RedirectStandardError "$env:USERPROFILE\.online-learning.err.log"
    Start-Sleep -Seconds 3
    $pid = Get-RunningPid
    if ($pid -ne "") { Write-Output "OK: Online-Learning laeuft (PID $pid)" }
    else { Write-Output "Start evtl fehlgeschlagen, siehe err.log" }
  }
}
elseif ($action -eq "stop") {
  $pids = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'online_learning' -and $_.CommandLine -notmatch 'hermes|emilija' }
  if ($pids) {
    foreach ($p in $pids) { Write-Output ("Stoppe PID {0}" -f $p.ProcessId); Stop-Process -Id $p.ProcessId -Force }
    Write-Output "Online-Learning gestoppt"
  } else { Write-Output "Laeuft nicht" }
}
else {
  Write-Output "Usage: online-learning-service.ps1 start stop status"
}