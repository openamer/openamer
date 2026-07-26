from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    assert "%LOCALAPPDATA%\\openamer\\openamer-agent\\venv\\Scripts" in doc
    assert "Get-Command openamer        # should print C:\\Users\\<you>\\AppData\\Local\\openamer\\openamer-agent\\venv\\Scripts\\openamer.exe" in doc
    assert '$openamerBin = "$InstallDir\\venv\\Scripts"' in install
