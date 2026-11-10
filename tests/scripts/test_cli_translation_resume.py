"""Regression tests for CLI translation resume without live credentials or APIs."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def translator(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts/i18n_fill_cli_locales.py"
    spec = importlib.util.spec_from_file_location("cli_translation_resume", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    locales = tmp_path / "locales"
    locales.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(module, "LOCALES", locales)
    monkeypatch.setattr(module, "TMP", cache_dir)
    monkeypatch.setattr(module, "load_env", lambda: {})
    monkeypatch.setattr(module, "BATCH_PAUSE_S", 0)
    monkeypatch.setattr(module, "MAX_WORKERS", 1)

    def forbid_network(*args, **kwargs):
        pytest.fail("Translation resume tests must not call external APIs")

    monkeypatch.setattr(module, "call_model", forbid_network)
    return module


def seed(translator, english, catalog=None, cache=None, accepted=None):
    (translator.LOCALES / "en.yaml").write_text(
        yaml.safe_dump(english, allow_unicode=True), encoding="utf-8"
    )
    if catalog is not None:
        (translator.LOCALES / "de.yaml").write_text(
            yaml.safe_dump(catalog, allow_unicode=True), encoding="utf-8"
        )
    if cache is not None:
        (translator.TMP / "i18n_cli_de_translations.json").write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
        )
    if accepted is not None:
        (translator.TMP / "i18n_cli_de_identical.json").write_text(
            json.dumps(accepted), encoding="utf-8"
        )
    return translator.flatten(english)


def test_fully_cached_locale_materializes_catalog_without_loading_credentials(translator, monkeypatch):
    english = {"ui": {"greet": "Hello {name}", "quit": "Quit"},
               "approval": {"smart_deny_once_inputs": "o,once"}}
    flat = seed(translator, english, catalog=english,
                cache={"ui.greet": "Hallo {name}", "ui.quit": "Beenden",
                       "approval.smart_deny_once_inputs": "wrong"})

    def forbid_credentials():
        pytest.fail("A fully cached locale must not load credentials")

    monkeypatch.setattr(translator, "load_env", forbid_credentials)
    status, count, total = translator.translate_locale("de", flat, False, False)

    assert status in {"cached", "written"}
    assert (count, total) == (0, len(flat))
    assert translator.flatten(translator.load_yaml("de")) == {
        "ui.greet": "Hallo {name}", "ui.quit": "Beenden",
        "approval.smart_deny_once_inputs": "o,once",
    }


def test_stale_english_cache_does_not_override_translated_catalog(translator):
    english = {"ui": {"greet": "Hello", "quit": "Quit"}}
    flat = seed(translator, english,
                catalog={"ui": {"greet": "Hallo", "quit": "Quit"}},
                cache={"ui.greet": "Hello", "ui.quit": "Beenden"})

    assert translator.translate_locale("de", flat, False, False) == ("cached", 0, 2)
    assert translator.flatten(translator.load_yaml("de")) == {
        "ui.greet": "Hallo", "ui.quit": "Beenden",
    }


def test_partial_cache_is_materialized_even_without_a_backend(translator):
    english = {"ui": {"greet": "Hello", "quit": "Quit"}}
    flat = seed(translator, english, catalog=english, cache={"ui.greet": "Hallo"})

    assert translator.translate_locale("de", flat, False, False)[0] == "no-backend"
    assert translator.flatten(translator.load_yaml("de")) == {
        "ui.greet": "Hallo", "ui.quit": "Quit",
    }


def fake_backend(translator, monkeypatch, reply):
    monkeypatch.setattr(translator, "BACKENDS", [("offline", "unused", "TEST_KEY", "test")])
    monkeypatch.setattr(translator, "load_env", lambda: {"TEST_KEY": "test-only"})

    def respond(*args, **kwargs):
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply)

    monkeypatch.setattr(translator, "call_model", respond)


def test_failed_short_labels_are_not_accepted_as_complete(translator, monkeypatch):
    flat = seed(translator, {"ui": {"quit": "Quit", "product": "OpenAmer"}})
    fake_backend(translator, monkeypatch, OSError("offline test failure"))

    assert translator.translate_locale("de", flat, False, False) == ("written", 0, 2)
    accepted = json.loads((translator.TMP / "i18n_cli_de_identical.json").read_text())
    assert accepted == []
    assert translator.translate_locale("de", flat, False, True) == ("would-translate", 2, 2)


@pytest.mark.parametrize("text,accepted", [
    ("Quit", False), ("Error", False), ("No active goal.", False),
    ("Please select a language before continuing.", False),
    ("OpenAmer", True), ("OK", True), ("config.yaml", True),
    ("/model", True), ("ms", True), ("`--global`", True),
])
def test_successful_unchanged_reply_only_settles_machine_or_product_text(
        translator, monkeypatch, text, accepted):
    flat = seed(translator, {"ui": {"label": text}})
    fake_backend(translator, monkeypatch, {"0": text})

    translator.translate_locale("de", flat, False, False)

    settled = json.loads((translator.TMP / "i18n_cli_de_identical.json").read_text())
    assert settled == (["ui.label"] if accepted else [])
    assert translator.translate_locale("de", flat, False, True) == (
        "would-translate", 0 if accepted else 1, 1,
    )


@pytest.mark.parametrize("source,reply,count", [
    ("Quit", "Quit", 0), ("OpenAmer", "OpenAmer", 0),
    ("Please select a language before continuing.",
     "Please select a language before continuing.", 0),
    ("Quit", "Beenden", 1),
])
def test_success_count_only_includes_changed_translations(
        translator, monkeypatch, source, reply, count):
    flat = seed(translator, {"ui": {"label": source}})
    fake_backend(translator, monkeypatch, {"0": reply})

    assert translator.translate_locale("de", flat, False, False) == ("written", count, 1)


@pytest.mark.parametrize("entrypoint", ["locale", "main"])
def test_stale_accept_list_cannot_hide_unchanged_english_prose(
        translator, monkeypatch, capsys, entrypoint):
    english = {"ui": {"label": "Quit", "help": "Please select a language before continuing."}}
    flat = seed(translator, english, catalog=english, cache=translator.flatten(english),
                accepted=["ui.label", "ui.help"])

    if entrypoint == "locale":
        assert translator.translate_locale("de", flat, False, True) == ("would-translate", 2, 2)
    else:
        monkeypatch.setattr(translator.sys, "argv", ["i18n_fill_cli_locales.py", "--dry-run", "de"])
        assert translator.main() == 0
        output = capsys.readouterr().out
        assert "targets: 1 -> de(2)" in output
        assert "would-translate" in output


def test_whitespace_only_cache_change_remains_a_translation_gap(translator):
    flat = seed(translator, {"ui": {"label": "Quit"}},
                cache={"ui.label": " Quit "})

    assert translator.translate_locale("de", flat, False, True) == ("would-translate", 1, 1)


@pytest.mark.parametrize("cached", ["", "   "])
def test_blank_cache_cannot_mask_translated_catalog(translator, cached):
    flat = seed(translator, {"ui": {"label": "Quit"}},
                catalog={"ui": {"label": "Beenden"}}, cache={"ui.label": cached})

    assert translator.translate_locale("de", flat, False, False) == ("cached", 0, 1)
    assert translator.flatten(translator.load_yaml("de")) == {"ui.label": "Beenden"}
