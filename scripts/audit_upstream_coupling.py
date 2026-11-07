"""Scan OpenAmer for residual upstream coupling - core tree only (fast)."""

from __future__ import annotations

import pathlib
import re
import json

OA = pathlib.Path(__file__).resolve().parent.parent

ROOTS = [
    "agent", "openamer_cli", "openamer_brain", "tools", "gateway",
    "scripts", "apps/desktop/src", "apps/desktop/e2e", "web", "ui-tui",
    "providers", "native", "os", "packs", "plugins",
]

SKIP_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".venv", "dist",
    "build", "target", "reports", "tmp", "out", "coverage",
}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".sh", ".ps1", ".json", ".yaml", ".yml", ".toml", ".md", ".cfg", ".txt"}

UPSTREAM_NAMES = {
    "hermes_cli", "hermes_constants", "hermes_state", "hermes_logging",
    "hermes_platform", "hermes_bootstrap", "hermes",
    "hermes_state_repair", "hermes_pkce", "hermes_dir_acl",
    "hermes_startup_watchdog", "hermes_state_api_content",
}

IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
NET_RE = re.compile(
    r"(NousResearch/hermes-agent|github\.com/NousResearch|hermes-agent"
    r"|raw\.githubusercontent\.com/NousResearch)", re.IGNORECASE)
HERMES_TOKEN = re.compile(r"\bhermes\b", re.IGNORECASE)


def main() -> None:
    files: list[pathlib.Path] = []
    for root in ROOTS:
        rp = OA / root
        if not rp.exists():
            continue
        for p in rp.rglob("*"):
            if p.is_file() and p.suffix.lower() in SUFFIXES and not any(
                part in SKIP_DIRS for part in p.parts
            ):
                files.append(p)

    imports: dict[str, set[str]] = {}
    network: dict[str, list[int]] = {}
    token_hits: dict[str, list[int]] = {}

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = f.relative_to(OA).as_posix()
        if f.suffix == ".py":
            for m in IMPORT_RE.finditer(text):
                mod = m.group(1)
                if mod in UPSTREAM_NAMES:
                    imports.setdefault(mod, set()).add(rel)
        for i, line in enumerate(text.splitlines(), 1):
            if NET_RE.search(line):
                network.setdefault(rel, []).append(i)
            elif HERMES_TOKEN.search(line):
                token_hits.setdefault(rel, []).append(i)

    print("=" * 68)
    print("RESIDUAL UPSTREAM COUPLING (core tree)")
    print("=" * 68)
    print(f"files scanned: {len(files)}")

    print("\n[1] runtime imports of upstream module names")
    if imports:
        for mod, where in sorted(imports.items()):
            print(f"  {mod}: {len(where)} file(s)")
            for w in sorted(where)[:15]:
                print(f"      {w}")
    else:
        print("  NONE - no OpenAmer module imports an upstream module")

    print("\n[2] network / git references to the upstream repo")
    if network:
        for f, lines in sorted(network.items()):
            print(f"  {f}  (lines {lines[:8]})")
    else:
        print("  NONE")

    print(f"\n[3] residual 'hermes' token: {len(token_hits)} files")
    for f, lines in sorted(token_hits.items()):
        print(f"  {f}  x{len(lines)}  lines {lines[:8]}")

    out = OA / "reports" / "upstream-coupling-scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "scanned_files": len(files),
        "imports": {k: sorted(v) for k, v in imports.items()},
        "network": network,
        "token_files": {k: len(v) for k, v in token_hits.items()},
    }, indent=2), encoding="utf-8")
    print(f"\nreport written: {out}")


if __name__ == "__main__":
    main()
