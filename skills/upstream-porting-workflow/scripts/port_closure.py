#!/usr/bin/env python3
"""Transitive dependency closure for a set of upstream modules.

WHY: a partial port looks like a LOGIC bug. The ported module imports fine, but
names inside its import block resolve against modules that were never brought
along -- and a broad `except ImportError: return []` turns that into silent empty
output, surfacing as `assert [] == [...]` in a test.

Before copying any file, this answers "is this a 4-file port or a subtree?" by
walking the upstream `from <pkg>.X import` / `from .X import` graph and reporting
what is genuinely absent in the local tree.

Usage:
    port_closure.py <upstream-root> <local-root> <upstream-pkg> <local-pkg> <mod> [mod...]

Example:
    port_closure.py <upstream-checkout> <local-checkout> \
                    <upstream-package> openamer_cli \
                    model_switch_providers
"""
import re
import sys
from pathlib import Path


def lines_of(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def main() -> int:
    if len(sys.argv) < 6:
        print(__doc__)
        return 2

    up_root, loc_root = Path(sys.argv[1]), Path(sys.argv[2])
    up_pkg, loc_pkg = sys.argv[3], sys.argv[4]
    seeds = sys.argv[5:]

    seen: set[str] = set()
    to_port: list[str] = []
    present: list[str] = []
    absent_upstream: list[str] = []
    queue = list(seeds)

    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)

        loc_file = loc_root / loc_pkg / f"{mod}.py"
        loc_pkgdir = loc_root / loc_pkg / mod / "__init__.py"
        if loc_file.is_file() or loc_pkgdir.is_file():
            present.append(mod)
            continue

        up_file = up_root / up_pkg / f"{mod}.py"
        if not up_file.is_file():
            absent_upstream.append(mod)
            continue

        to_port.append(f"{mod} ({lines_of(up_file)} lines)")
        text = up_file.read_text(encoding="utf-8", errors="replace")
        for dep in (set(re.findall(rf"from {up_pkg}\.(\w+) import", text))
                    | set(re.findall(r"from \.(\w+) import", text))):
            queue.append(dep)

    total = sum(int(re.search(r"\((\d+) lines\)", m).group(1)) for m in to_port) \
        if to_port else 0

    print(f"seeds: {seeds}\n")
    print(f"TO PORT ({len(to_port)} modules, {total} lines):")
    for m in sorted(to_port):
        print(f"  {m}")
    if absent_upstream:
        print(f"\nABSENT BOTH SIDES ({len(absent_upstream)}):")
        for m in sorted(absent_upstream):
            print(f"  {m}  <- not a port gap; check for a local equivalent / rename")
    print(f"\nalready present ({len(present)}):")
    for m in sorted(present):
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
