<#
.SYNOPSIS
  Sicheres OpenAmer Update-Skript
.DESCRIPTION
  Stoppt sauber: OpenAmer.exe, Chrome-Prozesse (mit chrome-profile), session_to_brain --watch.
  Entfernt stale Marker, fuehrt openamer update aus, repariert venv falls noetig,
  verifiziert die Installation und startet OpenAmer neu.
  Greift NIEMALS hermes/emilija-Prozesse an.
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
$hermesPattern = "hermes|emilija"

# --- OpenAmer.exe (Desktop-App) ---
$openamerProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='OpenAmer.exe'" -ErrorAction SilentlyContinue
foreach ($p in $openamerProcs) {
    $cmd = $p.CommandLine
    if ($cmd -match $hermesPattern) { continue }  # NIE hermes/emilija
    $msg = "  -> Stoppe OpenAmer.exe (PID $($p.ProcessId))"
    Write-Host $msg
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped += "OpenAmer.exe"
}

# --- Chrome mit openamer-laptop\chrome-profile ---
$chromeProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue
foreach ($p in $chromeProcs) {
    $cmd = $p.CommandLine
    if ($cmd -match [regex]::Escape("openamer-laptop") -and $cmd -match "chrome-profile") {
        if ($cmd -match $hermesPattern) { continue }
        $msg = "  -> Stoppe Chrome (chrome-profile) PID $($p.ProcessId)"
        Write-Host $msg
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped += "Chrome (chrome-profile)"
    }
}

# --- session_to_brain.py --watch ---
$brainProcs = Get-CimInstance -ClassName Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
foreach ($p in $brainProcs) {
    $cmd = $p.CommandLine
    if ($cmd -match "session_to_brain" -and $cmd -match "--watch") {
        if ($cmd -match $hermesPattern) { continue }
        $msg = "  -> Stoppe session_to_brain --watch PID $($p.ProcessId)"
        Write-Host $msg
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped += "session_to_brain"
    }
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