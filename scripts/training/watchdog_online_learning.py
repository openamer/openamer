#!/usr/bin/env python
"""Watchdog: Prüft ob online_learning.py --loop läuft, startet ggf. oder killt Duplikate.

Wichtig: Der Daemon besteht aus 2 Prozessen (venv-Parent + uv-Child) = 1 Instanz.
Zähle Prozesse mit gemeinsamer PPID-Kette als 1 Instanz.
"""
import psutil, sys, os, subprocess, time

VENV_PYTHON = r"C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe"
SCRIPT = r"C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\online_learning.py"

def find_learning_procs():
    """Finde alle Prozesse mit online_learning.py --loop in der CommandLine."""
    procs = []
    for proc in psutil.process_iter(['pid', 'ppid', 'create_time', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            if not cmdline:
                continue
            cmd_str = ' '.join(cmdline).lower()
            if any(py in cmdline[0].lower() for py in ['python', 'python3']):
                if 'online_learning.py' in cmd_str and '--loop' in cmd_str:
                    procs.append({
                        'pid': proc.info['pid'],
                        'ppid': proc.info['ppid'],
                        'create_time': proc.info.get('create_time', 0),
                        'cmdline': ' '.join(cmdline)[:200]
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
    
    # Baue PID->Prozess Map
    pid_map = {p['pid']: p for p in procs}
    
    # Finde Root-Prozesse (deren PPID nicht in der Liste ist)
    root_pids = set()
    child_of = {}  # pid -> root_pid
    
    for p in procs:
        pid = p['pid']
        ppid = p['ppid']
        if ppid in pid_map:
            # Dies ist ein Child-Prozess, finde seinen Root
            child_of[pid] = ppid
        else:
            root_pids.add(pid)
    
    # Verfolge Child-Ketten bis zum Root
    def find_root(pid, seen=None):
        if seen is None:
            seen = set()
        if pid in seen:
            return pid  # Zyklus-Schutz
        seen.add(pid)
        if pid in child_of:
            return find_root(child_of[pid], seen)
        return pid
    
    # Gruppiere: root_pid -> [pids]
    groups = {}
    for p in procs:
        pid = p['pid']
        if pid in root_pids:
            root = pid
        else:
            root = find_root(pid)
        if root not in groups:
            groups[root] = []
        groups[root].append(p)
    
    # Gib eine Liste von Instanzen zurück (je 1 Root-Prozess)
    instances = []
    for root_pid, members in groups.items():
        root_proc = pid_map[root_pid]
        instances.append({
            'root_pid': root_pid,
            'member_pids': [m['pid'] for m in members],
            'count': len(members),
            'create_time': root_proc['create_time'],
            'cmdline': root_proc['cmdline']
        })
    
    return instances

def main():
    procs = find_learning_procs()
    instances = group_into_instances(procs)
    
    if not instances:
        print("WATCHDOG: KEINE online_learning.py --loop Instanz gefunden. Starte...")
        sys.stdout.flush()
        logpath = os.path.join(os.path.dirname(SCRIPT), "..", "logs", "online_learning.log")
        try:
            logfile = open(logpath, "a", encoding="utf-8")
        except Exception:
            logfile = subprocess.DEVNULL
        proc = subprocess.Popen(
            [VENV_PYTHON, SCRIPT, "--loop"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=logfile,
            stderr=subprocess.STDOUT
        )
        # Liveness-Check mit Retry: der Daemon ist ein Twin-Chain (venv-Parent +
        # uv-Child), der oft langsamer startet als ein einzelner Prozess.
        # Warte stattdessen auf echte Prozess-Existenz, bis sie stirbt oder
        # die Maximalzeit erreicht ist — ein einfacher sleep(2) hat den Daemon
        # 38 Tage lang nicht zuverlässig erkannt.
        deadline = time.time() + 30
        started = False
        while time.time() < deadline:
            if proc.poll() is not None:
                print(f"WATCHDOG: FEHLER - Prozess ist mit Code {proc.returncode} immediately beendet. Siehe Log: {logpath}")
                sys.stdout.flush()
                return
            procs_after = find_learning_procs()
            instances_after = group_into_instances(procs_after)
            if instances_after:
                inst = instances_after[0]
                print(f"WATCHDOG: Gestartet - Root-PID {inst['root_pid']}, {inst['count']} Prozess(e)")
                started = True
                break
            time.sleep(1)
        if not started:
            print(f"WATCHDOG: FEHLER - Prozess nicht innerhalb von 30s gestartet. Siehe Log: {logpath}")
            sys.stdout.flush()
        return
    
    if len(instances) == 1:
        inst = instances[0]
        # Alles gut - genau 1 Daemon-Instanz
        return
    
    # Mehrere Daemon-Instanzen - älteste behalten, rest killen
    instances.sort(key=lambda x: x['create_time'])
    oldest = instances[0]
    to_kill = instances[1:]
    print(f"WATCHDOG: {len(instances)} Daemon-Instanz(en) gefunden. Behalte Root-PID {oldest['root_pid']} ({oldest['count']} Prozess(e)), kill {len(to_kill)} Duplikat(e).")
    for inst in to_kill:
        for pid in inst['member_pids']:
            try:
                kill_proc = psutil.Process(pid)
                kill_proc.terminate()
                gone, alive = psutil.wait_procs([kill_proc], timeout=3)
                if alive:
                    kill_proc.kill()
                print(f"  -> PID {pid} beendet")
            except Exception as e:
                print(f"  -> PID {pid} FEHLER: {e}")

if __name__ == '__main__':
    main()