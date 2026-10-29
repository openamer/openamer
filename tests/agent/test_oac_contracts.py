"""The OAC contract set must state the plan and must compile.

Five contracts:

  OpenAmerGenesis.sol  the generated genesis allocation
  TokenAllocation.sol  the allocation as a contract
  OAMER_Aeon.sol       the ERC-20 token with PoUW emission and the burn
  Timestamp.sol        the trustworthy on-chain clock
  TokenVault.sol       the creator's vesting and the sovereign treasury

The numbers in all of them come from the same plan (agent/tokenomics.py),
so the tests here check that they AGREE with the plan -- not that they
are individually plausible.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agent import oac_genesis, tokenomics as tok  # noqa: E402

CONTRACT_DIR = REPO / "chain" / "contracts"
CONTRACTS = [
    "OpenAmerGenesis.sol",
    "TokenAllocation.sol",
    "OAMER_Aeon.sol",
    "Timestamp.sol",
    "TokenVault.sol",
]


@pytest.fixture(scope="module")
def sources() -> dict[str, str]:
    """The contract sources, read once."""
    return {
        name: (CONTRACT_DIR / name).read_text(encoding="utf-8")
        for name in CONTRACTS
    }


# ── the numbers ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "contract",
    ["TokenAllocation.sol", "OAMER_Aeon.sol"],
)
def test_the_allocation_contracts_state_the_plan(sources, contract):
    """Both allocation contracts must quote the plan's numbers."""
    text = sources[contract]
    for a in tok.ALLOCATION:
        assert f"{a.amount}" in text, f"{contract} is missing {a.key} = {a.amount}"
    assert f"{tok.MAX_SUPPLY}" in text
    assert f"EMISSION_YEARS = {tok.EMISSION_YEARS}" in text
    assert f"HALVING_CYCLES = {tok.HALVING_CYCLES}" in text
    assert f"HALVING_YEARS = {tok.HALVING_YEARS}" in text


def test_the_vault_states_the_vesting_schedule(sources):
    """The vault must carry the 12-month cliff and the 36-month release."""
    text = sources["TokenVault.sol"]
    assert "CLIFF_MONTHS = 12" in text
    assert "VESTING_MONTHS = 36" in text
    assert f"CREATOR_ALLOCATION = {tok.share('creator').amount}" in text
    assert f"TREASURY_ALLOCATION = {tok.share('treasury').amount}" in text
    assert f"MINING_POOL_ALLOCATION = {tok.share('mining_pool').amount}" in text


def test_the_token_states_the_burn(sources):
    """The burn must be at least 30% (DIR-23)."""
    text = sources["OAMER_Aeon.sol"]
    assert "MIN_BURN_BPS = 3000" in text  # 30.00% in basis points


# ── the invariants the contracts enforce ────────────────────────────────

@pytest.mark.parametrize("contract", CONTRACTS)
def test_no_contract_has_a_mutating_admin(sources, contract):
    """DIR-20 excludes human or administrative influence.

    No owner, no admin, no mint authority, no upgrade path. A contract
    with any of those could change the emission, which is exactly what
    the directive forbids.
    """
    text = sources[contract]
    for forbidden in (
        "onlyOwner",
        "onlyAdmin",
        "Ownable",
        "AccessControl",
        "upgradeTo",
        "proxy",
        "_mint(",
        "setMintable",
    ):
        assert forbidden not in text, (
            f"{contract} must not contain {forbidden}"
        )


@pytest.mark.parametrize("contract", CONTRACTS)
def test_no_contract_is_selfdestructable(sources, contract):
    """A selfdestruct would let the contract destroy the allocation."""
    assert "selfdestruct" not in sources[contract]
    assert "delegatecall" not in sources[contract]


def test_the_token_is_the_only_place_with_a_mint(sources):
    """Only the token can create supply -- and only through mine()."""
    text = sources["OAMER_Aeon.sol"]
    assert "function mine(" in text
    # The emission is capped: the token cannot mint past the cap.
    assert "MAX_SUPPLY" in text
    assert "totalSupply + released > MAX_SUPPLY" in text


def test_the_vault_releases_only_to_the_creator(sources):
    """The creator's tranche goes to the creator, and only the creator
    may trigger it."""
    text = sources["TokenVault.sol"]
    assert "if (msg.sender != creator)" in text
    assert "IERC20(token).transfer(creator, released)" in text


def test_the_vault_releases_nothing_before_the_cliff(sources):
    """The cliff must be enforced, not merely documented."""
    text = sources["TokenVault.sol"]
    assert "revert CliffNotReached" in text
    assert "nowTs < cliff" in text


def test_the_clock_refuses_a_stale_timestamp(sources):
    """A replayed timestamp must not unlock a vesting tranche."""
    text = sources["Timestamp.sol"]
    assert "revert StaleTimestamp" in text
    assert "provided < highestTimestamp" in text


# ── they compile ────────────────────────────────────────────────────────

def test_the_contract_set_compiles():
    """All five contracts must build, without warnings.

    A warning in a genesis contract is a defect: a shadowed builtin, a
    mutable function that could be pure -- each of them a sign that
    something is not quite what the author meant.
    """
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "compile_oac_contracts.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=300,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "0 errors, 0 warnings" in proc.stdout, proc.stdout
    for name in ("OAMER_Aeon", "TokenAllocation", "Timestamp", "TokenVault"):
        assert name in proc.stdout, f"{name} was not compiled"


def test_the_generated_genesis_contract_is_current():
    """The generated contract must match the plan."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate_oac_genesis.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=120,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_the_abi_exposes_the_allocation_read_only():
    """The compiled ABI must expose the plan, and no mutator."""
    cmd = oac_genesis.solc_command()
    if cmd is None:
        pytest.skip("no Solidity compiler available")

    payload = {
        "language": "Solidity",
        "sources": {
            name: {"content": (CONTRACT_DIR / name).read_text(encoding="utf-8")}
            for name in CONTRACTS
        },
        "settings": {
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
        },
    }
    proc = subprocess.run(
        cmd, input=json.dumps(payload), capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    # solc prefixes non-JSON diagnostics on stdout (e.g. "Cannot retry
    # compilation with SMT ..." when no SMT solver is installed), so parse from
    # the first brace instead of char 0. Same fix as test_oac_genesis_compiles.py;
    # CI slice 3 caught this one after the other was fixed (2026-10-25).
    stdout = proc.stdout or ""
    brace = stdout.find("{")
    assert brace >= 0, f"compiler produced no JSON: {stdout[:200]!r}"
    out = json.loads(stdout[brace:])
    errors = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    assert not errors, errors

    compiled = out.get("contracts", {})
    aeon = compiled.get("OAMER_Aeon.sol", {}).get("OAMER_Aeon")
    assert aeon is not None, "OAMER_Aeon was not compiled"
    names = {
        item.get("name")
        for item in aeon["abi"]
        if item.get("type") == "function"
    }
    for expected in (
        "transfer",
        "approve",
        "transferFrom",
        "mine",
        "burn",
        "payForCloud",
        "balanceOf",
        "totalSupply",
    ):
        assert expected in names, f"the ABI is missing {expected}"
    for forbidden in ("mint", "setOwner", "upgrade"):
        assert forbidden not in names, f"the ABI exposes a mutator: {forbidden}"
