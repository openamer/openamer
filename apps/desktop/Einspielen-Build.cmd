@echo off
rem ---------------------------------------------------------------------------
rem Swap a side-built Electron package into the live install path.
rem
rem Prerequisites:
rem   1. dist/ is current (npm run build)
rem   2. the package was built sideways, because the live app holds the default
rem      output dir locked:
rem        node scripts/run-electron-builder.mjs --dir -c.directories.output=release-alt
rem
rem Then double-click this file. It kills, swaps, restarts. The previous build
rem is kept as release\win-unpacked.bak-apply for a one-move rollback.
rem
rem Test hooks (used by the sandbox matrix in references/packaged-build-swap.md):
rem   OPENAMER_APPLY_APPDIR   run the whole flow against another tree
rem   OPENAMER_APPLY_NO_KILL  skip the taskkill
rem   OPENAMER_APPLY_NO_START skip the relaunch
rem   OPENAMER_APPLY_NO_PAUSE skip the trailing pause
rem ---------------------------------------------------------------------------
setlocal
title OpenAmer - Build einspielen

set "APPDIR=%LOCALAPPDATA%\openamer-laptop\openamer-agent\apps\desktop"
if defined OPENAMER_APPLY_APPDIR set "APPDIR=%OPENAMER_APPLY_APPDIR%"

set "NEW=%APPDIR%\release-alt\win-unpacked"
set "LIVE=%APPDIR%\release\win-unpacked"
set "OLD=%APPDIR%\release\win-unpacked.bak-apply"

echo ============================================================
echo  OpenAmer - Build einspielen
echo ============================================================
echo.

if not exist "%NEW%\OpenAmer.exe" (
  echo [FEHLER] Neuer Build nicht gefunden: %NEW%
  echo          Nichts veraendert.
  echo.
  if not defined OPENAMER_APPLY_NO_PAUSE pause
  exit /b 1
)

if not defined OPENAMER_APPLY_NO_KILL (
  echo 1/4  Beende laufende Instanz...
  taskkill /F /IM OpenAmer.exe >nul 2>&1
  timeout /t 3 /nobreak >nul
  taskkill /F /IM OpenAmer.exe >nul 2>&1
  timeout /t 2 /nobreak >nul
)

echo 2/4  Sichere alten Build...
if exist "%OLD%" rd /s /q "%OLD%"
if exist "%LIVE%" move /y "%LIVE%" "%OLD%" >nul

rem A file still held open turns the move above into a silent no-op. Without
rem this guard the next move would nest the new build INSIDE the live dir
rem (release\win-unpacked\win-unpacked) and still report success.
if exist "%LIVE%" (
  echo [FEHLER] Alte Version liess sich nicht wegschieben - laeuft die App noch?
  echo          Nichts veraendert.
  echo.
  if not defined OPENAMER_APPLY_NO_PAUSE pause
  exit /b 1
)

echo 3/4  Spiele neuen Build ein...
move /y "%NEW%" "%LIVE%" >nul
if not exist "%LIVE%\OpenAmer.exe" (
  echo [FEHLER] Tausch fehlgeschlagen - alte Version wird zurueckgeholt.
  if exist "%OLD%" move /y "%OLD%" "%LIVE%" >nul
  echo.
  if not defined OPENAMER_APPLY_NO_PAUSE pause
  exit /b 1
)

echo 4/4  Starte OpenAmer...
if not defined OPENAMER_APPLY_NO_START start "" "%LIVE%\OpenAmer.exe"

echo.
echo Fertig.
if not defined OPENAMER_APPLY_NO_PAUSE timeout /t 5 >nul
exit /b 0
