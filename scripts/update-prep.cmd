@echo off
REM ============================================================
REM  OpenAmer - Update-Ein-Klick-Ablauf
REM  1. Beendet ALLE openamer-bezogenen Prozesse (Desktop-App,
REM     Gateway, Watchdogs, Cron, Web-Backend, und den Chat/Agent),
REM     damit `openamer update` die venv sauber ueberschreiben kann.
REM  2. Fuehrt das Update aus (openamer update --yes).
REM  3. Startet die Desktop-App danach automatisch neu.
REM
REM  Windows blockiert REPLACE auf laufende .exe-Dateien; ohne das
REM  Beenden der Prozesse schlaegt das Update mit "venv shim locked".
REM ============================================================
@setlocal

REM Konfiguration
set "AGENT=%LOCALAPPDATA%\openamer-laptop\openamer-agent"
set "VENV_OPENAMER=%AGENT%\venv\Scripts\openamer.exe"
set "DESKTOP_EXE=%AGENT%\apps\desktop\release\win-unpacked\OpenAmer.exe"

echo.
echo ============================================
echo  OpenAmer - Update (beenden - updaten - starten)
echo ============================================
echo.

echo [1/3] Beende alle OpenAmer-Prozesse ...
taskkill /IM OpenAmer.exe /F /T >nul 2>&1
taskkill /IM openamer.exe /F /T >nul 2>&1
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*openamer-agent*venv*' -and $_.ProcessId -ne $PID } | ForEach-Object { taskkill /PID $_.ProcessId /F /T 2>$null }"
echo.

echo [2/3] Fuehre Update aus ...
if exist "%VENV_OPENAMER%" (
    echo     Nun wird geupdatet. Dies dauert einige Minuten.
    "%VENV_OPENAMER%" update --yes
    if errorlevel 1 (
        echo.
        echo     Update meldete einen Fehler. Pruefe die Ausgabe oben.
        echo     Der Vorgang wird trotzdem mit dem Neustart fortgesetzt.
    )
) else (
    echo     Konnte %VENV_OPENAMER% nicht finden.
    echo     Fallback: versuche 'openamer update' aus PATH ...
    openamer update --yes
)
echo.

echo [3/3] Starte Desktop-App neu ...
if exist "%DESKTOP_EXE%" (
    start "" "%DESKTOP_EXE%"
    echo     Desktop-App gestartet: %DESKTOP_EXE%
) else (
    echo     Desktop-App nicht gefunden unter:
    echo     %DESKTOP_EXE%
    echo     Bitte oeffne die OpenAmer-App manuell aus dem Startmenue.
)

echo.
echo Fertig. Die aktualisierte OpenAmer-App sollte jetzt laufen.
echo.
pause