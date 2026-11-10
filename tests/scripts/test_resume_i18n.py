"""Exercise the recovery entrypoint with a real inert launcher, no model calls."""
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "resume_i18n.py"


def load():
    spec = importlib.util.spec_from_file_location("resume_i18n", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recovery_invokes_both_targets_and_records_result(tmp_path, monkeypatch, capsys):
    module = load()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "start_i18n_detached.py").write_text(
        "import sys\nprint('already alive: ' + sys.argv[sys.argv.index('--target')+1])\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "HOME", tmp_path / "home")
    assert module.main() == 0
    ledger = json.loads((tmp_path / "home/logs/i18n-resume.json").read_text(encoding="utf-8"))
    assert set(ledger["targets"]) == {"cli", "desktop"}
    assert all(record["returncode"] == 0 for record in ledger["targets"].values())
    assert capsys.readouterr().out == ""


def test_launcher_failure_is_not_reported_as_success(tmp_path, monkeypatch, capsys):
    module = load()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "start_i18n_detached.py").write_text(
        "import sys\nprint('backend unavailable', file=sys.stderr)\nsys.exit(2)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "HOME", tmp_path / "home")
    assert module.main() == 1
    assert "backend unavailable" in capsys.readouterr().out
