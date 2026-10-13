#!/usr/bin/env python3
"""
Persistent Task Queue — JSON-basiert, mit Prioritäten, Daemon, Retry & Stats.

Queue-Datei: .task-queue/queue.json  (relativ zum aktuellen Arbeitsverzeichnis)
Log-Datei:   .task-queue/task-queue.log

CLI:
  --add <json>          Task hinzufügen
  --list                Tasks anzeigen (Filter: --status, --priority)
  --process             Nächsten pending Task ausführen
  --daemon              Alle 10s neue Tasks verarbeiten (max 3 parallel, threading)
  --retry <id>          Failed Task wiederholen
  --cancel <id>         Task abbrechen
  --stats               Statistiken anzeigen

Exit-Codes: 0=ok, 1=pending, 2=failed
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue as ThreadQueue, Empty as QueueEmpty


# ── Konfiguration ──────────────────────────────────────────────────────────

QUEUE_DIR = Path.cwd() / ".task-queue"
QUEUE_FILE = QUEUE_DIR / "queue.json"
LOCK_FILE = QUEUE_DIR / "queue.lock"
LOG_FILE = QUEUE_DIR / "task-queue.log"

DAEMON_INTERVAL = 10       # Sekunden zwischen Polls
MAX_PARALLEL = 3           # Max gleichzeitige Threads im Daemon
TASK_TIMEOUT = 300         # Timeout pro Task in Sekunden

VALID_STATUSES = {"pending", "running", "done", "failed", "cancelled"}


# ── Logging ────────────────────────────────────────────────────────────────

def setup_logging():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("task-queue")


log = setup_logging()


# ── Daemon-Threading-Lock ──────────────────────────────────────────────────

_save_lock = threading.RLock()


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def _load_queue() -> list[dict]:
    """Queue aus Datei laden."""
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Fehler beim Lesen der Queue: {e}")
        return []


def _save_queue(tasks: list[dict]) -> bool:
    """Queue atomär in Datei speichern (thread-safe)."""
    for attempt in range(3):
        try:
            with _save_lock:
                tmp = QUEUE_FILE.with_suffix(f".tmp.{os.getpid()}")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, indent=2, ensure_ascii=False)
                tmp.replace(QUEUE_FILE)
            return True
        except OSError as e:
            if attempt < 2:
                time.sleep(0.1 * (attempt + 1))
                continue
            log.error(f"Fehler beim Schreiben der Queue (Versuch {attempt + 1}): {e}")
            return False
    return False


def _now_iso() -> str:
    """Aktuelle UTC-Zeit als ISO-String."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _update_task_status(task_id: str, status: str, **extra) -> bool:
    """Atomar: Queue laden, einen Task updaten, speichern (thread-safe)."""
    with _save_lock:
        tasks = _load_queue()
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = status
                for k, v in extra.items():
                    t[k] = v
                break
        return _save_queue(tasks)


def _task_duration(task: dict) -> float | None:
    """Dauer eines Tasks in Sekunden, falls vorhanden."""
    if "started_at" in task and "completed_at" in task:
        try:
            s = datetime.fromisoformat(task["started_at"])
            e = datetime.fromisoformat(task["completed_at"])
            return (e - s).total_seconds()
        except (ValueError, TypeError):
            pass
    return None


def _run_task_payload(task: dict) -> bool:
    """Führt die Task-Logik aus. Gibt True bei Erfolg, False bei Fehler.

    Die default-Implementierung erwartet ein `payload.command`-Feld und führt
    es via subprocess aus. Erweiterbare Hook-Struktur.

    Kann in Skills oder Subklassen überschrieben werden.
    """
    payload = task.get("payload", {})
    task_type = task.get("type", "unknown")

    # ── Type-Handler ────────────────────────────────────────────────────
    if task_type == "echo":
        msg = payload.get("message", "Echo-Task ausgeführt")
        log.info(f"[{task['id']}] {msg}")
        time.sleep(0.5)
        return True

    if task_type == "subprocess":
        import subprocess
        cmd = payload.get("command")
        if not cmd:
            log.error(f"[{task['id']}] Kein command im payload")
            return False
        log.info(f"[{task['id']}] Führe aus: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=TASK_TIMEOUT
            )
            if result.returncode == 0:
                log.info(f"[{task['id']}] OK — stdout: {result.stdout.strip()[:200]}")
                return True
            else:
                log.error(f"[{task['id']}] FEHLER ({result.returncode}): {result.stderr.strip()[:200]}")
                return False
        except subprocess.TimeoutExpired:
            log.error(f"[{task['id']}] Timeout nach {TASK_TIMEOUT}s")
            return False
        except Exception as e:
            log.error(f"[{task['id']}] Ausnahme: {e}")
            return False

    if task_type == "python":
        code = payload.get("code", "")
        if not code:
            log.error(f"[{task['id']}] Kein code im payload")
            return False
        log.info(f"[{task['id']}] Führe Python-Code aus")
        try:
            compiled = compile(code, f"<task-{task['id']}>", "exec")
            exec(compiled, {"__builtins__": __builtins__})
            log.info(f"[{task['id']}] Python-Code OK")
            return True
        except Exception as e:
            log.error(f"[{task['id']}] Python-Fehler: {e}")
            return False

    log.warning(f"[{task['id']}] Unbekannter Task-Typ: {task_type}, behandle als echo")
    log.info(f"[{task['id']}] Payload: {json.dumps(payload)}")
    time.sleep(0.5)
    return True


