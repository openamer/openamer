"""Runtime import scan: actually import every module and report failures.

Ground truth for "which modules are broken". A syntax/compile check cannot see a
cross-module ``from x import y`` that no longer exists, and an AST audit cannot
see names resolved through module ``__getattr__`` — the exact failure class that
made every OpenAmer launch die at ``agent init failed`` while the tree still
compiled cleanly.

Run it as a gate before pushing:

    venv/Scripts/python.exe scripts/check_runtime_imports.py
    # exit 0 = every module imports; exit 1 = at least one is broken

Optional-extra packages (acp, mcp) and POSIX-only stdlib modules legitimately
fail on a base Windows install; they are reported separately and do not fail the
gate unless ``--strict-extras`` is passed.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKIP = {"tests", "node_modules", "venv", ".venv", "__pycache__", "website", "out", "build", "dist"}
TARGETS = ("agent", "tools", "openamer_cli", "gateway", "cron", "acp_adapter", "tui_gateway", "providers")

# Modules that need an optional extra or a POSIX-only stdlib module. Their
# absence is expected on a base Windows install and is NOT a broken tree.
EXPECTED_UNAVAILABLE = (
    "fcntl",          # openamer_cli.pty_bridge — POSIX-only; Windows uses win_pty_bridge
    "termios",
    "ptyprocess",
    "acp",            # acp_adapter.* — pip install 'openamer[acp]'
    "mcp",            # MCP client surface — pip install 'openamer[mcp]'
)


def modules_of(pkg: str) -> list[str]:
    base = ROOT / pkg
    names: list[str] = []
    if not base.is_dir():
        return names
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = Path(dirpath).relative_to(ROOT) / fn
            mod = ".".join(rel.with_suffix("").parts)
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            names.append(mod)
    return sorted(names)


def is_expected(message: str) -> bool:
    return any(f"No module named '{name}'" in message for name in EXPECTED_UNAVAILABLE)


def main() -> int:
    ap = argparse.ArgumentParser(description="Runtime import gate for the openamer tree.")
    ap.add_argument("--strict-extras", action="store_true",
                    help="also fail on modules needing an optional extra / POSIX-only stdlib")
    args = ap.parse_args()

    broken: list[tuple[str, str, str]] = []
    expected: list[tuple[str, str]] = []
    scanned = 0

    for pkg in TARGETS:
        for mod in modules_of(pkg):
            if mod in TARGETS:  # the package __init__ itself
                continue
            scanned += 1
            try:
                importlib.import_module(mod)
            except ImportError as exc:
                msg = str(exc)
                if is_expected(msg) and not args.strict_extras:
                    expected.append((mod, msg))
                else:
                    broken.append((mod, "ImportError", msg))
            except Exception as exc:  # noqa: BLE001 — every failure kind matters here
                broken.append((mod, type(exc).__name__, str(exc)[:200]))

    print(f"scanned {scanned} modules")
    if expected:
        print(f"\nskipped {len(expected)} module(s) needing an optional extra / POSIX-only stdlib:")
        for mod, msg in expected:
            print(f"  {mod}: {msg}")

    if not broken:
        print("\nOK — every scanned module imports cleanly")
        return 0

    print(f"\nBROKEN: {len(broken)} module(s) fail to import\n")
    for mod, kind, msg in broken:
        print(f"{kind:14s} {mod}\n    {msg}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
