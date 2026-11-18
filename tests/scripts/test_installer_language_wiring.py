"""The setup language must survive the install, all the way into the app config.

A language chosen on the setup window's first screen is worthless if it dies at
the next process boundary. This test pins the four links of that chain so a
refactor cannot silently cut one:

    setup UI ($lang)  ->  Tauri arg  ->  install.ps1  ->  config.display.language

The last hop is deliberately done through the installed CLI
(`openamer config set display.language <code>`) rather than by editing YAML in
PowerShell: config.yaml is owned by the CLI, and a hand-written file would drift
from the schema the CLI migrates.
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
INSTALLER = REPO / "apps" / "bootstrap-installer"
INSTALL_PS1 = REPO / "scripts" / "install.ps1"


def test_install_script_accepts_a_language() -> None:
    source = INSTALL_PS1.read_text(encoding="utf-8")

    assert "[string]$UiLanguage" in source, "install.ps1 must accept -UiLanguage"


def test_language_is_persisted_through_the_cli() -> None:
    source = INSTALL_PS1.read_text(encoding="utf-8")
    start = source.find("function Set-UiLanguageFromSetup")

    assert start != -1, "install.ps1 must define Set-UiLanguageFromSetup"

    body = source[start : source.find("\nfunction ", start + 1)]

    assert "openamer_cli.main" in body, "the language must be written by the CLI, not by hand"
    assert "config" in body and "display.language" in body
    assert "$UiLanguage" in body, "the function must use the parameter it is given"
    # A malformed code must not reach the config: the regex is the only guard
    # between a UI value and a persisted setting.
    assert "-notmatch" in body, "the language code must be validated before it is written"


def test_config_stage_runs_the_persistence_step() -> None:
    source = INSTALL_PS1.read_text(encoding="utf-8")

    assert "function Stage-ConfigTemplates  { Copy-ConfigTemplates; Set-UiLanguageFromSetup }" in source, (
        "the config-templates stage is what runs after the venv exists — the "
        "language write must be part of it or it never runs"
    )


def test_tauri_passes_the_language_to_the_script() -> None:
    source = (INSTALLER / "src-tauri" / "src" / "bootstrap.rs").read_text(encoding="utf-8")

    assert "pub language: Option<String>" in source, "BootstrapArgs must carry the language"
    assert '"-UiLanguage"' in source, "the stage call must pass -UiLanguage"
    assert "args.language" in source


def test_setup_ui_sends_the_chosen_language() -> None:
    source = (INSTALLER / "src" / "store.ts").read_text(encoding="utf-8")

    assert "language: " in source and "$lang.get()" in source, (
        "startInstall must send the language that was chosen on the first screen"
    )
