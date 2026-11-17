"""Regression: daily-release.py must stamp *valid* versions.

The daily release previously wrote a bare compact date id (e.g. "260816",
without dots) into pyproject.toml, openamer_cli/__init__.py and
apps/desktop/package.json. That is NOT valid semver (electron-builder rejects
it with `Invalid version`) nor PEP-440. The fix must write punctuated CalVer
(YYYY.M.D) into every version field while keeping the compact vYYMMDD *tag*.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "daily-release.py"


def _load_dr():
    """Load scripts/daily-release.py by path (module name has a hyphen)."""
    spec = importlib.util.spec_from_file_location("daily_release", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def dr(monkeypatch, tmp_path):
    mod = _load_dr()
    # Redirect the three version files to a scratch tree.
    pkg = tmp_path / "openamer_cli"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '__version__ = "0.0.1"\n__release_date__ = "1970.01.01"\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.0.1"\n', encoding="utf-8"
    )
    desk = tmp_path / "apps" / "desktop"
    desk.mkdir(parents=True)
    (desk / "package.json").write_text(
        '{\n  "name": "openamer",\n  "version": "0.0.1"\n}\n', encoding="utf-8"
    )
    monkeypatch.setattr(mod, "VERSION_FILE", pkg / "__init__.py")
    monkeypatch.setattr(mod, "PYPROJECT_FILE", tmp_path / "pyproject.toml")
    monkeypatch.setattr(mod, "DESKTOP_PKG", desk / "package.json")
    return mod


def _stamp(dr, tmp_path):
    """Run the stamping and return the three file texts."""
    dr.update_version_files("260816", "2026.8.16")
    return {
        "init": (tmp_path / "openamer_cli" / "__init__.py").read_text(encoding="utf-8"),
        "pyproject": (tmp_path / "pyproject.toml").read_text(encoding="utf-8"),
        "desktop": (tmp_path / "apps" / "desktop" / "package.json").read_text(encoding="utf-8"),
    }


def test_version_files_get_valid_calver(dr, tmp_path):
    t = _stamp(dr, tmp_path)

    m = re.search(r'__version__\s*=\s*"([^"]+)"', t["init"])
    assert m and re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)), f"init version {m and m.group(1)!r}"

    m2 = re.search(r'^version\s*=\s*"([^"]+)"', t["pyproject"], re.MULTILINE)
    assert m2 and re.fullmatch(r"\d+\.\d+\.\d+", m2.group(1)), f"pyproject {m2 and m2.group(1)!r}"

    pkgdata = json.loads(t["desktop"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", pkgdata["version"]), f"desktop {pkgdata['version']!r}"
    assert pkgdata["version"] == "2026.8.16"


def test_all_three_versions_agree(dr, tmp_path):
    t = _stamp(dr, tmp_path)
    v_init = re.search(r'__version__\s*=\s*"([^"]+)"', t["init"]).group(1)
    v_py = re.search(r'^version\s*=\s*"([^"]+)"', t["pyproject"], re.MULTILINE).group(1)
    v_desktop = json.loads(t["desktop"])["version"]
    assert v_init == v_py == v_desktop == "2026.8.16"


def test_version_is_pep440_parseable(dr, tmp_path):
    import packaging.version as pv
    t = _stamp(dr, tmp_path)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', t["init"]).group(1)
    parsed = str(pv.Version(m))
    assert parsed == m, f"PEP-440 failed to round-trip {m!r} -> {parsed!r}"


def test_tag_stays_compact_but_version_is_dotted(dr):
    """The git tag keeps vYYMMDD; only the version fields become dotted."""
    tag = dr.today_compact()
    assert re.fullmatch(r"v\d{6}", tag), f"tag {tag!r} must stay vYYMMDD"
    assert tag[1:].count(".") == 0
    date_str = dr.today_date_str()
    assert date_str.count(".") == 2, f"date_str {date_str!r} must be YYYY.M.D"


class _R:
    def __init__(self, code, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = code, stdout, stderr


def test_push_main_rebases_over_a_concurrent_cron_commit(monkeypatch):
    """A rejected push must be rebased and retried, not silently dropped.

    Measured 2026-11-17: `git push origin main` was called with its result
    discarded and the tag was pushed anyway, so tag v261117 carried version
    2026.11.17 on a commit that never reached main. Every install reads main and
    kept reporting 2026.11.14.
    """
    dr = _load_dr()
    calls = []

    def fake_git(*args):
        calls.append(args)
        if args[:2] == ("push", "origin"):
            # first push rejected, second accepted
            rejected = sum(1 for c in calls if c[:2] == ("push", "origin")) == 1
            return _R(1 if rejected else 0,
                      stderr="! [rejected] main -> main (fetch first)" if rejected else "")
        if args[:3] == ("pull", "--rebase", "--autostash"):
            return _R(0)
        return _R(0)

    monkeypatch.setattr(dr, "git", fake_git)
    result = dr.push_main()
    assert result.returncode == 0
    assert ("pull", "--rebase", "--autostash", "origin", "main") in calls
    assert sum(1 for c in calls if c[:2] == ("push", "origin")) == 2


def test_push_main_stops_when_the_rebase_conflicts(monkeypatch):
    dr = _load_dr()
    calls = []

    def fake_git(*args):
        calls.append(args)
        if args[:2] == ("push", "origin"):
            return _R(1, stderr="! [rejected]")
        if args[:3] == ("pull", "--rebase", "--autostash"):
            return _R(1, stderr="CONFLICT (content): pyproject.toml")
        return _R(0)

    monkeypatch.setattr(dr, "git", fake_git)
    result = dr.push_main()
    assert result.returncode != 0
    assert ("rebase", "--abort") in calls