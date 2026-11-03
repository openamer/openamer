"""The EXTRACTED workspace resolver must work against a real git repo.

``openamer_cli.kanban_db`` was split into ``kanban_db`` + ``kanban_db_workspace``
+ ``kanban_db_dispatch``, and ``kanban_db_workspace`` reaches origin-resident
helpers late-bound through ``_kb`` (a bottom-of-file ``import kanban_db as _kb``
that breaks the import cycle). During that split the module was rewritten to
call ``_kb._git_out(...)`` — a helper that was never hoisted into
``kanban_db``. Result: every real dispatch died with

    workspace: module 'openamer_cli.kanban_db' has no attribute '_git_out'

while CI stayed green, because the tests only ever exercised the *duplicate*
``_resolve_worktree_workspace`` / ``_git_toplevel`` copies that stayed behind in
``kanban_db`` (they call ``subprocess`` directly and were unaffected).

These tests therefore drive ``kanban_db_workspace`` itself — the module the
dispatcher actually spawns through — against real, disposable git repos, and
one of them resolves in a fresh interpreter so an in-process monkeypatch or
leaked module state can never make the suite lie again.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from openamer_cli import kanban_db as kb
from openamer_cli import kanban_db_workspace as kbw
from openamer_cli import kanban_db_dispatch as kbd

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated OPENAMER_HOME with an empty kanban DB."""
    home = tmp_path / ".openamer"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git", "-C", str(cwd),
            "-c", "user.name=Test User",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True, capture_output=True, text=True,
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    return repo


def _task(tid: str):
    with kb.connect() as conn:
        return kb.get_task(conn, tid)


def _create(**kwargs) -> str:
    with kb.connect() as conn:
        return kb.create_task(conn, **kwargs)


# ---------------------------------------------------------------------------
# The helper that went missing in the split
# ---------------------------------------------------------------------------

def test_git_out_is_resident_in_kanban_db():
    """``kanban_db_workspace`` needs it late-bound; the attribute must exist."""
    assert callable(getattr(kb, "_git_out", None)), (
        "kanban_db._git_out is the late-bound helper kanban_db_workspace "
        "resolves through _kb; its absence breaks every worktree dispatch"
    )


