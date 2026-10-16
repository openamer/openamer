"""Regression test: ``darwin_publish`` must locate its own repo, not one machine's.

Bug: the module root was a literal Windows path::

    REPO = Path(r"C:\\Users\\damir\\openamer-repo")

Everything derived from it -- ``reports/darwin-autopatch.json``,
``reports/trend-scout-latest.md``, ``website/static/darwin/darwin-status.json``
and ``scripts/darwin_engine.py`` -- therefore pointed at one developer's
checkout. On any other checkout (another user, a CI runner, a second clone) the
paths either do not exist (the daily publish cannot read its inputs) or, when a
same-named directory does exist, a *foreign* tree gets published from.

The subject is intentionally probed in a subprocess: ``darwin_publish`` resolves
its home and its validator log at import time, and the second half of this test
deliberately runs the script from a location that is not this repo. Importing it
in-process would test the ambient machine instead of the fix.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUBLISH = REPO / "scripts" / "darwin_publish.py"

#: Print the module's own idea of the repo root.
_PROBE = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('dp_repo_probe', sys.argv[1])\n"
    "mod = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(mod)\n"
    "print(mod.REPO)\n"
)


def _install(root: Path) -> Path:
    """Shape ``root`` as a home the import-time validator-log lookup can resolve.

    The lookup runs at import, so without it the probe would fail for a reason
    that has nothing to do with ``REPO`` (see
    ``tests/test_darwin_publish_home.py`` for that contract).
    """
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    (root / "config.yaml").write_text("x\n", encoding="utf-8")
    (root / "logs" / "skill-validator-latest.json").write_text(
        '{"skill_results": []}', encoding="utf-8")
    return root


def _repo_as_seen_by(script: Path, home: Path) -> Path:
    """Run ``script`` and return the repo root it resolved."""
    env = dict(os.environ, OPENAMER_HOME=str(home))
    out = subprocess.run([sys.executable, "-c", _PROBE, str(script)],
                         capture_output=True, text=True, env=env, timeout=120)
    assert out.returncode == 0, (
        f"probing {script} failed:\n{out.stdout}\n{out.stderr}")
    return Path(out.stdout.strip())


def test_repo_root_is_derived_from_the_script_location(tmp_path):
    """The shipped script resolves to the checkout it lives in."""
    seen = _repo_as_seen_by(PUBLISH, _install(tmp_path / "home"))

    assert seen == REPO, (
        f"darwin_publish resolved REPO={seen}, but the script lives in {REPO}")
    # Invariant, not a literal: the script sits in <repo>/scripts/.
    assert seen == PUBLISH.resolve().parents[1]


def test_a_foreign_checkout_resolves_to_itself(tmp_path):
    """A copy of the script elsewhere must not report THIS repo.

    This is the shape that breaks for every other user: with a hardcoded path
    the copy still claims ``C:\\Users\\damir\\openamer-repo`` and publishes that
    tree's numbers, or dies on paths that do not exist there.
    """
    other = tmp_path / "someone-elses-checkout"
    (other / "scripts").mkdir(parents=True)
    copy = other / "scripts" / "darwin_publish.py"
    copy.write_bytes(PUBLISH.read_bytes())

    seen = _repo_as_seen_by(copy, _install(tmp_path / "home"))

    assert seen == other, f"foreign checkout reported REPO={seen}, not {other}"
    assert seen != REPO, "a copy outside this repo resolved back to this repo"