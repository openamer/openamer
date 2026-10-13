"""install.ps1 must resolve its home from evidence and persist only proof.

Root cause of the "empty desktop config after a reboot or an update" report:

    # scripts/install.ps1 (before this change)
    $currentOpenAmerHome = [Environment]::GetEnvironmentVariable("OPENAMER_HOME", "User")
    if (-not $currentOpenAmerHome -or $currentOpenAmerHome -ne $OpenAmerHome) {
        [Environment]::SetEnvironmentVariable("OPENAMER_HOME", $OpenAmerHome, "User")
    }

``$OpenAmerHome`` defaulted to ``$env:LOCALAPPDATA\\openamer`` whenever
``OPENAMER_HOME`` was missing from the process, so a single update -- or a reboot
with the variable unset -- pinned the *user* environment to a guessed home that
had nothing to do with the install being updated. Every later process, including
the desktop app's backend, inherited that spelling and came up on an empty home
(a ~51-byte onboarding stub instead of the real config).

Two layers are pinned here, because either alone would be a false comfort:

* Source-level contract (runs everywhere, including Linux CI, which cannot
  execute the installer): the ladder order, and that the persist call is gated on
  proof rather than on ``$OpenAmerHome`` differing from the stored value.
* Behavioral (runs wherever PowerShell exists): the resolution block is
  extracted verbatim from the real ``install.ps1`` and driven against real
  temporary layouts, so the precedence is measured rather than described.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"

BEGIN_MARKER = "# BEGIN install-home-resolution"
END_MARKER = "# END install-home-resolution"

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _install_ps1_text() -> str:
    return INSTALL_PS1.read_text(encoding="utf-8")


def _resolution_block() -> str:
    """The install-home-resolution block, exactly as shipped."""
    lines = _install_ps1_text().splitlines()
    begin = next((i for i, line in enumerate(lines) if BEGIN_MARKER in line), None)
    end = next((i for i, line in enumerate(lines) if END_MARKER in line), None)

    assert begin is not None, f"{BEGIN_MARKER} missing from scripts/install.ps1"
    assert end is not None and end > begin, f"{END_MARKER} missing from scripts/install.ps1"

    return "\n".join(lines[begin + 1 : end])


def _set_path_variable_body() -> str:
    text = _install_ps1_text()
    start = text.index("function Set-PathVariable {")
    end = text.index("function Write-BootstrapMarker", start)

    return text[start:end]


# ---------------------------------------------------------------------------
# Source-level contract
# ---------------------------------------------------------------------------


def test_resolution_ladder_is_ordered_evidence_first() -> None:
    """The documented order, asserted against the real block, rung by rung."""
    block = _resolution_block()

    explicit = block.index("if ($RequestedExplicit) {")
    breadcrumb = block.index("$fromMarker = Get-InstallBreadcrumbHome $c")
    shipped = block.index("$fromLayout = Get-ShippedLayoutHome $c")
    env = block.index("if ($env:OPENAMER_HOME) {")
    default = block.index("Home   = (Get-PlatformDefaultOpenAmerHome)")

    assert explicit < breadcrumb < shipped < env < default, (
        "install.ps1 must resolve -OpenAmerHome -> breadcrumb -> shipped layout "
        "-> env -> platform default"
    )

    # The platform default is the last rung and is never 'Proven'.
    tail = block[default:]
    assert "Proven = $false" in tail


def test_breadcrumb_home_is_marked_proven_and_the_default_is_not() -> None:
    block = _resolution_block()

    assert re.search(r'Source = "breadcrumb" \}', block)
    assert re.search(r'Source = "shipped-layout" \}', block)


def test_persist_is_gated_on_proof_not_on_a_difference() -> None:
    """The exact regression: persist was reached whenever the stored value differed."""
    body = _set_path_variable_body()

    assert 'if (-not $currentOpenAmerHome -or $currentOpenAmerHome -ne $OpenAmerHome)' not in body, (
        "the unconditional persist of $OpenAmerHome is what pinned the wrong home "
        "to the user environment (#45300); it must be gated on a proven home"
    )

    persist_call = body.index('[Environment]::SetEnvironmentVariable("OPENAMER_HOME"')
    prefix = body[:persist_call]

    assert "$currentOpenAmerHome -eq $resolvedHome" in prefix, (
        "an already-correct user-level value must never be overwritten"
    )
    assert "elseif (-not $resolution.Proven)" in prefix, (
        "a home that cannot be proven to belong to this install must be logged, "
        "not persisted"
    )

    # The persist call must sit in the branch reached only after the
    # corrected/!proven checks -- i.e. a home this install proved is its own.
    chain = prefix[prefix.rindex("if ($currentOpenAmerHome -eq $resolvedHome)") :]

    assert chain.index("elseif (-not $resolution.Proven)") < chain.rindex("} else {"), (
        "the persist call must be in the proven branch, after the unproven one"
    )


def test_breadcrumb_write_is_wired_and_only_for_proven_homes() -> None:
    body = _set_path_variable_body()

    assert "Set-InstallHomeBreadcrumb" in body
    assert re.search(r"if \(\$resolution\.Proven -and \(Test-Path \$InstallDir\)\)", body), (
        "the breadcrumb must only be written for a home this install can prove"
    )


def test_initialize_runs_before_every_entry_mode() -> None:
    text = _install_ps1_text()
    dispatch = text.index("Initialize-OpenAmerHome `")

    for mode in ('if ($Ensure -ne "")', "if ($ProtocolVersion)", "if ($Manifest)", "    Main\n}"):
        assert dispatch < text.index(mode), "the home must be resolved before any mode runs"


def test_breadcrumb_is_gitignored() -> None:
    """A file dropped next to a managed checkout must not dirty it (#38529)."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert re.search(r"^\.openamer-home$", gitignore, re.M), (
        ".openamer-home would be swept into `openamer update`'s untracked "
        "autostash and keep `git status` dirty in every managed checkout"
    )


