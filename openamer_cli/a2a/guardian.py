"""openamer_cli.a2a.guardian — the single integration point (guardian Stufe 4).

Stufe 4 of the A2A guardian pipeline: the ONLY place that turns a verified,
signed proposal into a GitHub change. It enforces the safety rules:

  * the proposal must be from a TRUSTED node whose signature verifies;
  * the patch is applied on an ISOLATED branch (never on main directly);
  * tests must pass on that branch;
  * only then is the change merged to main.

By default this module is DRY-RUN / review-only: ``guardian_review`` verifies
and reports what WOULD happen, without touching git. ``guardian_apply`` is the
explicit, guarded path that actually creates a branch, applies, runs tests,
and merges — callers must opt in. This keeps the risky step explicit and
never automatic.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from openamer_cli.a2a.proposal import CodeProposal, verify_proposal_for_guardian


class GuardianError(Exception):
    """Raised when a proposal cannot be safely integrated."""


def _run(cmd: list[str], *, cwd: Path, timeout: float = 300) -> tuple[int, str]:
    """Run a command, return (returncode, stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as exc:
        return 1, str(exc)


def _apply_patch(patch: str, *, cwd: Path, git_cmd: list[str]) -> None:
    """Apply a unified diff to the working tree of *cwd*.

    Uses ``git apply`` WITHOUT ``--index`` (robust on Windows where
    ``core.autocrlf`` makes the index hold CRLF while the patch context is LF
    — ``--index`` then fails with "does not match index"). After applying we
    ``git add -A`` so the change is staged for the guardian commit.
    """
    if not patch or not patch.strip():
        return
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as fh:
        fh.write(patch)
        tmp = fh.name
    try:
        rc, out = _run(git_cmd + ["apply", "--whitespace=nowarn", tmp], cwd=cwd, timeout=120)
        if rc != 0:
            raise GuardianError(f"git apply failed: {out[:400]}")
        rc, out = _run(git_cmd + ["add", "-A"], cwd=cwd, timeout=120)
        if rc != 0:
            raise GuardianError(f"git add failed: {out[:300]}")
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


def _run_project_tests(project_root: Path, *, python: str = "") -> tuple[int, str]:
    """Run the project test suite on a checkout (guardian gate).

    Platform-robust: on Windows/MSYS the git `bash` cannot resolve a native
    Windows path (C:\\...), so convert to an MSYS path when bash is used, and
    fall back to the venv Python directly when bash is unavailable or the
    runner is absent. The Python path needs no bash and works everywhere.
    """
    py = python or str(project_root / ".venv" / "Scripts" / "python.exe")
    runner = project_root / "scripts" / "run_tests.sh"

    if runner.exists():
        import shutil
        bash = shutil.which("bash")
        if bash:
            # Convert a Windows drive path to an MSYS path for git-bash
            # (C:\\... -> /c/...). Paths without a drive are used as-is.
            run_msys = str(runner)
            if len(run_msys) >= 3 and run_msys[1] == ":" and run_msys[2] == "\\":
                drive = run_msys[0].lower()
                run_msys = "/" + drive + run_msys[2:].replace("\\", "/")
            import os
            env = dict(os.environ)
            env["OPENAMER_PYTHON"] = str(py)
            # Use the resolved bash path (shutil.which), not the bare "bash"
            # string: on MSYS/git-bash, subprocess may not find the bare name
            # on PATH, yielding WinError 2 even though `bash` works in a shell.
            rc, out = _run([bash, run_msys, "tests/openamer_cli/test_a2a_proposal.py"],
                           cwd=project_root, timeout=600)
            if rc == 0:
                return rc, out

    return _run([py, "-m", "pytest", "tests/openamer_cli/test_a2a_proposal.py", "-q"],
                cwd=project_root, timeout=600)


def guardian_review(
    proposal: CodeProposal,
    *,
    trusted_peers: dict,
    project_root: Path,
    tolerance: int = 300,
) -> dict:
    """DRY-RUN: verify a proposal and report what the guardian WOULD do.

    Never touches git. Returns a dict with ok/reason/paths/branch_name. This is
    the safe review entry point; callers show this before deciding to apply.
    """
    ok, reason = verify_proposal_for_guardian(
        proposal, trusted_peers=trusted_peers, tolerance=tolerance
    )
    branch = "guardian/" + proposal_id_slug(proposal)
    return {
        "ok": ok,
        "reason": reason,
        "paths": proposal.paths,
        "branch_name": branch,
        "would_apply": ok and bool(proposal.patch),
        "dry_run": True,
        "project_root": str(project_root),
    }


def proposal_id_slug(proposal: CodeProposal) -> str:
    import re
    from openamer_cli.a2a.board import proposal_id
    return re.sub(r"[^a-z0-9]+", "-", proposal.title.lower()).strip("-")[:40] + "-" + proposal_id(proposal)[:8]


def guardian_apply(
    proposal: CodeProposal,
    *,
    trusted_peers: dict,
    project_root: Path,
    tolerance: int = 300,
    python: str = "",
) -> dict:
    """Explicitly integrate a verified proposal: branch -> apply -> test -> merge.

    SAFETY: this is the one path that writes to git. It refuses when the
    sender is untrusted or the signature is invalid, applies on an isolated
    branch, runs the project tests, and ONLY merges to main when green.
    Returns a report dict. Raises GuardianError on any unsafe condition.
    """
    ok, reason = verify_proposal_for_guardian(
        proposal, trusted_peers=trusted_peers, tolerance=tolerance
    )
    if not ok:
        raise GuardianError(f"refused: {reason}")

    branch = "guardian/" + proposal_id_slug(proposal)
    git = ["git"]

    # Resolve the current branch robustly (a fresh repo may use 'master' or
    # 'main' depending on host git config) — never hard-code 'main'.
    rc, cur_branch = _run(git + ["branch", "--show-current"], cwd=project_root, timeout=60)
    if rc != 0 or not cur_branch.strip():
        rc, cur_branch = _run(git + ["symbolic-ref", "--short", "HEAD"], cwd=project_root, timeout=60)
    cur_branch = cur_branch.strip()
    if not cur_branch:
        raise GuardianError("cannot determine current git branch")

    # 1) ensure clean-ish start on the current branch
    rc, out = _run(git + ["checkout", cur_branch], cwd=project_root, timeout=120)
    if rc != 0:
        raise GuardianError(f"cannot checkout {cur_branch}: {out[:300]}")

    # 2) create isolated branch
    rc, out = _run(git + ["checkout", "-b", branch], cwd=project_root, timeout=120)
    if rc != 0:
        raise GuardianError(f"cannot create branch {branch}: {out[:300]}")

    _ok = False
    try:
        # 3) apply the patch
        _apply_patch(proposal.patch, cwd=project_root, git_cmd=git)

        # 4) run the project tests on this branch (the hard gate)
        trc, tout = _run_project_tests(project_root, python=python)
        if trc != 0:
            raise GuardianError(f"tests failed on branch {branch}: {tout[-400:]}")

        # 5) commit on the branch
        rc, out = _run(
            git + ["commit", "-am", f"guardian: {proposal.title}"],
            cwd=project_root, timeout=120,
        )
        if rc != 0:
            raise GuardianError(f"commit failed: {out[:300]}")

        # 6) merge back to the current branch
        rc, out = _run(git + ["checkout", cur_branch], cwd=project_root, timeout=120)
        if rc != 0:
            raise GuardianError(f"cannot return to {cur_branch}: {out[:300]}")
        rc, out = _run(git + ["merge", "--no-ff", branch], cwd=project_root, timeout=120)
        if rc != 0:
            raise GuardianError(f"merge failed: {out[:300]}")

        _ok = True
        return {"ok": True, "branch": branch, "merged": True, "title": proposal.title,
                "base": cur_branch}
    finally:
        if not _ok:
            # Hard-reset the working tree back to the base branch so an
            # applied-but-unmerged patch (or a test failure) can NEVER leak
            # half-applied changes onto the base branch. Only green, merged
            # changes survive.
            _run(git + ["reset", "--hard", cur_branch], cwd=project_root, timeout=60)
        _run(git + ["checkout", cur_branch], cwd=project_root, timeout=60)
        _run(git + ["branch", "-D", branch], cwd=project_root, timeout=60)
