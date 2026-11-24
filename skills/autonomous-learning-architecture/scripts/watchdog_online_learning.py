#!/usr/bin/env python
"""Watchdog: Prüft ob online_learning.py --loop läuft, startet ggf. oder killt Duplikate.

Der Daemon besteht aus 2 Prozessen (venv-Parent + uv-Child) = 1 Instanz.
Dieses Script gruppiert nach PPID-Kette, nicht roher PID-Zahl.

Verwendung:
  python watchdog_online_learning.py

Exit-Codes:
  0 — Daemon läuft sauber (stillschweigend) ODER erfolgreich gestartet/bereinigt
  1 — Fehler (Start fehlgeschlagen)

3 Fälle:
  - 0 Instanzen → Starte neuen Daemon
  - 1 Instanz → Nichts tun (stillschweigend)
  - 2+ Instanzen → Älteste behalten, restliche killen
"""
import psutil, subprocess, time

VENV_PYTHON = r"C:/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/python.exe"
SCRIPT = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/online_learning.py"


def find_learning_procs():
    """Finde alle Prozesse mit online_learning.py --loop in der CommandLine."""
    procs = []
    for proc in psutil.process_iter(["pid", "ppid", "create_time", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue
            cmd_str = " ".join(cmdline).lower()
            if any(py in cmdline[0].lower() for py in ("python", "python3")):
                if "online_learning.py" in cmd_str and "--loop" in cmd_str:
                    procs.append({
                        "pid": proc.info["pid"],
                        "ppid": proc.info["ppid"],
                        "create_time": proc.info.get("create_time", 0),
                        "cmdline": " ".join(cmdline)[:200],
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            pass
    return procs


def group_into_instances(procs):
    """Gruppiere Prozesse nach Prozesskette (PPID).

    Ein Daemon = venv-Python (Parent) + uv-Python (Child) = 1 Instanz.
    Erkenne: Wenn Prozess B die PPID von Prozess A hat, sind sie 1 Instanz.
    """
    if not procs:
        return []

    pid_map = {p["pid"]: p for p in procs}
    child_of = {}  # pid → parent_pid (nur wenn parent in der Liste)

    for p in procs:
        pid = p["pid"]
        ppid = p["ppid"]
        if ppid in pid_map:
            child_of[pid] = ppid

    def find_root(pid, seen=None):
        if seen is None:
            seen = set()
        if pid in seen:
            return pid  # Zyklus-Schutz
        seen.add(pid)
        if pid in child_of:
            return find_root(child_of[pid], seen)
        return pid

    groups = {}
    for p in procs:
        pid = p["pid"]
        root = pid if pid not in child_of else find_root(pid)
        groups.setdefault(root, []).append(p)

    instances = []
    for root_pid, members in groups.items():
        root_proc = pid_map[root_pid]
        instances.append({
            "root_pid": root_pid,
            "member_pids": [m["pid"] for m in members],
            "count": len(members),
            "create_time": root_proc["create_time"],
            "cmdline": root_proc["cmdline"],
        })

    return instances


def main():
    procs = find_learning_procs()
    instances = group_into_instances(procs)

    if not instances:
        print("WATCHDOG: KEINE online_learning.py --loop Instanz gefunden. Starte...")
        proc = subprocess.Popen(
            [VENV_PYTHON, SCRIPT, "--loop"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        procs_after = find_learning_procs()
        instances_after = group_into_instances(procs_after)
        if instances_after:
            inst = instances_after[0]
            print(f"WATCHDOG: Gestartet - Root-PID {inst['root_pid']}, "
                  f"{inst['count']} Prozess(e)")
        else:
            print("WATCHDOG: FEHLER - Prozess scheint nicht gestartet zu sein")
        return

    if len(instances) == 1:
        # Alles gut — genau 1 Daemon-Instanz, silent exit
        return

    # Mehrere Daemon-Instanzen — älteste behalten, rest killen
    instances.sort(key=lambda x: x["create_time"])
    oldest = instances[0]
    to_kill = instances[1:]
    print(f"WATCHDOG: {len(instances)} Daemon-Instanz(en) gefunden. "
          f"Behalte Root-PID {oldest['root_pid']} ({oldest['count']} Prozess(e)), "
          f"kill {len(to_kill)} Duplikat(e).")
    for inst in to_kill:
        for pid in inst["member_pids"]:
            try:
                kill_proc = psutil.Process(pid)
                kill_proc.terminate()
                gone, alive = psutil.wait_procs([kill_proc], timeout=3)
                if alive:
                    kill_proc.kill()
                print(f"  -> PID {pid} beendet")
            except Exception as e:
                print(f"  -> PID {pid} FEHLER: {e}")


if __name__ == "__main__":
    main()