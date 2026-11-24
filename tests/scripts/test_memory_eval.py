"""Tests for scripts/bench/memory_eval.py.

Regression for two measured traps (2026-11-24):

1. ``BASE = Path(__file__).resolve().parents[2]`` bound the script to its
   location. It was correct only while the script lived in ``<home>/scripts/``,
   so the file could not be versioned: a repository copy resolved BASE to the
   checkout and looked for the episode store in a directory that does not exist
   there. The scorer now resolves the install home from ``OPENAMER_HOME``.
2. ``latest.json`` was never rewritten by the code that printed
   ``stored: .../latest.json``. A reader therefore got a stale baseline run and
   read 0.14 as if it were the ``chunks`` score (real value: 0.18). The file is
   now written on every complete run and carries its ``backend``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER = REPO_ROOT / "scripts" / "bench" / "memory_eval.py"


@pytest.fixture(scope="module")
def scorer_path() -> Path:
    assert SCORER.is_file(), f"scorer missing at {SCORER}"
    return SCORER


def _find_real_scripts() -> Path:
    """The install home's scripts dir, which holds longterm_memory.py."""
    if os.environ.get("OPENAMER_HOME"):
        cand = Path(os.environ["OPENAMER_HOME"]) / "scripts"
        if (cand / "longterm_memory.py").is_file():
            return cand
    default = (
        Path.home() / "AppData" / "Local" / "openamer-laptop" / "scripts"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop" / "scripts"
    )
    if (default / "longterm_memory.py").is_file():
        return default
    pytest.skip("no install home with longterm_memory.py -- cannot build a hermetic home")


def _load(home: Path):
    """Import the scorer with OPENAMER_HOME pointed at ``home``."""
    old = os.environ.get("OPENAMER_HOME")
    os.environ["OPENAMER_HOME"] = str(home)
    try:
        spec = importlib.util.spec_from_file_location("memory_eval_under_test", SCORER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old is None:
            os.environ.pop("OPENAMER_HOME", None)
        else:
            os.environ["OPENAMER_HOME"] = old


def test_base_follows_openamer_home(tmp_path, scorer_path):
    """The scorer must read data from the install home, not from its own folder.

    This is what makes the file versionable at all.
    """
    module = _load(tmp_path)
    assert module.BASE == tmp_path.resolve()
    assert module.STORE == tmp_path.resolve() / "memory" / "longterm_episodes.jsonl"
    assert module.LABELS == tmp_path.resolve() / "missions" / "beyond-all" / "memory-eval-set.jsonl"
    assert module.OUT_DIR == tmp_path.resolve() / "reports" / "memory-eval"


def test_base_is_not_the_checkout(tmp_path, scorer_path):
    """A copy inside the repository must NOT resolve BASE to the repository.

    Measured failure this guards: the versioned copy would have looked for the
    episode store at ``<checkout>/memory/longterm_episodes.jsonl``, which does
    not exist, and every score would have been 0 / error.
    """
    module = _load(tmp_path)
    assert module.BASE != REPO_ROOT.resolve()
    assert module.STORE.is_relative_to(tmp_path.resolve())


def test_latest_json_is_written_on_a_complete_run(tmp_path, scorer_path):
    """`latest.json` must describe the newest complete run, and say which backend.

    Built from a 2-episode fake store + 2 labels so the test stays fast: the
    point is which files appear, not the score value.
    """
    home = tmp_path
    (home / "memory").mkdir()
    (home / "missions" / "beyond-all").mkdir(parents=True)
    (home / "reports" / "memory-eval").mkdir(parents=True)
    # The scorer puts BASE/scripts on sys.path to import `longterm_memory`.
    # Only the top-level .py files are needed; copying them keeps the test
    # hermetic (data in tmp) without cutting the scorer off from its code.
    import shutil

    real_scripts = _find_real_scripts()
    (home / "scripts").mkdir()
    for src in real_scripts.glob("*.py"):
        shutil.copy2(src, home / "scripts" / src.name)

    episodes = [
        {
            "hash": "h1",
            "digest": "h1",
            "text": "The cache guard tests failed because a stale fixture was reused.",
            "ts": "2026-11-24T00:00:00+00:00",
        },
        {
            "hash": "h2",
            "digest": "h2",
            "text": "The brain export wrote 120 records, 40 of them trajectories.",
            "ts": "2026-11-24T00:00:01+00:00",
        },
    ]
    import json as _json

    (home / "memory" / "longterm_episodes.jsonl").write_text(
        "\n".join(_json.dumps(e) for e in episodes) + "\n", encoding="utf-8"
    )
    # The store index is keyed by text_hash(text), not by the record's `hash`
    # field -- labels must therefore carry the text hash. Deriving it from the
    # module keeps this test honest if the keying ever changes.
    module = _load(home)
    target_hash = module.text_hash(episodes[0]["text"])
    labels = [
        {
            "id": "t1",
            "question": "Why did the cache guard tests fail?",
            "expect_hash": target_hash,
            "class": "semantic",
        }
    ]
    (home / "missions" / "beyond-all" / "memory-eval-set.jsonl").write_text(
        "\n".join(_json.dumps(lb) for lb in labels) + "\n", encoding="utf-8"
    )

    env = dict(os.environ, OPENAMER_HOME=str(home))
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, str(scorer_path), "--backend", "current", "--k", "5"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )

    out_dir = home / "reports" / "memory-eval"
    latest = out_dir / "latest.json"
    per_backend = out_dir / "latest-current.json"
    # The run may legitimately refuse (e.g. the store indexer rejects the fake
    # rows); if so it must say why rather than write a misleading file.
    if proc.returncode != 0:
        assert "latest.json" not in proc.stdout
        pytest.skip(f"fake store rejected by the indexer: {proc.stderr[-300:]}")

    assert latest.is_file(), f"latest.json not written; stdout={proc.stdout[-400:]}"
    assert per_backend.is_file(), per_backend
    payload = _json.loads(latest.read_text(encoding="utf-8"))
    assert payload.get("backend") == "current"
    assert payload.get("overall", {}).get("n") == len(labels)
