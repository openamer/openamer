"""Launch a translation swarm: one worker per (backend x locale slice).

Why a swarm and not one big fleet: measured on this machine, a single free
provider answers `HTTP 429` and then sits in a 4 x 40 s backoff, while another
provider answers the same chunk immediately. One shared backend list therefore
serialises the whole fleet behind the slowest provider. Pinning each worker
process to one backend (`OPENAMER_I18N_BACKEND`) turns that into parallel lanes:
a throttled provider only slows its own slice, and every lane owns a different
set of languages, so no two workers write the same locale.

Usage:
    python scripts/start_translation_swarm.py                 # all usable backends
    python scripts/start_translation_swarm.py --workers 2     # processes per backend
    python scripts/start_translation_swarm.py --status
    python scripts/start_translation_swarm.py --target cli
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
LOGDIR = HOME / "logs"
PIDFILE = LOGDIR / "translation-swarm.pid.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pending_locales() -> list[str]:
    names = json.loads((REPO / "locales" / "_languages.json").read_text(encoding="utf-8"))
    return [code for code in names if code != "en"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2, help="processes per backend")
    ap.add_argument("--threads", type=int, default=3, help="threads per process")
    ap.add_argument("--target", choices=("desktop", "cli"), default="desktop")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        if not PIDFILE.exists():
            print("no translation swarm recorded")
            return 1
        rec = json.loads(PIDFILE.read_text(encoding="utf-8"))
        alive = 0
        for w in rec.get("workers", []):
            ok = load("launcher_probe", REPO / "scripts" / "start_i18n_detached.py")._pid_alive(w["pid"])
            alive += 1 if ok else 0
            print(f"  pid {w['pid']:<8} {'alive' if ok else 'dead '}  {w['backend']:<26} "
                  f"{len(w['locales'])} locales  log={Path(w['log']).name}")
        print(f"{alive}/{len(rec.get('workers', []))} swarm workers alive; started {rec.get('started')}")
        return 0 if alive else 1

    script_name = ("fill_desktop_locales.py" if args.target == "desktop"
                   else "i18n_fill_cli_locales.py")
    module = load("swarm_target", REPO / "scripts" / script_name)
    env = module.load_env()
    chain = module.backend_chain(env)
    names = [cand[0] for cand in chain]
    if not names:
        print("no usable backend: every key is missing")
        return 1

    todo = pending_locales()
    if not todo:
        print(f"nothing pending for {args.target}")
        return 0

    # One lane per backend, then one slice per worker inside that lane.
    lanes: dict[str, list[list[str]]] = {name: [[] for _ in range(args.workers)] for name in names}
    for index, code in enumerate(todo):
        lane = lanes[names[index % len(names)]]
        lane[index % len(lane)].append(code)

    LOGDIR.mkdir(parents=True, exist_ok=True)
    workers = []
    for backend, slices in lanes.items():
        for slot, codes in enumerate(slices, 1):
            if not codes:
                continue
            log = LOGDIR / f"swarm-{args.target}-{backend}-{slot}.log"
            child_env = os.environ.copy()
            child_env["OPENAMER_I18N_BACKEND"] = backend
            child_env["OPENAMER_DESKTOP_WORKERS" if args.target == "desktop"
                      else "OPENAMER_I18N_WORKERS"] = str(args.threads)
            kwargs: dict = {
                "cwd": str(REPO), "env": child_env, "stdin": subprocess.DEVNULL,
                "stdout": open(log, "w", encoding="utf-8"), "stderr": subprocess.STDOUT,
            }
            if os.name == "nt":
                kwargs["creationflags"] = 0x00000008 | 0x00000200
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen([sys.executable, str(REPO / "scripts" / script_name), *codes], **kwargs)
            created = None
            try:
                import psutil
                created = psutil.Process(proc.pid).create_time()
            except Exception:  # noqa: BLE001 - bookkeeping must not abort a launch
                created = None
            workers.append({"pid": proc.pid, "created": created, "backend": backend,
                            "locales": codes, "log": str(log)})
            print(f"  {backend:<26} slot {slot}: pid {proc.pid} -> {len(codes)} locales ({log.name})")

    PIDFILE.write_text(json.dumps({"started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "target": args.target, "pending": len(todo),
                                   "workers": workers}, indent=1),
                       encoding="utf-8", newline="\n")
    print(f"\n{len(workers)} swarm workers for {len(todo)} locales across {len(names)} backends")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
