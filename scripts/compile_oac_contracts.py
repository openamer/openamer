"""Compile the whole OAC contract set with solc.

The genesis contract is generated from agent/tokenomics.py; the token,
the allocation, the vault and the clock are hand-written but state the
same numbers. This compiles them all and reports the compiler's
verdict, so a contract that does not build never ships.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agent import oac_genesis  # noqa: E402

CONTRACT_DIR = REPO_ROOT / "chain" / "contracts"

# The generated genesis contract plus the hand-written ones.
CONTRACTS = [
    "OpenAmerGenesis.sol",
    "TokenAllocation.sol",
    "OAMER_Aeon.sol",
    "Timestamp.sol",
    "TokenVault.sol",
]


def main() -> int:
    cmd = oac_genesis.solc_command()
    if cmd is None:
        print(
            "no Solidity compiler found (solc, npm solc, or npx)",
            file=sys.stderr,
        )
        return 2

    sources = {}
    for name in CONTRACTS:
        path = CONTRACT_DIR / name
        if not path.exists():
            print(f"missing contract: {path}", file=sys.stderr)
            return 1
        sources[name] = {"content": path.read_text(encoding="utf-8")}

    payload = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "outputSelection": {
                "*": {"*": ["abi", "evm.bytecode.object"]},
            },
        },
    }
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return 1

    # solc writes non-JSON diagnostics to stdout before the document -- on Linux
    # with no SMT solver it prints ">>> Cannot retry compilation with SMT ..."
    # first, which made json.loads fail on a perfectly good compile (CI, measured
    # 2026-10-25). Skip to the first brace.
    raw = proc.stdout or ""
    brace = raw.find("{")
    if brace < 0:
        print(f"compiler produced no JSON (stdout={raw[:200]!r})", file=sys.stderr)
        return 1
    out = json.loads(raw[brace:])
    errors = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    warnings = [
        e for e in out.get("errors", []) if e.get("severity") == "warning"
    ]
    for entry in errors + warnings:
        print(entry.get("formattedMessage", str(entry)), file=sys.stderr)
    if errors:
        return 1

    compiled = []
    for file_name, contracts in out.get("contracts", {}).items():
        for contract_name, artifact in contracts.items():
            bytecode = artifact.get("evm", {}).get("bytecode", {}).get("object", "")
            compiled.append((file_name, contract_name, len(bytecode) // 2))

    for file_name, contract_name, size in sorted(compiled):
        print(f"  {file_name}: {contract_name} -> {size} bytes of bytecode")
    print(
        f"{len(compiled)} contract(s) compiled, 0 errors, {len(warnings)} warnings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
