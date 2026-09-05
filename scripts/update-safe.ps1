<#
.SYNOPSIS
  Sicheres OpenAmer Update-Skript
.DESCRIPTION
  Stoppt sauber: OpenAmer.exe, Chrome-Prozesse (mit chrome-profile), session_to_brain --watch.
  Entfernt stale Marker, fuehrt openamer update aus, repariert venv falls noetig,
  verifiziert die Installation und startet OpenAmer neu.
.PARAMETER DryRun
  Wenn gesetzt, wird das echte Update uebersprungen (Trockenlauf).
#>

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
$VenvOpenAmer = Join-Path $RepoRoot "venv\Scripts\openamer.exe"
$OpenAmerHome = "$env:LOCALAPPDATA\openamer-laptop"
$MarkerFile = Join-Path $RepoRoot ".update-incomplete"

Write-Host "=== update-safe.ps1 ===" -ForegroundColor Cyan
Write-Host "Repo:  $RepoRoot"
Write-Host "DryRun:" ($DryRun -eq $true)
Write-Host ""

# -- Schritt 1: Prozesse stoppen ------------------------------------------------
Write-Host "[1/7] Stoppe OpenAmer-eigene Prozesse..." -ForegroundColor Yellow

$stopped = @()
# Bei DryRun nur anzeigen, was gestoppt WÜRDE — nie wirklich beenden.
function Stop-OAProcess {
    param([int]$TargetPid, [string]$Label)
    if ($DryRun) {
        Write-Host "  [DRYRUN] wuerde stoppen: $Label (PID $TargetPid)"
        $script:stopped += $Label
        return
    }
    Write-Host "  -> Stoppe $Label (PID $TargetPid)"
    Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue
    $script:stopped += $Label
}

# --- OpenAmer.exe (Desktop-App) ---
$openamerProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='OpenAmer.exe'" -ErrorAction SilentlyContinue
foreach ($p in $openamerProcs) {
    Stop-OAProcess -TargetPid $p.ProcessId -Label "OpenAmer.exe"
}

# --- Chrome mit openamer-laptop\chrome-profile ---
$chromeProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue
foreach ($p in $chromeProcs) {
    $cmd = $p.CommandLine
    if ($cmd -match [regex]::Escape("openamer-laptop") -and $cmd -match "chrome-profile") {
        Stop-OAProcess -TargetPid $p.ProcessId -Label "Chrome (chrome-profile)"
    }
}

# --- session_to_brain.py --watch ---
$brainProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
foreach ($p in $brainProcs) {
    $cmd = $p.CommandLine
    if ($cmd -match "session_to_brain" -and $cmd -match "--watch") {
        Stop-OAProcess -TargetPid $p.ProcessId -Label "session_to_brain"
    }
}

# --- Generische venv-Blocker aus openamer-agent (fängt brain collect, REPLs, alles das
#     die venv-Scripts offen hält: openamer.exe, python.exe unter venv\).(venv-Blocker).
$venvProcs = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match [regex]::Escape("openamer-agent\venv") -and $_.Name -in @("python.exe","openamer.exe") }
foreach ($p in $venvProcs) {
    Stop-OAProcess -TargetPid $p.ProcessId -Label "venv($($p.Name))"
}

# --- Hängengebliebener Updater (openamer-setup.exe) ---
$setupProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='openamer-setup.exe'" -ErrorAction SilentlyContinue
foreach ($p in $setupProcs) {
    Stop-OAProcess -TargetPid $p.ProcessId -Label "openamer-setup"
}

# --- ALLE OpenAmer-Hintergrund-Daemons (dashboard-server, remote-web, system-snapshot,
#     webhook-engine, stealth-server, tool_server, mesh-daemon, ...) die zusätzlich
#     venv\Lib offen halten können. Generisch: jeder Prozess mit 'openamer-laptop' oder
#     'openamer-repo' im Pfad. SCHÜTZT strikt hermes/emilija.
$daemonProcs = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        ($_.CommandLine -match [regex]::Escape("openamer-laptop") -or $_.CommandLine -match [regex]::Escape("openamer-repo")) `
        -and $_.CommandLine -notmatch $hermesPattern `
        -and $_.Name -notin @("bash.exe","powershell.exe","cmd.exe","grep.exe")
    }