# ---------------------------------------------------------------------------
# Behavioral: the real block, driven under PowerShell
# ---------------------------------------------------------------------------

pytestmark_ps = pytest.mark.skipif(
    POWERSHELL is None, reason="PowerShell is required to execute the installer's resolution block"
)


def _run_block(tmp_path: Path, harness: str, env_extra: dict[str, str]) -> dict:
    """Extract the shipped resolution block, run ``harness`` against it, return JSON."""
    script = tmp_path / "resolution_probe.ps1"
    script.write_text(
        "function Write-Info { param([string]$Message) Write-Host \"-> $Message\" }\n"
        "function Write-Warn { param([string]$Message) Write-Host \"[!] $Message\" }\n"
        + _resolution_block()
        + "\n"
        + harness,
        encoding="utf-8",
    )

    import os

    env = {k: v for k, v in os.environ.items() if k != "OPENAMER_HOME"}
    env.update(env_extra)

    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        text=True,
        # Windows PowerShell writes its own errors in the ANSI code page.
        errors="replace",
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, f"PowerShell failed: {result.stdout}\n{result.stderr}"

    return json.loads(result.stdout.strip().splitlines()[-1])


def _resolve_harness(checkout: Path) -> str:
    quoted = str(checkout).replace("'", "''")

    return (
        f"$r = Resolve-OpenAmerHome -Checkouts @('{quoted}')\n"
        "@{ home = [string]$r.Home; proven = [bool]$r.Proven; source = [string]$r.Source }"
        " | ConvertTo-Json -Compress\n"
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_block_resolves_breadcrumb_over_platform_default(tmp_path) -> None:
    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".openamer-home").write_text(str(home), encoding="utf-8")

    out = _run_block(
        tmp_path,
        _resolve_harness(checkout),
        {"LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path)},
    )

    assert out["home"] == str(home)
    assert out["proven"] is True
    assert out["source"] == "breadcrumb"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_block_derives_the_shipped_layout(tmp_path) -> None:
    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)

    out = _run_block(
        tmp_path,
        _resolve_harness(checkout),
        {"LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path)},
    )

    assert out["home"] == str(home)
    assert out["proven"] is True
    assert out["source"] == "shipped-layout"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_block_without_evidence_is_unproven_and_uses_the_platform_default(tmp_path) -> None:
    """No evidence: usable for this run, never persisted (Proven = false)."""
    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)
    local = tmp_path / "LocalAppData"

    out = _run_block(
        tmp_path,
        _resolve_harness(checkout),
        {"LOCALAPPDATA": str(local), "USERPROFILE": str(tmp_path)},
    )

    assert out["home"] == str(local / "openamer")
    assert out["proven"] is False
    assert out["source"] == "platform-default"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_block_treats_an_inherited_env_value_as_unproven(tmp_path) -> None:
    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)

    out = _run_block(
        tmp_path,
        _resolve_harness(checkout),
        {
            "LOCALAPPDATA": str(tmp_path / "LocalAppData"),
            "USERPROFILE": str(tmp_path),
            "OPENAMER_HOME": str(tmp_path / "other-tree"),
        },
    )

    assert out["home"] == str(tmp_path / "other-tree")
    assert out["proven"] is False
    assert out["source"] == "env"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_block_honours_an_explicit_home(tmp_path) -> None:
    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)
    explicit = tmp_path / "chosen-home"

    harness = (
        f"$r = Resolve-OpenAmerHome -Requested '{explicit}' -RequestedExplicit "
        f"-Checkouts @('{checkout}')\n"
        "@{ home = [string]$r.Home; proven = [bool]$r.Proven; source = [string]$r.Source }"
        " | ConvertTo-Json -Compress\n"
    )

    out = _run_block(
        tmp_path,
        harness,
        {"LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path)},
    )

    assert out["home"] == str(explicit)
    assert out["proven"] is True
    assert out["source"] == "explicit"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_initialize_keeps_the_checkout_under_the_resolved_home(tmp_path) -> None:
    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)

    harness = (
        "$OpenAmerHome = ''\n"
        f"$InstallDir = '{checkout}'\n"
        "Initialize-OpenAmerHome -RequestedExplicit:$false -InstallDirExplicit:$false\n"
        "@{ home = [string]$OpenAmerHome; installDir = [string]$InstallDir;"
        " proven = [bool]$script:OpenAmerHomeProven } | ConvertTo-Json -Compress\n"
    )

    out = _run_block(
        tmp_path,
        harness,
        {"LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path)},
    )

    assert out["home"] == str(home)
    assert out["installDir"] == str(checkout)
    assert out["proven"] is True


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell required")
def test_written_breadcrumb_round_trips_bom_less(tmp_path) -> None:
    """PowerShell writes it, Python reads it: the byte shape must not drift."""
    checkout = tmp_path / "openamer-laptop" / "openamer-agent"
    checkout.mkdir(parents=True)
    home = tmp_path / "openamer-laptop"

    harness = (
        f"$ok = Set-InstallHomeBreadcrumb -Checkout '{checkout}' -HomePath '{home}'\n"
        "@{ ok = [bool]$ok } | ConvertTo-Json -Compress\n"
    )

    out = _run_block(
        tmp_path,
        harness,
        {"LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path)},
    )

    assert out["ok"] is True

    marker = checkout / ".openamer-home"
    raw = marker.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf"), "a BOM would be read as part of the path"
    assert marker.read_text(encoding="utf-8-sig").strip() == str(home)

    # And the Python resolver reads back exactly what PowerShell wrote.
    from openamer_constants import get_install_scoped_openamer_home

    assert get_install_scoped_openamer_home(checkout) == str(home)
