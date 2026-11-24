# Watchdog: Prüfe ob online_learning.py --loop läuft, starte ggf. neu
# Aufruf: powershell -ExecutionPolicy Bypass -File _watchdog_online_learning.ps1
#
# Twin-Erkennung: Der online_learning Daemon startet über venv/python.exe,
# was einen uv-Prozess als Child erzeugt = 2 Prozesse sind 1 gesunder Daemon (TWIN_OK)
#
# Exit-Codes:
#   0 = TWIN_OK (2 Prozesse = 1 gesunder Daemon) oder OK (1 Prozess)
#   1 = Daemon war tot, wurde gestartet
#   2 = Duplikate gefunden, älteste$TWIN_OK beibehalten, Rest gekillt
#   3 = Fehler (Pfad nicht gefunden etc.)

$processes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*online_learning.py*' })

# TWIN_OK: venv launcher + uv worker = 1 healthy daemon
# @(...) wraparound sichert .Count für 0, 1, N Ergebnisse
$TWIN_OK = 2

if ($processes.Count -eq 0) {
    Write-Output "WATCHDOG: Kein online_learning Prozess gefunden. Starte neuen..."
    $venv = "C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe"
    $script = "C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\online_learning.py"

    if (-not (Test-Path $venv)) {
        Write-Output "WATCHDOG: FEHLER - Venv-Python nicht gefunden: $venv"
        exit 3
    }
    if (-not (Test-Path $script)) {
        Write-Output "WATCHDOG: FEHLER - Skript nicht gefunden: $script"
        exit 3
    }

    Start-Process -FilePath $venv -ArgumentList "$script --loop" -WindowStyle Hidden

    Write-Output "WATCHDOG: online_learning gestartet (PID wird asynchron erstellt)."
    exit 1
}
elseif ($processes.Count -gt $TWIN_OK) {
    Write-Output "WATCHDOG: $($processes.Count) online_learning Prozesse (TWIN_OK=$TWIN_OK). Beende Duplikate..."

    # Sortiere nach CreationDate, behalte die ältesten $TWIN_OK Prozesse
    $sorted = $processes | Sort-Object CreationDate
    $keep = $sorted[0..($TWIN_OK - 1)]

    foreach ($p in $sorted[$TWIN_OK..($sorted.Count - 1)]) {
        Write-Output "WATCHDOG: Beende Duplikat PID $($p.ProcessId)..."
        Stop-Process -Id $p.ProcessId -Force
    }

    $keepPids = ($keep | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Output "WATCHDOG: Behalte $($keep.Count) Prozesse: PID(s) $keepPids (älteste Instanzen)."
    exit 2
}
elseif ($processes.Count -eq $TWIN_OK) {
    $pids = ($processes | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Output "WATCHDOG: TWIN_OK - $TWIN_OK online_learning Prozesse (PID(s) $pids). Alles gut."
    exit 0
}
else {
    $pids = ($processes | ForEach-Object { $_.ProcessId }) -join ', '
    Write-Output "WATCHDOG: OK - online_learning läuft mit PID(s) $pids."
    exit 0
}