foreach ($p in $daemonProcs) {
    # Nicht den eigenen PowerShell-Prozess / Terminal-Shell stoppen
    if ($p.ProcessId -eq $PID) { continue }
    Stop-OAProcess -TargetPid $p.ProcessId -Label "daemon($($p.Name))"
}

if ($stopped.Count -eq 0) {
    Write-Host "  [OK] Keine OpenAmer-Prozesse aktiv." -ForegroundColor Green
} else {
    $joined = $stopped -join ", "
    Write-Host "  [OK] Gestoppt: $joined" -ForegroundColor Green
}
Write-Host ""

# -- Schritt 2: Stale Marker entfernen -------------------------------------------
Write-Host "[2/7] Entferne stale Marker..." -ForegroundColor Yellow
if (Test-Path $MarkerFile) {
    Remove-Item $MarkerFile -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] .update-incomplete entfernt" -ForegroundColor Green
} else {
    Write-Host "  [OK] Kein stale Marker gefunden" -ForegroundColor Green
}
Write-Host ""

# -- Schritt 3: Paketquellen aktualisieren -----------------------------------------
if (-not $DryRun) {
    Write-Host "[3/7] Fuehre openamer update aus..." -ForegroundColor Yellow
    try {
        & $VenvOpenAmer update
        if ($LASTEXITCODE -ne 0) { throw "openamer update exit code $LASTEXITCODE" }
        Write-Host "  [OK] Update erfolgreich" -ForegroundColor Green
    } catch {
        Write-Host "  [FEHLER] beim Update: $_" -ForegroundColor Red
        Write-Host "UPDATE FAILED" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[3/7] [TROCKENLAUF] openamer update uebersprungen" -ForegroundColor DarkYellow
}
Write-Host ""

# -- Schritt 4: Venv-Pruefung und -Reparatur ---------------------------------------
Write-Host "[4/7] Pruefe venv..." -ForegroundColor Yellow
if (-not (Test-Path $VenvPython)) {
    Write-Host "  [WARN] python.exe fehlt! Baue venv neu..." -ForegroundColor Yellow
    try {
        uv venv --clear --python 3.11 (Join-Path $RepoRoot "venv")
        Write-Host "  [OK] venv neu angelegt" -ForegroundColor Green
        Write-Host "  -> Installiere Dependencies..."
        uv pip install --python (Join-Path $RepoRoot "venv\Scripts\python.exe") -e "${RepoRoot}[all]"
        if ($LASTEXITCODE -ne 0) { throw "uv pip install fehlgeschlagen" }
        Write-Host "  [OK] Dependencies installiert" -ForegroundColor Green
    } catch {
        Write-Host "  [FEHLER] Venv-Reparatur fehlgeschlagen: $_" -ForegroundColor Red
        Write-Host "UPDATE FAILED" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [OK] venv intakt (python.exe vorhanden)" -ForegroundColor Green
}
Write-Host ""

# -- Schritt 5: Version verifizieren -----------------------------------------------
Write-Host "[5/7] Verifiziere openamer --version..." -ForegroundColor Yellow
try {
    $versionOutput = & $VenvOpenAmer --version
    if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
    Write-Host "  [OK] $versionOutput" -ForegroundColor Green
    Write-Host ""

    # -- Schritt 6: UPDATE OK ------------------------------------------------------
    Write-Host "[6/7] Ergebnis:" -ForegroundColor Yellow
    Write-Host "  [OK] UPDATE OK" -ForegroundColor Green
} catch {
    Write-Host "  [FEHLER] Version check fehlgeschlagen: $_" -ForegroundColor Red
    Write-Host "UPDATE FAILED" -ForegroundColor Red
    exit 1
}
Write-Host ""

# -- Schritt 7: OpenAmer neustarten ------------------------------------------------
Write-Host "[7/7] Starte OpenAmer..." -ForegroundColor Yellow
try {
    if (-not $DryRun) {
        Start-Process -FilePath $VenvOpenAmer -ArgumentList "desktop"
        Write-Host "  [OK] OpenAmer Desktop gestartet" -ForegroundColor Green
    } else {
        Write-Host "  [TROCKENLAUF] Start uebersprungen" -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "  [WARN] Neustart fehlgeschlagen: $_" -ForegroundColor Yellow
    Write-Host "  (Starte 'openamer desktop' manuell)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== update-safe.ps1 abgeschlossen ===" -ForegroundColor Cyan