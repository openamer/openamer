"""Guard: ``_install_uv`` must pin TEMP/TMP inside OPENAMER_HOME and clean up.

Regression for HOME litter: with TMP and TEMP both unset, .NET's
``[System.IO.Path]::GetTempPath()`` (used by the astral Windows installer)
falls back to ``%USERPROFILE%``, so every uv install dropped a ~18 MB
``uv-x86_64`` GUID extraction dir into the user's HOME (measured 2026-10-11:
102 dirs, 1.8 GB).  ``_install_uv`` now pins TEMP/TMP to
``<OPENAMER_HOME>/tmp/uv-install`` and removes it in a ``finally``.
"""
from pathlib import Path
from unittest import mock

from openamer_cli import managed_uv as m


def test_install_uv_pins_temp_into_home_and_cleans_up(tmp_path):
    target = tmp_path / "openamer-laptop" / "bin" / "uv.exe"
    captured = {}

    def fake_windows(env):
        captured.update(env)
        # While the installer runs, the pinned scratch dir must exist and be
        # the same for TEMP and TMP.
        assert Path(env["TEMP"]).is_dir()
        assert Path(env["TEMP"]) == Path(env["TMP"])

    with mock.patch.object(m, "_install_uv_windows", fake_windows), \
            mock.patch.object(m.platform, "system", return_value="Windows"):
        m._install_uv(target)

    assert "openamer-laptop" in captured["TEMP"]
    assert captured["TEMP"].endswith(str(Path("tmp") / "uv-install"))
    # No litter: the scratch dir is gone once _install_uv returns.
    assert not Path(captured["TEMP"]).exists()
