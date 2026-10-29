"""Compile the OAC genesis contract with solc, if a compiler is available.

A rendered contract that was never compiled is unverified text: it can
look right in a diff and fail to build. This test compiles it for real
when a compiler is reachable, and skips -- loudly -- when it is not.

The compiler is resolved in this order:

  1. ``solc`` on PATH,
  2. the npm package ``solc`` (its ``solc.js`` entry point, run through
     node -- the ``.bin/solcjs`` shim is a shell script and cannot be
     spawned on Windows),
  3. ``npx solc@<version>`` (downloads on demand -- slow, so last).

Compilation goes through the standard-JSON interface, so the compiler's
verdict comes back as data: the ABI, the bytecode, and the warnings.

The npm install lives in ``%TEMP%``, outside the repo, so no build
artefact is ever committed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agent import oac_genesis  # noqa: E402

CONTRACT = REPO / "chain" / "contracts" / "OpenAmerGenesis.sol"


def _solc_command() -> list[str] | None:
    """The compiler command, resolved by the module both callers share."""
    return oac_genesis.solc_command()


def _compile(source: str) -> dict:
    """Compile the source via standard-JSON; return the compiler output.

    Raises AssertionError with the compiler's own diagnostics when the
    compilation fails.
    """
    cmd = _solc_command()
    assert cmd is not None, "no solc available"
    payload = {
        "language": "Solidity",
        "sources": {"OpenAmerGenesis.sol": {"content": source}},
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
    assert proc.returncode == 0, f"the compiler crashed:\n{proc.stderr}"
    # solc prefixes non-JSON diagnostics on stdout (e.g. "Cannot retry compilation
    # with SMT ..." when no solver is present); parse from the first brace.
    stdout = proc.stdout or ""
    brace = stdout.find("{")
    assert brace >= 0, f"compiler produced no JSON: {stdout[:200]!r}"
    out = json.loads(stdout[brace:])
    errors = [
        e for e in out.get("errors", []) if e.get("severity") == "error"
    ]
    assert not errors, "compilation failed:\n" + "\n".join(
        e.get("formattedMessage", str(e)) for e in errors
    )
    return out


def _contract(out: dict) -> dict:
    """The compiled OpenAmerGenesis contract artifact."""
    contracts = out.get("contracts", {})
    for sources in contracts.values():
        if "OpenAmerGenesis" in sources:
            return sources["OpenAmerGenesis"]
    raise AssertionError(
        f"the contract was not compiled; got {sorted(contracts)}"
    )


@pytest.mark.skipif(
    _solc_command() is None,
    reason="no Solidity compiler available (solc / npm solc / npx)",
)
def test_the_genesis_contract_compiles():
    """The generated contract must actually build.

    Compilation is the only honest check of a contract: everything else
    is a text comparison against expectations that could themselves be
    wrong.
    """
    out = _compile(oac_genesis.render_contract())
    artifact = _contract(out)
    assert artifact["evm"]["bytecode"]["object"], "the contract has no bytecode"
    assert artifact["abi"], "the contract has no ABI"


@pytest.mark.skipif(
    _solc_command() is None,
    reason="no Solidity compiler available (solc / npm solc / npx)",
)
def test_the_compiled_contract_has_no_warnings():
    """No warnings: a warning in a genesis contract is a defect."""
    out = _compile(oac_genesis.render_contract())
    warnings = [
        e for e in out.get("errors", []) if e.get("severity") == "warning"
    ]
    assert not warnings, "the contract compiles with warnings:\n" + "\n".join(
        e.get("formattedMessage", str(e)) for e in warnings
    )


@pytest.mark.skipif(
    _solc_command() is None,
    reason="no Solidity compiler available (solc / npm solc / npx)",
)
def test_the_committed_contract_compiles():
    """The file in the repo must compile, not just the rendered source."""
    out = _compile(CONTRACT.read_text(encoding="utf-8"))
    assert _contract(out)["evm"]["bytecode"]["object"]


@pytest.mark.skipif(
    _solc_command() is None,
    reason="no Solidity compiler available (solc / npm solc / npx)",
)
def test_the_compiled_abi_exposes_the_allocation_and_the_schedule():
    """The compiled ABI must expose the plan -- read-only.

    The constants and the two view functions are what a chain, a wallet
    or the Explorer (DIR-24) would read. A missing entry means the
    allocation is not observable.
    """
    out = _compile(oac_genesis.render_contract())
    abi = _contract(out)["abi"]
    names = {
        item.get("name")
        for item in abi
        if item.get("type") == "function"
    }
    for expected in (
        "allocations",
        "emissionSchedule",
        "MAX_SUPPLY",
        "TOTAL_SUPPLY",
        "MINING_POOL_ALLOCATION",
        "TREASURY_ALLOCATION",
        "CREATOR_ALLOCATION",
        "EMISSION_YEARS",
        "HALVING_CYCLES",
        "HALVING_YEARS",
    ):
        assert expected in names, f"the ABI is missing {expected}"

    # And no mutator: the allocation must be observable, not settable.
    for forbidden in ("setAllocation", "updateAllocation", "mint", "burn"):
        assert forbidden not in names, f"the ABI exposes a mutator: {forbidden}"

    # The view functions must be pure.
    for item in abi:
        if item.get("name") in ("allocations", "emissionSchedule"):
            assert item.get("stateMutability") == "pure", (
                f"{item['name']} must be a pure view function"
            )