# ── CLI-Befehle ────────────────────────────────────────────────────────────

def cmd_add(args):
    """Task hinzufügen: --add '{"type":"backup","payload":{}}'"""
    try:
        data = json.loads(args.add) if isinstance(args.add, str) else args.add
    except json.JSONDecodeError as e:
        log.error(f"Ungültiges JSON: {e}")
        sys.exit(1)

    task_type = data.get("type", "echo")
    payload = data.get("payload", {})
    priority = data.get("priority", 3)
    scheduled_at = data.get("scheduled_at")

    if not isinstance(priority, int) or priority < 1 or priority > 5:
        log.error("priority muss zwischen 1 und 5 liegen")
        sys.exit(1)

    task = {
        "id": str(uuid.uuid4())[:8],
        "type": task_type,
        "payload": payload,
        "status": "pending",
        "priority": priority,
        "created_at": _now_iso(),
        "scheduled_at": scheduled_at,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    tasks = _load_queue()
    tasks.append(task)
    if _save_queue(tasks):
        log.info(f"Task hinzugefügt: {task['id']} (type={task_type}, priority={priority})")
        print(json.dumps(task, indent=2))
    else:
        log.error("Konnte Task nicht speichern")
        sys.exit(1)


def cmd_list(args):
    """Tasks auflisten: --list [--status pending] [--priority 1]"""
    tasks = _load_queue()
    if not tasks:
        print("Keine Tasks in der Queue.")
        return

    # Filter
    if args.status:
        status_filter = args.status.split(",") if "," in args.status else [args.status]
        tasks = [t for t in tasks if t.get("status") in status_filter]
    if args.priority is not None:
        tasks = [t for t in tasks if t.get("priority") == args.priority]
    if args.type_filter:
        tasks = [t for t in tasks if t.get("type") == args.type_filter]

    if not tasks:
        print("Keine Tasks gefunden (Filter zu streng?).")
        return

    # Sortierung: pending nach priority (höchste zuerst), dann created_at
    tasks.sort(key=lambda t: (
        0 if t.get("status") == "pending" else 1,
        -t.get("priority", 3),
        t.get("created_at", ""),
    ))

    print(f"{'ID':<10} {'TYPE':<14} {'STATUS':<10} {'PRIO':<5} {'CREATED':<22} {'SCHEDULED':<22} {'ERROR':<30}")
    print("-" * 113)
    for t in tasks:
        err = (t.get("error") or "")[:30]
        sched = t.get("scheduled_at") or "-"
        print(f"{t['id']:<10} {t['type']:<14} {t.get('status',''):<10} {t.get('priority',3):<5} "
              f"{t.get('created_at',''):<22} {sched:<22} {err:<30}")


def cmd_process(args):
    """Nächsten pending Task ausführen (nach Priority & scheduled_at)."""
    tasks = _load_queue()

    # Priorisiere pending Tasks: höchste Priority zuerst, dann scheduled_at (None = sofort)
    pending = [
        t for t in tasks
        if t.get("status") == "pending"
    ]

    if not pending:
        log.info("Keine pending Tasks.")
        return 0

    def sort_key(t):
        prio = -t.get("priority", 3)  # höhere Zahl = höhere Priorität
        sched = t.get("scheduled_at")
        if sched is None:
            sched_key = "0000"
        else:
            sched_key = sched
        return (prio, sched_key)

    pending.sort(key=sort_key)
    task = pending[0]

    # Check scheduled_at
    now = _now_iso()
    sched = task.get("scheduled_at")
    if sched and sched > now:
        log.info(f"Task {task['id']} ist erst für {sched} geplant, überspringe.")
        return 0

    # Task aktualisieren → running
    for t in tasks:
        if t["id"] == task["id"]:
            t["status"] = "running"
            t["started_at"] = _now_iso()
            t["error"] = None
            break
    _save_queue(tasks)

    log.info(f"Starte Task: {task['id']} (type={task['type']}, priority={task.get('priority',3)})")
    try:
        success = _run_task_payload(task)
    except Exception as e:
        log.error(f"Task {task['id']} ausnahme: {e}")
        success = False

    # Ergebnis speichern
    tasks = _load_queue()
    for t in tasks:
        if t["id"] == task["id"]:
            t["status"] = "done" if success else "failed"
            t["completed_at"] = _now_iso()
            if not success:
                t["error"] = f"Task failed (see log)"
            break
    _save_queue(tasks)

    if success:
        log.info(f"Task {task['id']} erfolgreich abgeschlossen.")
    else:
        log.error(f"Task {task['id']} fehlgeschlagen.")

    # Nach dem Prozess Exit-Code checken
    _exit_with_queue_status()


def cmd_daemon(args):
    """Daemon-Modus: --daemon"""
    log.info("=" * 60)
    log.info("Task-Queue Daemon gestartet")
    log.info(f"  Queue: {QUEUE_FILE}")
    log.info(f"  Intervall: {DAEMON_INTERVAL}s, Max parallel: {MAX_PARALLEL}")
    log.info("=" * 60)

    running_tasks: list[dict] = []
    run_lock = threading.Lock()
    stop_event = threading.Event()

    def _worker(task: dict):
        """Führt einen einzelnen Task im Thread aus."""
        tid = task["id"]
        log.info(f"[Daemon] Worker startet Task {tid}")

        # Atomare Status-Updates — kein Race-Condition mehr
        _update_task_status(tid, "running", started_at=_now_iso(), error=None)

        try:
            success = _run_task_payload(task)
        except Exception as e:
            log.error(f"[Daemon] Task {tid} Ausnahme: {e}")
            success = False

        now = _now_iso()
        extra = {"completed_at": now}
        if not success:
            extra["error"] = "Daemon execution failed"
        _update_task_status(tid, "done" if success else "failed", **extra)

        with run_lock:
            running_tasks[:] = [rt for rt in running_tasks if rt["id"] != tid]

        log.info(f"[Daemon] Task {tid} {'erfolgreich' if success else 'fehlgeschlagen'}")

    while not stop_event.is_set():
        tasks = _load_queue()
        now = _now_iso()

        # Pending Tasks nach Priorität
        pending = [
            t for t in tasks
            if t.get("status") == "pending"
            and (t.get("scheduled_at") is None or t["scheduled_at"] <= now)
        ]
        pending.sort(key=lambda t: (-t.get("priority", 3), t.get("created_at", "")))

        # Starte neue Tasks bis MAX_PARALLEL
        with run_lock:
            active_count = len(running_tasks)
            free_slots = MAX_PARALLEL - active_count

        if pending and free_slots > 0:
            to_start = pending[:free_slots]
            for pt in to_start:
                with run_lock:
                    running_tasks.append(pt)
                t = threading.Thread(target=_worker, args=(pt,), daemon=True)
                t.start()
                log.info(f"[Daemon] Task {pt['id']} gestartet ({len(running_tasks)}/{MAX_PARALLEL} Threads)")

        # Warte auf Intervall (checke stop_event alle 1s)
        for _ in range(DAEMON_INTERVAL):
            if stop_event.is_set():
                break
            time.sleep(1)

    log.info("Daemon gestoppt.")


def cmd_retry(args):
    """Failed Task wiederholen: --retry <id>"""
    task_id = args.retry
    tasks = _load_queue()

    found = False
    for t in tasks:
        if t["id"] == task_id:
            if t.get("status") != "failed":
                log.warning(f"Task {task_id} hat Status '{t.get('status')}', nicht 'failed'. Setze trotzdem zurück.")
            t["status"] = "pending"
            t["started_at"] = None
            t["completed_at"] = None
            t["error"] = None
            found = True
            break

    if not found:
        log.error(f"Task {task_id} nicht gefunden.")
        sys.exit(1)

    if _save_queue(tasks):
        log.info(f"Task {task_id} zurückgesetzt auf pending und zur Wiederholung vorgemerkt.")
    else:
        log.error("Konnte Queue nicht speichern.")
        sys.exit(1)


def cmd_cancel(args):
    """Task abbrechen: --cancel <id>"""
    task_id = args.cancel
    tasks = _load_queue()

    found = False
    for t in tasks:
        if t["id"] == task_id:
            if t.get("status") in ("done", "cancelled"):
                log.warning(f"Task {task_id} ist bereits {t.get('status')}.")
                return
            t["status"] = "cancelled"
            t["completed_at"] = _now_iso()
            t["error"] = "Cancelled by user"
            found = True
            break

    if not found:
        log.error(f"Task {task_id} nicht gefunden.")
        sys.exit(1)

    if _save_queue(tasks):
        log.info(f"Task {task_id} abgebrochen (cancelled).")
    else:
        log.error("Konnte Queue nicht speichern.")
        sys.exit(1)


def cmd_stats(args):
    """Statistiken anzeigen: --stats"""
    tasks = _load_queue()
    if not tasks:
        print("Keine Tasks in der Queue. Keine Statistiken verfügbar.")
        return

    total = len(tasks)
    status_counts = {}
    for t in tasks:
        s = t.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    # Duration
    durations = []
    for t in tasks:
        d = _task_duration(t)
        if d is not None:
            durations.append(d)

    # Tasks pro Stunde (basierend auf completion time)
    completed_times = [
        datetime.fromisoformat(t["completed_at"])
        for t in tasks
        if t.get("completed_at") and t.get("status") in ("done", "failed")
    ]
    tasks_per_hour = 0
    if len(completed_times) >= 2:
        timespan = (max(completed_times) - min(completed_times)).total_seconds()
        if timespan > 0:
            tasks_per_hour = len(completed_times) / (timespan / 3600)

    done = status_counts.get("done", 0)
    failed = status_counts.get("failed", 0)
    processed = done + failed
    failure_rate = (failed / processed * 100) if processed > 0 else 0.0

    avg_duration = sum(durations) / len(durations) if durations else 0.0

    print("=" * 50)
    print("  Task-Queue Statistiken")
    print("=" * 50)
    print(f"  Gesamt Tasks:      {total}")
    print(f"  ├── pending:       {status_counts.get('pending', 0)}")
    print(f"  ├── running:       {status_counts.get('running', 0)}")
    print(f"  ├── done:          {done}")
    print(f"  ├── failed:        {failed}")
    print(f"  └── cancelled:     {status_counts.get('cancelled', 0)}")
    print()
    print(f"  Durchschnitts-Dauer: {avg_duration:.2f}s")
    if durations:
        print(f"  Kürzester Task:     {min(durations):.2f}s")
        print(f"  Längster Task:      {max(durations):.2f}s")
    print(f"  Tasks/Stunde:       {tasks_per_hour:.1f}")
    print(f"  Fehlerrate:         {failure_rate:.1f}%")
    print("=" * 50)


def _exit_with_queue_status():
    """Setzt Exit-Code basierend auf Queue-Status."""
    tasks = _load_queue()
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    if failed > 0:
        sys.exit(2)
    if pending > 0:
        sys.exit(1)
    sys.exit(0)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Task Queue — Persistent JSON-Queue mit Prioritäten & Daemon"
    )
    parser.add_argument("--add", type=str, default=None,
                        help="Task hinzufügen (JSON-String)")
    parser.add_argument("--list", action="store_true",
                        help="Tasks auflisten")
    parser.add_argument("--status", type=str, default=None,
                        help="Filter für --list: pending,done,failed,...")
    parser.add_argument("--priority", type=int, default=None,
                        help="Filter für --list (1-5)")
    parser.add_argument("--type", dest="type_filter", type=str, default=None,
                        help="Filter für --list nach Task-Typ")
    parser.add_argument("--process", action="store_true",
                        help="Nächsten pending Task ausführen")
    parser.add_argument("--daemon", action="store_true",
                        help="Daemon-Modus (alle 10s, max 3 parallel)")
    parser.add_argument("--retry", type=str, default=None,
                        help="Failed Task wiederholen (ID)")
    parser.add_argument("--cancel", type=str, default=None,
                        help="Task abbrechen (ID)")
    parser.add_argument("--stats", action="store_true",
                        help="Statistiken anzeigen")
    parser.add_argument("--exit-code", action="store_true",
                        help="Exit-Code setzen: 0=ok, 1=pending, 2=failed")

    args = parser.parse_args()

    # Queue-Verzeichnis erstellen
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # Locking für nicht-daemon Befehle
    if not args.daemon:
        # Kurze Lock-Phase für atomare Operationen
        pass

    if args.add:
        cmd_add(args)
    elif args.list:
        cmd_list(args)
    elif args.process:
        cmd_process(args)
    elif args.daemon:
        cmd_daemon(args)
    elif args.retry:
        cmd_retry(args)
    elif args.cancel:
        cmd_cancel(args)
    elif args.stats:
        cmd_stats(args)
    elif args.exit_code:
        _exit_with_queue_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()