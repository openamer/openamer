#!/usr/bin/env python3
"""Self-modification with a test gate and rollback — for OpenAmer Agent.

This is the "does not break" axis made concrete for OpenAmer itself: a change
to a core file is only kept if the test suite proves it does not break
anything. On any failure the original is restored atomically.

Why a script + skill instead of a core tool: OpenAmer's design rule is "the
core is a narrow waist; capability lives at the edges." A self-modify *tool*
would ship on every API call. A script invoked via the terminal tool costs
nothing until it is actually used — the same capability, zero footprint.

Usage:
    python scripts/self_modify.py <path> <new_content_file>
    python scripts/self_modify.py <path> --content "new content"
    python scripts/self_modify.py <path> --patch <patch_file>

The target path must be inside the openamer-agent package. The change is
applied, the test suite runs, and the change is kept only if tests pass.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_target(path: str) -> Path:
    root = _repo_root().resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise SystemExit(f"refusing to modify outside the repo: {path}")
    if not target.exists():
        raise SystemExit(f"target does not exist: {path}")
    if not target.is_file():
        raise SystemExit(f"target is not a file: {path}")
    return target


def _syntax_check(path: Path) -> tuple[bool, str]:
    """Compile the target file; a broken Python file fails immediately."""
    if path.suffix != ".py":
        return (True, "")
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except SyntaxError as e:
        return (False, f"syntax error: {e}")
    return (True, "")


def _run_tests(scope: str | None = None) -> tuple[bool, str]:
    root = _repo_root()
    # Prefer the venv python (has pytest), then the current python, then the
    # canonical runner. This makes the gate work regardless of how the repo
    # was installed (venv, uv, nix, etc.).
    target = scope or "tests/"
    candidates: list[list[str]] = []
    for venv_py in (root / "venv" / "Scripts" / "python.exe", root / ".venv" / "Scripts" / "python.exe", root / "venv" / "bin" / "python", root / ".venv" / "bin" / "python"):
        if venv_py.exists():
            candidates.append([str(venv_py), "-m", "pytest", target, "-q"])
    candidates.append([sys.executable, "-m", "pytest", target, "-q"])

    last_err = ""
    for cmd in candidates:
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            return (False, "(tests timed out)")
        except FileNotFoundError as e:
            last_err = f"(runner not found: {e})"
            continue
        # If pytest isn't installed in this interpreter, try the next.
        if "No module named pytest" in (proc.stderr or ""):
            last_err = "(pytest not installed in this interpreter)"
            continue
        tail = (proc.stdout or "") + (proc.stderr or "")
        return (proc.returncode == 0, tail[-3000:])
    return (False, last_err or "(no test runner available)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-modify a core file, gated by tests.")
    parser.add_argument("path", help="path to the file to modify (relative to repo root)")
    parser.add_argument("new_content_file", nargs="?", help="file containing the new content")
    parser.add_argument("--content", help="new content as a string")
    parser.add_argument("--patch", help="unified diff file to apply (git apply)")
    parser.add_argument("--tests", help="test scope to gate on (default: full tests/)")
    args = parser.parse_args()

    target = _resolve_target(args.path)
    # Preserve exact bytes (CRLF vs LF) so rollback is byte-identical.
    original = target.read_bytes()
    backup = target.with_suffix(target.suffix + ".bak")

    # Determine the new content.
    if args.patch:
        patch_path = Path(args.patch).expanduser()
        if not patch_path.exists():
            raise SystemExit(f"patch file not found: {args.patch}")
        backup.write_bytes(original)
        try:
            r = subprocess.run(
                ["git", "apply", str(patch_path)],
                cwd=_repo_root(),
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                backup.unlink(missing_ok=True)
                raise SystemExit(f"patch failed: {r.stderr}")
        except FileNotFoundError:
            backup.unlink(missing_ok=True)
            raise SystemExit("git not found")
    else:
        if args.content is not None:
            new_content = args.content
        elif args.new_content_file:
            new_content = Path(args.new_content_file).expanduser().read_text(encoding="utf-8")
        else:
            raise SystemExit("provide new_content_file, --content, or --patch")
        backup.write_bytes(original)
        target.write_text(new_content, encoding="utf-8")

    # Syntax gate first (always on, catches broken Python immediately and
    # cheaply, before spending time on the test suite).
    ok, err = _syntax_check(target)
    if not ok:
        target.write_bytes(original)
        backup.unlink(missing_ok=True)
        print(f"✗ change rejected ({err}, rolled back)")
        return 1

    # Test gate.
    ok, tail = _run_tests(args.tests)
    if not ok:
        # Rollback.
        target.write_bytes(original)
        backup.unlink(missing_ok=True)
        print(f"✗ change rejected (tests failed, rolled back):\n{tail[-800:]}")
        return 1

    backup.unlink(missing_ok=True)
    print(f"✓ change to {args.path} applied and verified (tests pass)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
