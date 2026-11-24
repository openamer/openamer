#!/usr/bin/env python3
"""Find composite/list-constant drift in the OpenAmer toolset layer.

Two port artifacts this reports in one pass, instead of one pytest failure at a
time:

  (A) MISSING MEMBER — a configurable leaf toolset whose static tools are NOT a
      subset of a platform composite that is supposed to bundle it. The subset
      test that drives expansion (`_get_platform_tools`, `_expand_parent_toolsets`)
      then silently drops that toolset, and the failure text names the FEATURE
      (e.g. "browser not found in {...}") rather than the drifted string.

  (B) EXTRA MEMBER — a non-configurable toolset that the config layer's
      "recover non-configurable platform toolsets" block auto-enables for a
      platform, i.e. a capability that leaks past an explicit
      `platform_toolsets` override (e.g. 'asi').

Usage (from the repo root, or point --root at a worktree of origin/main):

    .venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/composite_toolset_drift.py
    .venv/Scripts/python.exe .../composite_toolset_drift.py --root C:/Users/damir/wt-toolset

Exit code 1 when drift is found, 0 when clean — usable as a gate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root (or worktree) to inspect")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "toolsets.py").is_file():
        print(f"ABORT: no toolsets.py under {root} — pass --root <repo>")
        return 1
    sys.path.insert(0, str(root))

    from toolsets import TOOLSETS, resolve_toolset          # noqa: E402
    from openamer_cli.tools_config import (                 # noqa: E402
        CONFIGURABLE_TOOLSETS,
        _DEFAULT_OFF_TOOLSETS,
        PLATFORMS,
    )

    configurable = {k for k, _, _ in CONFIGURABLE_TOOLSETS}
    # Leaf toolsets whose tools sit inside the platform composites.
    leaves = [
        k for k, v in TOOLSETS.items()
        if k not in configurable and not v.get("includes") and not v.get("posture")
    ]

    drift = 0
    print("=== (A) MISSING MEMBER: leaf tools not inside the bundle that should hold them ===")
    for platform, meta in PLATFORMS.items():
        composite = meta["default_toolset"]
        bundle = set(resolve_toolset(composite, include_registry=False))
        for leaf in configurable:
            leaf_tools = set(resolve_toolset(leaf, include_registry=False))
            if not leaf_tools:
                continue
            extra = leaf_tools - bundle
            if extra:
                drift += 1
                print(f"  {platform:12s} bundle={composite:22s} "
                      f"leaf={leaf:14s} NOT bundled: {sorted(extra)}")
    if not drift:
        print("  (none)")

    print()
    print("=== (B) EXTRA MEMBER: non-configurable toolsets auto-recovered per platform ===")
    for platform, meta in PLATFORMS.items():
        bundle = set(resolve_toolset(meta["default_toolset"], include_registry=False))
        configurable_universe = set()
        for ck in configurable:
            configurable_universe.update(resolve_toolset(ck, include_registry=False))
        recovered = []
        for leaf in leaves:
            if leaf.startswith("openamer-"):
                continue
            if leaf in _DEFAULT_OFF_TOOLSETS:
                continue
            t = set(resolve_toolset(leaf, include_registry=False))
            if t and t.issubset(bundle) and not t.issubset(configurable_universe):
                recovered.append(leaf)
        print(f"  {platform:12s} default_toolset={meta['default_toolset']:22s} "
              f"recovered={sorted(recovered)}")
        # An explicit override must return exactly what the user listed; anything
        # in `recovered` is what leaks into it (and what `_DEFAULT_OFF_TOOLSETS`
        # / CONFIGURABLE_TOOLSETS membership is supposed to control).
        if recovered:
            drift += 1

    print()
    print(f"drift signals: {drift}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
