"""Regression: install.ps1 must syntax-check the dashboard backend source.

Issue #59004 reported a fresh Windows desktop install crashing on launch
because ``openamer_cli/web_server.py`` inside the installed checkout still
contained merge-conflict markers. Import-only dependency probes (fastapi /
uvicorn) do not catch that: the packages can be present while the backend
source itself is unparsable.

This test is source-level because Linux CI cannot execute the PowerShell
installer. It locks the contract that install.ps1 runs ``py_compile`` against
``openamer_cli/web_server.py`` and fails the stage when that syntax probe fails.

It also locks the follow-up behavior (commit ``7ead2f73d``): the probe must
*surface* the SyntaxError and recover a locally-broken copy instead of dying
with a bare "failed syntax check". Before that commit, ``py_compile`` was piped
to ``Out-Null``, so the user got no line number and no pointer to the culprit --
and the usual culprit is their own autostashed local edit, which made a
first-time install read as "OpenAmer is broken".
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"


def test_install_ps1_compiles_web_server_source_after_web_deps_probe() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")

    probe = re.search(
        r"import fastapi, uvicorn[\s\S]{0,1200}?-m py_compile \$webServerPath",
        text,
    )
    assert probe is not None, (
        "install.ps1 must syntax-check openamer_cli/web_server.py after the "
        "dashboard dependency probe so a fresh desktop install fails early on "
        "merge-conflict markers or other SyntaxErrors."
    )


def test_install_ps1_fails_stage_when_web_server_syntax_probe_fails() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")

    assert "if ($LASTEXITCODE -eq 0) { $webServerSyntaxOk = $true }" in text
    assert "if (-not $webServerSyntaxOk) {" in text
    assert (
        "dashboard backend source failed syntax check: "
        "openamer_cli/web_server.py (see the SyntaxError above)" in text
    ), (
        "install.ps1 must fail the install stage when openamer_cli/web_server.py "
        "does not compile, instead of writing a broken desktop/backend install."
    )


def test_install_ps1_surfaces_the_syntax_error_instead_of_discarding_it() -> None:
    """The diagnostic output must be captured, not piped to Out-Null."""
    text = INSTALL_PS1.read_text(encoding="utf-8")

    # Capture the probe's output so it can be printed on failure.
    assert "= @(& $pythonExe -m py_compile $webServerPath 2>&1)" in text, (
        "the py_compile probe must capture stdout+stderr so the real "
        "SyntaxError can be reported on failure."
    )
    # And print it, line by line, before the stage fails.
    assert 'Write-Err "openamer_cli/web_server.py failed its Python syntax check:"' in text
    assert "foreach ($line in $webServerSyntaxErr)" in text


def test_install_ps1_recovers_a_locally_broken_web_server_copy() -> None:
    """A non-parsing *local edit* must be set aside, never discarded."""
    text = INSTALL_PS1.read_text(encoding="utf-8")

    assert "$webServerPath = \"$InstallDir\\openamer_cli\\web_server.py\"" in text
    # Detect the local modification, keep the user's file, restore pristine.
    assert "$serverLocallyModified = $true" in text
    assert '"$webServerPath.local-" + (Get-Date -Format "yyyyMMdd-HHmmss")' in text
    assert "Your version was kept at: $serverBackup" in text
    assert "git -c windows.appendAtomically=false checkout -- openamer_cli/web_server.py" in text
    # The pristine copy is then re-probed so the install can finish.
    assert "Pristine openamer_cli/web_server.py restored -- syntax check passes." in text


def test_install_ps1_safety_net_covers_every_locally_modified_python_file() -> None:
    """Commit 23cdfc725 generalized the net beyond web_server.py.

    The autostash replays *all* local edits, so any single non-parsing .py file
    was enough to kill the install with a misleading message.
    """
    text = INSTALL_PS1.read_text(encoding="utf-8")

    assert "git -c windows.appendAtomically=false diff --name-only HEAD" in text
    assert "locally modified Python file(s) for syntax errors" in text
    assert "compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" in text
    assert '"$localAbsPath.local-" + (Get-Date -Format "yyyyMMdd-HHmmss")' in text
    assert "Your version was kept at: $localBackup" in text
    assert "git -c windows.appendAtomically=false checkout -- $localRelPath" in text


def test_install_ps1_safety_net_runs_before_the_web_probe() -> None:
    """Ordering contract: set bad local edits aside *before* verifying sources.

    If the net ran after the web probe, a broken local edit would still fail the
    stage first -- which is the whole class of failure it exists to prevent.
    """
    text = INSTALL_PS1.read_text(encoding="utf-8")

    idx_net = text.index("Local-edit safety net")
    idx_web_probe = text.index("-m py_compile $webServerPath")
    assert idx_net < idx_web_probe
