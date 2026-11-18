"""Exercise verdict persistence through the real wrapper in a miniature checkout.

The miniature full suite is a synthetic regression fixture, never evidence for
this repository's full suite or the reference installation's DIR-05 anchor.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("run_tests.sh", "run_tests_parallel.py", "pytest_live_guard.py"):
        shutil.copyfile(REPO_ROOT / "scripts" / name, scripts / name)
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_sample.py").write_text(
        "import os\n\ndef test_sample():\n"
        "    assert 'OPENAI_API_KEY' not in os.environ\n", encoding="utf-8"
    )
    return root


def run_wrapper(checkout, tmp_path, *args, set_home=True):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("The canonical wrapper requires bash")
    home = tmp_path / "isolated home"
    # Keep the negative control safe even before OPENAMER_HOME forwarding works:
    # the old fallback must resolve under this synthetic user, not the host.
    user = tmp_path / "user"
    user.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(user), USERPROFILE=str(user),
               OPENAMER_HOME=str(home), OPENAMER_PYTHON=sys.executable,
               OPENAI_API_KEY="synthetic-credential-must-not-leak")
    if not set_home:
        env.pop("OPENAMER_HOME")
    result = subprocess.run(
        [bash, str(checkout / "scripts" / "run_tests.sh"), "-j", "1",
         "--file-retries", "0", *args],
        cwd=checkout, env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return home, result


def test_targeted_wrapper_preserves_full_verdict(checkout, tmp_path):
    home = tmp_path / "isolated home"
    canonical = home / "logs" / "suite-verdict.json"
    canonical.parent.mkdir(parents=True)
    # Explicitly synthetic: only the bytes-preservation contract is under test.
    canonical.write_text('{"scope":"full","fixture":true}', encoding="utf-8")
    before = hashlib.sha256(canonical.read_bytes()).hexdigest()
    _, result = run_wrapper(checkout, tmp_path, "tests/test_sample.py")
    targeted = home / "logs" / "suite-verdict-targeted.json"
    assert targeted.exists(), result.stdout
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == before
    record = json.loads(targeted.read_text(encoding="utf-8"))
    assert record["scope"] == "targeted"
    assert record["repo_root"] == str(checkout.resolve())
    assert record["revision"] is None  # This fixture has no git metadata.
    assert record["argv"][-1] == "tests/test_sample.py"
    assert record["home_resolution"] == "env"
    assert str(targeted) in result.stdout


def test_full_fixture_writes_canonical_with_git_provenance(checkout, tmp_path):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git provenance requires git")
    subprocess.run([git, "init", str(checkout)], check=True, capture_output=True)
    subprocess.run(
        [git, "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "Synthetic fixture"],
        cwd=checkout, check=True, capture_output=True,
    )
    revision = subprocess.check_output(
        [git, "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    home, _ = run_wrapper(checkout, tmp_path)
    record = json.loads((home / "logs" / "suite-verdict.json").read_text(encoding="utf-8"))
    assert record["scope"] == "full"
    assert record["repo_root"] == str(checkout.resolve())
    assert record["cwd"] == str(checkout.resolve())
    assert record["revision"] == revision
    assert record["argv"][1:] == ["-j", "1", "--file-retries", "0"]
    assert record["home_resolution"] == "env"
    assert record["passed"] == 1
    assert not (home / "logs" / "suite-verdict-targeted.json").exists()


@pytest.mark.parametrize("selection", [
    ["--paths", "tests/test_sample.py"],
    ["--files", "tests/test_sample.py"],
    ["--slice", "1/2"],
    ["-k", "sample"],
    ["--", "-k", "sample"],
])
def test_restricted_runs_never_write_canonical(checkout, tmp_path, selection):
    home, _ = run_wrapper(checkout, tmp_path, *selection)
    assert not (home / "logs" / "suite-verdict.json").exists()
    record = json.loads(
        (home / "logs" / "suite-verdict-targeted.json").read_text(encoding="utf-8")
    )
    assert record["scope"] == "targeted"


def test_unset_home_records_safe_fallback(checkout, tmp_path):
    _, _ = run_wrapper(checkout, tmp_path, "tests/test_sample.py", set_home=False)
    # No memory/ directory exists in the synthetic user's AppData candidates.
    record = json.loads(
        (checkout / "logs" / "suite-verdict-targeted.json").read_text(encoding="utf-8")
    )
    assert record["home_resolution"] == f"fallback:{checkout.resolve()}"


def test_per_test_home_remains_isolated(tmp_path):
    # The repository autouse fixture must still override the runner's home.
    assert Path(os.environ["OPENAMER_HOME"]) == tmp_path / "openamer_test"
    assert "OPENAI_API_KEY" not in os.environ
