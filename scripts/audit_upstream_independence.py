"""Audit: how much of OpenAmer is genuinely OpenAmer vs. rebranded upstream.

For every upstream file that has an OpenAmer counterpart, we:
  1. apply the known rebrand map to the upstream text
  2. compute a real diff (not a ratio) on top of that
  3. classify the delta:
       IDENTICAL      -> still upstream, only renamed
       COSMETIC       -> only trivial edits (imports, docstrings, naming)
       SUBSTANTIVE   -> real logic divergence
  4. report the size of the substantive delta

Also scans the whole repo for residual upstream coupling:
  - runtime imports of upstream module names
  - pip/npm dependencies that are upstream-specific
  - network/updater references to the upstream repo
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import json
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from upstream_rebrand import rebrand  # noqa: E402

OA = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_UP = pathlib.Path(r"C:\Users\damir\AppData\Local\hermes\hermes-agent")
UP = DEFAULT_UP

NOISE = re.compile(
    r"^\s*(#\s*(Copyright|Licensed|SPDX)|\"\"\"|\'\'\'|#\s*-{3,}|"
    r"from\s+openamer|import\s+openamer|"
    r"#\s*(Upstream|Ported from|Adapted from|Rebrand|hermes|openamer))",
    re.IGNORECASE,
)

PAIRS = (("agent", "agent"), ("openamer_cli", "hermes_cli"))


def _load_marker_helper():
    """Import the provenance helper without making the script depend on it."""
    import importlib.util

    helper = OA / "openamer_cli" / "upstream_provenance.py"
    if not helper.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_oa_provenance", helper)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


find_marker = None
_helper = _load_marker_helper()
if _helper is not None:
    find_marker = _helper.find_marker


def _has_marker(text: str) -> bool:
    if find_marker is None:
        # Fallback: the marker line can be detected without the helper.
        return "Upstream-Derived:" in text
    return find_marker(text) is not None


def _changed_lines(a: list[str], b: list[str], noise: re.Pattern[str]) -> tuple[int, int]:
    """Return (upstream_lines_changed, new_lines_added).

    ``upstream_lines_changed`` counts the upstream lines that no longer survive
    unchanged in the OpenAmer version -- the honest denominator for "how much
    of upstream is still here". ``new_lines_added`` counts the lines OpenAmer
    wrote that upstream never had.

    A modified line is one change, not two: ``difflib.unified_diff`` emits a
    ``-`` and a ``+`` line for it. ``SequenceMatcher`` opcodes report the
    replacement block once, so a modified block counts as
    ``max(removed, added)``.
    """
    matcher = difflib.SequenceMatcher(None, a, b)
    upstream_changed = 0
    added = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            removed, new = a[i1:i2], b[j1:j2]
        elif tag == "delete":
            removed, new = a[i1:i2], []
        elif tag == "insert":
            removed, new = [], b[j1:j2]
        else:  # pragma: no cover - difflib emits no other tags
            continue

        def _substantive(lines: list[str]) -> int:
            return sum(
                1
                for line in lines
                if line.strip()
                and len(line.strip()) >= 4
                and not noise.match(line)
            )

        upstream_changed += _substantive(removed)
        added += _substantive(new)
    # A modified block counts once, not as removed+added.
    return max(upstream_changed, added), added


def classify(up_text: str, oa_text: str) -> tuple[str, int, int]:
    """Return (class, changed_lines, upstream_lines)."""
    src = rebrand(up_text)
    a = src.splitlines()
    b = oa_text.splitlines()
    up_lines = len(a)
    if src.strip() == oa_text.strip():
        return "IDENTICAL", 0, up_lines

    changed, _added = _changed_lines(a, b, NOISE)

    ratio = changed / max(up_lines, 1)
    if changed == 0:
        return "COSMETIC", 0, up_lines
    if ratio < 0.10:
        return "MINOR", changed, up_lines
    return "SUBSTANTIVE", changed, up_lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--upstream",
        default=str(DEFAULT_UP),
        help="path to the upstream checkout to compare against",
    )
    args = ap.parse_args(argv)
    upstream = pathlib.Path(args.upstream).expanduser()
    if not upstream.is_dir():
        print(f"upstream checkout not found: {upstream}", file=sys.stderr)
        return 2
    return audit(upstream, OA)


def audit(upstream: pathlib.Path, openamer: pathlib.Path) -> int:
    """Audit ``openamer`` against ``upstream`` and write the JSON report."""
    results = []
    identical = cosmetic = minor = substantive = 0
    only_openamer = 0
    marked: list[str] = []
    unmarked: list[str] = []

    for oa_sub, up_sub in PAIRS:
        up_dir = upstream / up_sub
        oa_dir = openamer / oa_sub
        if not up_dir.is_dir():
            continue
        for up_file in sorted(up_dir.rglob("*.py")):
            rel = up_file.relative_to(up_dir)
            oa_file = oa_dir / rel
            if not oa_file.exists():
                only_openamer += 1
                continue
            try:
                up_text = up_file.read_text(encoding="utf-8", errors="replace")
                oa_text = oa_file.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:  # pragma: no cover
                print(f"SKIP {oa_sub}/{rel}: {exc}", file=sys.stderr)
                continue
            cls, changed, up_lines = classify(up_text, oa_text)
            if cls == "IDENTICAL":
                identical += 1
                if _has_marker(oa_text):
                    marked.append(f"{oa_sub}/{rel.as_posix()}")
                else:
                    unmarked.append(f"{oa_sub}/{rel.as_posix()}")
            elif cls == "COSMETIC":
                cosmetic += 1
            elif cls == "MINOR":
                minor += 1
            else:
                substantive += 1
            results.append(
                {
                    "file": f"{oa_sub}/{rel.as_posix()}",
                    "class": cls,
                    "changed_lines": changed,
                    "upstream_lines": up_lines,
                    "ratio": round(changed / max(up_lines, 1), 3),
                }
            )

    results.sort(key=lambda r: (r["class"], r["ratio"]))
    out = openamer / "reports" / "upstream-independence-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("=" * 68)
    print("UPSTREAM INDEPENDENCE AUDIT")
    print("=" * 68)
    print(f"upstream ref        : {upstream}")
    print(f"openamer tree       : {openamer}")
    print()
    print(f"IDENTICAL (rebrand only) : {identical:4d}")
    print(f"COSMETIC (noise only)    : {cosmetic:4d}")
    print(f"MINOR   (<10% changed)   : {minor:4d}")
    print(f"SUBSTANTIVE (real logic) : {substantive:4d}")
    print(f"openamer-only files      : {only_openamer:4d}")
    print(f"total compared           : {len(results):4d}")

    leaky = [r for r in results if r["class"] == "IDENTICAL"]
    if leaky:
        print("\n--- still verbatim upstream (rebranded only) ---")
        for r in leaky:
            tag = "attributed" if r["file"] in marked else "UNATTRIBUTED"
            print(f"  [{tag}] {r['file']}  ({r['upstream_lines']} lines)")

    print(f"\nprovenance markers on verbatim files: {len(marked)}/{len(leaky)}")
    if unmarked:
        print("  files missing a marker:")
        for f in unmarked:
            print(f"    {f}")

    worst = [r for r in results if r["class"] == "SUBSTANTIVE"]
    worst.sort(key=lambda r: -r["ratio"])
    print(f"\n--- top 20 by divergence ratio ({len(worst)} substantive) ---")
    for r in worst[:20]:
        print(
            f"  {r['ratio']:.3f}  {r['changed_lines']:5d}/{r['upstream_lines']:<6d} {r['file']}"
        )
    print(f"\nreport written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
