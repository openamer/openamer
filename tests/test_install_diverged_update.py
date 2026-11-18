"""Regression: installer/bootstrap must recover from diverged managed clones.

When ``~/.openamer/openamer-agent`` has local-only commits (or diverged history),
``git pull --ff-only`` fails with exit 128 and bootstrap aborts at the
repository stage. ``openamer update`` already resets to ``origin/$BRANCH`` in
that case; both installer scripts must do the same.

Fixes the bootstrap failure seen in #53257 and desktop update paths that run
``install.ps1`` / ``install.sh`` non-interactively.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"


def _extract_install_sh_update_block() -> str:
    text = INSTALL_SH.read_text()
    match = re.search(
        r"(?P<block>git checkout \"\$BRANCH\".*?fi\n\n            if \[ -n \"\$autostash_ref\" \])",
        text,
        re.DOTALL,
    )
    assert match is not None, "managed-install update block not found in install.sh"
    return match["block"]


def _install_ps1_branch_update_tail() -> str:
    """The recovery tail after the ff-only pull, without pinning the checkout call.

    This used to slice from `checkout $Branch` up to `elseif ($Tag)` — which put
    the anchor *before* the block it described and broke the moment the checkout
    line changed (`checkout -B $Branch FETCH_HEAD`, PR #429). A test that fails
    when a sibling line is edited, while the behaviour it guards is intact, is a
    change detector. Anchor on the recovery sequence itself instead.
    """
    text = INSTALL_PS1.read_text()
    start = text.index("pull --ff-only origin $Branch")
    return text[start : start + 900]


def test_install_sh_resets_when_ff_only_pull_fails() -> None:
    block = _extract_install_sh_update_block()

    assert 'git pull --ff-only origin "$BRANCH"' in block
    assert 'git reset --hard "origin/$BRANCH"' in block
    assert "Fast-forward not possible" in block

    pull_idx = block.find('git pull --ff-only origin "$BRANCH"')
    reset_idx = block.find('git reset --hard "origin/$BRANCH"')
    assert pull_idx != -1 and reset_idx != -1
    assert pull_idx < reset_idx, "ff-only pull must be attempted before reset fallback"


def test_install_ps1_resets_when_ff_only_pull_fails() -> None:
    tail = _install_ps1_branch_update_tail()

    assert 'reset --hard "origin/$Branch"' in tail
    assert "Fast-forward not possible" in tail

    pull_idx = tail.find("pull --ff-only origin $Branch")
    reset_idx = tail.find('reset --hard "origin/$Branch"')
    assert pull_idx != -1 and reset_idx != -1
    assert pull_idx < reset_idx, "ff-only pull must be attempted before reset fallback"


def test_install_ps1_checks_out_what_it_fetched() -> None:
    """The fetch names a branch; the checkout must name the fetched commit.

    `git fetch origin <branch>` only writes FETCH_HEAD when no remote-tracking
    ref exists yet, so a bare `checkout <branch>` dies with "pathspec did not
    match" — the dead end that aborted the repository stage on 2026-11-18.
    """
    text = INSTALL_PS1.read_text()

    assert "checkout -B $Branch FETCH_HEAD" in text