def test_git_out_returns_stdout_inside_a_repo(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    out = kb._git_out(repo, "rev-parse", "--show-toplevel")
    assert out is not None
    assert Path(out).resolve() == repo.resolve()


def test_git_out_returns_none_outside_a_repo(kanban_home, tmp_path):
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    assert kb._git_out(outside, "rev-parse", "--show-toplevel") is None


def test_git_out_returns_none_for_failing_command(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    # show-ref on a branch that does not exist exits non-zero.
    assert kb._git_out(repo, "show-ref", "--verify", "refs/heads/nope") is None


def test_git_out_returns_none_for_detached_head(kanban_home, tmp_path):
    """``branch --show-current`` prints nothing on a detached HEAD."""
    repo = _make_repo(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--detach", sha)
    assert kb._git_out(repo, "branch", "--show-current") is None


def test_extracted_helpers_answer_on_a_real_repo(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    assert kbw._git_toplevel(repo) == repo.resolve()
    assert kbw._git_current_branch(repo) == "main"
    assert kbw._git_common_dir(repo) == (repo / ".git").resolve()
    assert kbw._git_dir(repo) == (repo / ".git").resolve()


# ---------------------------------------------------------------------------
# real worktree materialization through the extracted module
# ---------------------------------------------------------------------------

def test_extracted_module_creates_worktree_from_repo_root_anchor(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    tid = _create(title="anchored worktree", workspace_kind="worktree",
                  workspace_path=str(repo))

    workspace, branch = kbw._resolve_worktree_workspace(_task(tid))

    assert workspace == (repo / ".worktrees" / tid).resolve()
    assert branch == f"wt/{tid}"
    # A real linked checkout, not an empty directory.
    assert (workspace / "README.md").read_text(encoding="utf-8") == "base\n"
    assert _git(workspace, "rev-parse", "--abbrev-ref", "HEAD") == f"wt/{tid}"
    registered = {
        Path(line.split(" ", 1)[1]).resolve(strict=False)
        for line in _git(repo, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    }
    assert workspace in registered


def test_extracted_module_reuses_its_own_worktree(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    tid = _create(title="returning task", workspace_kind="worktree",
                  workspace_path=str(repo))

    first, branch = kbw._resolve_worktree_workspace(_task(tid))
    # Second dispatch of the same card must land on the same checkout instead
    # of failing with "already registered worktree".
    second, branch2 = kbw._resolve_worktree_workspace(_task(tid))

    assert first == second
    assert branch == branch2 == f"wt/{tid}"


def test_extracted_module_falls_back_when_path_is_another_tasks_checkout(
    kanban_home, tmp_path
):
    """Decompose children inherit the root's literal path — never share it."""
    repo = _make_repo(tmp_path)
    _git(repo, "worktree", "add", str(repo / ".worktrees" / "sibling"),
         "-b", "wt/sibling", "HEAD")
    occupied = repo / ".worktrees" / "sibling"

    tid = _create(title="second sibling", workspace_kind="worktree",
                  workspace_path=str(occupied))

    workspace, branch = kbw._resolve_worktree_workspace(_task(tid))

    assert workspace == (repo / ".worktrees" / tid).resolve()
    assert branch == f"wt/{tid}"
    # The sibling is untouched and still on its own branch.
    assert _git(occupied, "rev-parse", "--abbrev-ref", "HEAD") == "wt/sibling"


def test_extracted_module_dir_workspace_fallback(kanban_home, tmp_path):
    target = tmp_path / "plain-dir" / "nested"
    tid = _create(title="dir task", workspace_kind="dir", workspace_path=str(target))

    resolved = kbw.resolve_workspace(_task(tid))

    assert Path(resolved) == target
    assert target.is_dir()


def test_extracted_module_rejects_non_repo_worktree_path(kanban_home, tmp_path):
    outside = tmp_path / "no-repo" / "here"
    tid = _create(title="bad path", workspace_kind="worktree",
                  workspace_path=str(outside))
    with pytest.raises(ValueError, match="not inside a git repo"):
        kbw.resolve_workspace(_task(tid))


# ---------------------------------------------------------------------------
# the duplicate copies must not drift from the extracted module again
# ---------------------------------------------------------------------------

def test_duplicate_and_extracted_resolvers_agree(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    tid = _create(title="agreement", workspace_kind="worktree",
                  workspace_path=str(repo))
    task = _task(tid)

    extracted = kbw._resolve_worktree_workspace(task)
    duplicate = kb._resolve_worktree_workspace(task)

    assert extracted == duplicate


# ---------------------------------------------------------------------------
# separate process: no monkeypatch, no leaked module state
# ---------------------------------------------------------------------------

_SEPARATE_PROCESS_SNIPPET = """
import json, sys
from pathlib import Path
import openamer_cli.kanban_db_workspace as kbw
import openamer_cli.kanban_db as kb
repo = Path(sys.argv[1])
tid = sys.argv[2]
with kb.connect() as conn:
    task = kb.get_task(conn, tid)
workspace, branch = kbw._resolve_worktree_workspace(task)
print(json.dumps({
    "module_file": kbw.__file__,
    "git_out": callable(getattr(kb, "_git_out", None)),
    "workspace": str(workspace),
    "branch": branch,
    "has_readme": (workspace / "README.md").exists(),
}))
"""


def test_extracted_module_resolves_in_a_separate_process(kanban_home, tmp_path):
    repo = _make_repo(tmp_path)
    tid = _create(title="subprocess dispatch", workspace_kind="worktree",
                  workspace_path=str(repo))

    env = dict(os.environ)
    env["OPENAMER_HOME"] = str(kanban_home)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(PROJECT_ROOT), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
    )
    env.pop("OPENAMER_KANBAN_BOARD", None)
    proc = subprocess.run(
        [sys.executable, "-c", _SEPARATE_PROCESS_SNIPPET, str(repo), tid],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr

    import json

    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["git_out"] is True
    # The child must import THIS checkout, not an installed copy of OpenAmer.
    assert Path(payload["module_file"]).resolve().is_relative_to(
        PROJECT_ROOT.resolve()
    )
    assert Path(payload["workspace"]) == repo / ".worktrees" / tid
    assert payload["branch"] == f"wt/{tid}"
    assert payload["has_readme"] is True


# ---------------------------------------------------------------------------
# the live dispatch entry point, end to end, with no spawn side effects
# ---------------------------------------------------------------------------

def test_dispatch_loop_workspace_step_uses_extracted_module(kanban_home, tmp_path):
    """``_worker_argv`` + workspace resolution are the two steps that used to
    blow up before a worker could ever start. Drive both on a real repo."""
    repo = _make_repo(tmp_path)
    tid = _create(title="dispatchable", workspace_kind="worktree",
                  workspace_path=str(repo), assignee="dev")

    task = _task(tid)
    workspace, branch = kbw._resolve_worktree_workspace(task)
    argv = kbd._worker_argv(task, "dev", None)

    assert (Path(workspace) / ".git").exists()
    assert branch == f"wt/{tid}"
    assert "chat" in argv and f"work kanban task {tid}" in argv
    # No reasoning override on this card -> the flag is not emitted at all.
    assert "--reasoning" not in argv
