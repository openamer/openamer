"""One-off parallel i18n backfill: several locale chains at once, then normalize.

Why this exists: the 30-minute cron advances one locale per slot, measured at
~25-60 strings/minute, which leaves ~2 days of work for the 87k remaining strings.
The bottleneck is the free translation API's latency per batch, not this machine,
so running several locales at the same time is the lever.

Safeguards:
  * the i18n cron is paused first -- its normalize() rewrites EVERY catalog and
    would clobber a worker's delivery
  * every worker runs with --no-normalize for the same reason
  * normalize runs exactly once, at the end, after all workers stopped
  * the cron is resumed in a finally block, so a crash cannot leave it paused
"""
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path.home() / "openamer-repo"
HOME = pathlib.Path(os.path.expanduser("~/AppData/Local/openamer-laptop"))
LOG = HOME / "reports" / "i18n-backfill.log"
CRON_ID = "34a170dc3892"
WORKERS = 4
BUDGET_MIN = 90


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def pending_locales() -> list[str]:
    """Locales that miss strings or speak a foreign script, worst first."""
    out = subprocess.run(
        [sys.executable, "scripts/i18n_converge.py", "--report",
         "--json", str(HOME / "reports" / "i18n-backfill-state.json")],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log("report: " + (out.stdout or "").strip().splitlines()[-1] if out.stdout else "report failed")
    data = json.loads((HOME / "reports" / "i18n-backfill-state.json").read_text(encoding="utf-8"))
    rows = data["locales"]
    todo = [r for r in rows if r.get("real_gaps", 1) > 0 or r.get("script_gaps", 0) > 0]
    todo.sort(key=lambda r: r.get("share", 1))
    return [r["locale"] for r in todo]


def cron(action: str) -> None:
    r = subprocess.run(["openamer", "cron", action, CRON_ID], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    log(f"cron {action}: rc={r.returncode} {(r.stdout or r.stderr).strip()[:120]}")


def main() -> int:
    todo = pending_locales()
    log(f"pending locales: {len(todo)}")
    if not todo:
        return 0

    slices = [todo[i::WORKERS] for i in range(WORKERS)]
    cron("pause")
    procs = []
    try:
        python_exe = str(REPO / "venv" / "Scripts" / "python.exe")
        for idx, locales in enumerate(slices):
            cmd = [python_exe, "scripts/i18n_converge.py",
                   "--only", ",".join(locales),
                   "--budget-minutes", str(BUDGET_MIN),
                   "--no-normalize", "--order", "worst"]
            out = open(HOME / "reports" / f"i18n-backfill-{idx}.log", "w", encoding="utf-8")
            p = subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT)
            procs.append((idx, p, out, len(locales)))
            log(f"worker {idx}: {len(locales)} locales, pid {p.pid} -> {locales[:6]}...")
        while procs:
            alive = []
            for idx, p, out, n in procs:
                if p.poll() is None:
                    alive.append((idx, p, out, n))
                else:
                    log(f"worker {idx} finished rc={p.returncode} ({n} locales)")
                    out.close()
            procs = alive
            if procs:
                time.sleep(30)
    finally:
        # normalize once, on a quiet tree
        python_exe = str(REPO / "venv" / "Scripts" / "python.exe")
        for script in ("i18n_fix_plural_double_word.py", "i18n_fix_aria_hotkeys.py"):
            r = subprocess.run([python_exe, f"scripts/{script}", "--apply"],
                               cwd=REPO, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            log(f"normalize {script}: rc={r.returncode}")
        cron("resume")

    check = subprocess.run([python_exe, "scripts/i18n_converge.py", "--report"],
                           cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    for line in (check.stdout or "").strip().splitlines()[-3:]:
        log("after: " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())