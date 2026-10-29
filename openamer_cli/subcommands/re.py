"""``openamer re`` — reverse-engineering surface inside OpenAmer.

This is the single entry point for the capability, so nobody has to remember
which repository a scanner lives in:

    openamer re doctor              which engines are actually usable here
    openamer re scan  <target>      inspect a JavaScript/Electron surface
    openamer re recall <query>      findings already recorded in memory

`scan` drives ``scripts/helix_scan.py``, OpenAmer's own engine: standard library
only, no external decompiler, because on a host without Ghidra, Hopper, IDA,
JADX or Kuna the upstream providers report ``provider_unavailable`` and nothing
can be inspected at all.

Findings are recorded through ``scripts/openamer_re_bridge.py`` only when
``--remember`` is passed: writing to long-term memory is a decision, not a side
effect of running a scan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE_VARIABLES = {
    "ghidra": "GHIDRA_INSTALL_DIR",
    "hopper": "HOPPER_SUPPORT_DIR",
    "ida": "IDA_INSTALL_DIR",
    "jadx": "JADX_HOME",
    "kuna": "KUNA_HOME",
}


def _home() -> Path:
    override = os.environ.get("OPENAMER_HOME")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "openamer-laptop"


def _scripts_dir() -> Path:
    # re.py lives at <root>/openamer_cli/subcommands/re.py, so the repo's
    # scripts/ is two levels up -- parents[3] is the directory ABOVE the
    # checkout, which is why CI reported ModuleNotFoundError: No module named
    # 'helix_scan' while a local install with %LOCALAPPDATA%\openamer-laptop    # scripts happened to work.
    repo_scripts = Path(__file__).resolve().parents[2] / "scripts"
    for candidate in (_home() / "scripts", repo_scripts):
        if (candidate / "helix_scan.py").is_file():
            return candidate
    return repo_scripts


def _load_scanner():
    scripts = _scripts_dir()
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import helix_scan  # noqa: PLC0415  (path is resolved at call time)

    return helix_scan


def _oare_command() -> list[str] | None:
    """The upstream CLI, if this machine has it. Absent is a normal state."""
    repo = Path(os.environ.get("OPENAMER_RE_REPO", "C:/Users/damir/openamer-rea"))
    script = repo / "scripts" / "rea.mjs"
    node = shutil.which("node")
    if script.is_file() and node:
        return [node, str(script)]
    binary = shutil.which("oare")
    return [binary] if binary else None


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
def cmd_doctor(args: argparse.Namespace) -> int:
    home = _home()
    scanner = _scripts_dir() / "helix_scan.py"
    bridge = home / "scripts" / "openamer_re_bridge.py"
    oare = _oare_command()

    print("OpenAmer RE — what is usable on this machine\n")

    if scanner.is_file():
        print(f"  helix engine   ready   {scanner}")
    else:
        print(f"  helix engine   MISSING {scanner}")

    if oare:
        print(f"  upstream CLI   ready   {' '.join(oare)}")
        try:
            version = subprocess.run(
                [*oare, "--version"], capture_output=True, text=True, timeout=120
            )
            print(f"                 version {(version.stdout or '').strip() or '?'}")
        except (OSError, subprocess.SubprocessError) as cause:
            print(f"                 not answering: {cause}")
    else:
        print("  upstream CLI   absent  (set OPENAMER_RE_REPO or install `oare`)")

    print(f"  memory bridge  {'ready' if bridge.is_file() else 'MISSING'}   {bridge}")
    print("\n  external engines — the upstream providers need one of these:")
    for name, variable in ENGINE_VARIABLES.items():
        value = os.environ.get(variable)
        state = "set" if value else "not configured"
        print(f"    {name:<8} {state:<15} {variable}")
    print(
        "\n  Without a decompiler, native binaries cannot be inspected by anything.\n"
        "  A JavaScript or Electron surface can: that is what `openamer re scan` does."
    )
    return 0


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def _evidence(report: dict, target: Path) -> dict:
    """Wrap a scanner report in the record shape the memory bridge accepts."""
    digest = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else ""
    return {
        "evidence_id": f"helix:{digest[:12] or hashlib.sha256(str(target).encode()).hexdigest()[:12]}",
        "subject": {
            "name": str(target),
            "format": report.get("kind") or "javascript-directory",
            "digest": {"sha256": digest},
        },
        "provider": {"id": "helix", "version": "1.0.0"},
        "operation": "scan_javascript_surface",
        "predicate_type": "structural",
        "confidence": "observed",
        "authority": "derived-from-artifact",
        "normalized_result": report,
        "limitations": report.get("limitations", []),
    }


def cmd_scan(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser()
    if not target.exists():
        print(f"openamer re scan: no such target: {target}", file=sys.stderr)
        return 2

    helix_scan = _load_scanner()
    try:
        if target.is_dir():
            finding = helix_scan.collect_from_directory(target)
        else:
            finding = helix_scan.collect_from_asar(target)
    except (OSError, ValueError) as cause:
        print(f"openamer re scan: {cause}", file=sys.stderr)
        return 2

    report = finding.as_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else helix_scan.summarize(report))

    if not args.remember:
        print("\n(not recorded — pass --remember to store this as a memory episode)")
        return 0

    bridge = _home() / "scripts" / "openamer_re_bridge.py"
    if not bridge.is_file():
        print(f"\nopenamer re scan: memory bridge missing at {bridge}", file=sys.stderr)
        return 1

    evidence = _evidence(report, target)
    handle, path = tempfile.mkstemp(prefix="helix-evidence-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False)
        completed = subprocess.run(
            [sys.executable, str(bridge), "ingest", path, "--kind", "re_finding"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        Path(path).unlink(missing_ok=True)

    print()
    print((completed.stdout or "").strip() or (completed.stderr or "").strip())
    return completed.returncode


# --------------------------------------------------------------------------- #
# recall
# --------------------------------------------------------------------------- #
def cmd_recall(args: argparse.Namespace) -> int:
    memory = next(
        (
            candidate
            for candidate in (
                _home() / "scripts" / "longterm_memory.py",
                _home() / "scripts" / "training" / "longterm_memory.py",
                Path(__file__).resolve().parents[3] / "scripts" / "longterm_memory.py",
            )
            if candidate.is_file()
        ),
        None,
    )
    if memory is None:
        print(
            "openamer re recall: longterm_memory.py not found under "
            f"{_home() / 'scripts'}",
            file=sys.stderr,
        )
        return 1
    completed = subprocess.run(
        [sys.executable, str(memory), "query", args.query],
        capture_output=True,
        text=True,
        timeout=300,
    )
    print((completed.stdout or "").strip() or (completed.stderr or "").strip())
    return completed.returncode


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_re_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "re",
        help="Reverse-engineer an app without its source: scan, doctor, recall",
        description=(
            "Inspect a shipped application. `scan` reads JavaScript and Electron "
            "surfaces with OpenAmer's own engine and states its blind spots; "
            "`doctor` shows which external decompilers are actually installed."
        ),
    )
    actions = parser.add_subparsers(dest="re_command", metavar="COMMAND")
    parser.set_defaults(func=cmd_doctor)

    doctor = actions.add_parser("doctor", help="Which engines are usable here")
    doctor.set_defaults(func=cmd_doctor)

    scan = actions.add_parser("scan", help="Inspect an ASAR archive or a JavaScript directory")
    scan.add_argument("target", help="Path to an .asar archive or a directory")
    scan.add_argument("--json", action="store_true", help="Machine-readable report")
    scan.add_argument(
        "--remember",
        action="store_true",
        help="Record the finding as an episodic memory (never implicit)",
    )
    scan.set_defaults(func=cmd_scan)

    recall = actions.add_parser("recall", help="Search earlier findings in long-term memory")
    recall.add_argument("query", help="What to look for")
    recall.set_defaults(func=cmd_recall)
