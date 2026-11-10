"""A reboot-recycled process ID must not strand a locale lock."""
import importlib.util
import subprocess
import sys
from pathlib import Path


def test_legacy_lock_with_unrelated_live_pid_is_reclaimed(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / 'scripts/fill_desktop_locales.py'
    spec = importlib.util.spec_from_file_location('lock_recovery', script)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    monkeypatch.setattr(worker, 'HOME', tmp_path)
    lockdir = tmp_path / 'tmp/locks'
    lockdir.mkdir(parents=True)
    other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        (lockdir / 'desktop-zz.lock').write_text(str(other.pid), encoding='utf-8')
        with worker.locale_lock('zz') as owned:
            assert owned is True
            with worker.locale_lock('zz') as duplicate:
                assert duplicate is False
    finally:
        other.terminate()
        other.wait(timeout=10)
