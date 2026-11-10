"""Regression tests for validated, non-destructive desktop translation resumes."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def fill(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "desktop_resume", REPO / "scripts" / "fill_desktop_locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "HOME", tmp_path / "home")
    monkeypatch.setattr(module, "I18N", tmp_path / "i18n")
    module.I18N.mkdir()
    return module


def test_existing_overrides_use_ast_paths_and_decoded_literals(fill):
    path = fill.I18N / "zz.ts"
    path.write_text(
        "export const zz = {\n"
        "  common: { dynamic: fn({ nested: 'not an override' }),\n"
        "    'key.with.dot': `Übersetzt`, save: 'Ligne\\nSuivante',\n"
        "  }, other: { label: 'D’accord' },\n"
        "}\n", encoding="utf-8")
    assert fill.existing_overrides("zz") == {
        f"common{fill.SEP}key.with.dot": "Übersetzt",
        f"common{fill.SEP}save": "Ligne\nSuivante",
        f"other{fill.SEP}label": "D’accord",
    }


def test_js_roundtrips_newlines_and_control_characters(fill):
    value = "Avañe'ẽ\\path\n\r\t\b\f\x00\x01\x1f\u2028\u2029"
    literal = fill.js(value)
    assert not any(c in literal for c in "\n\r\t\b\f\x00\x01\x1f\u2028\u2029")
    proc = subprocess.run(
        ["node", "-e", f"process.stdout.write(JSON.stringify({literal}))"],
        capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(proc.stdout) == value


@pytest.mark.parametrize(("source", "invalid"), [
    ("Open {name}", "Öffne {user}"),
    ("Open {name}", "Öffne {name} {name}"),
    ("Open {{name}}", "Öffne {name}"),
    ("Progress %1$s", "Fortschritt %s"),
    ("Open ${name}", "Öffne {name}"),
    ("Press Ctrl+N", "Drücke Ctrl+M"),
    ("Press Ctrl/⌘+N", "Drücke Ctrl/⌘+M"),
    ("Press Enter", "Drücke Escape"),
    ("Open settings", "Open settings"),
    ("Save", " Save "),
])
def test_invalid_chunk_stays_a_gap(fill, monkeypatch, capsys, source, invalid):
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: json.dumps({"0": invalid}))
    assert fill.translate_chunk([("label", source)], "German", {"TEST": "not-a-secret"}) == {}
    assert "rejected" in capsys.readouterr().out


def test_rejected_batch_retries_next_backend(fill, monkeypatch):
    monkeypatch.setattr(fill, "BACKENDS", [
        ("first", "unused", "TEST", "model"), ("second", "unused", "TEST", "model")])
    replies = iter([{"0": "Open {name}"}, {"0": "Öffne {name}"}])
    monkeypatch.setattr(fill, "call_model", lambda *args: json.dumps(next(replies)))
    assert fill.translate_chunk([("label", "Open {name}")], "German", {"TEST": "test"}) == {
        "label": "Öffne {name}"}


@pytest.mark.parametrize("token", ["OpenAmer", "JSON", "https://example.com", "`--help`", "123", "⌘+N"])
def test_legitimate_machine_tokens_can_remain_unchanged(fill, monkeypatch, token):
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: json.dumps({"0": token}))
    assert fill.translate_chunk([("label", token)], "German", {"TEST": "test"}) == {"label": token}


def write_cache(fill, data):
    path = fill.HOME / "tmp" / "desktop_zz.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("location", ["cache", "module"])
def test_resume_retries_invalid_values_instead_of_counting_them(fill, monkeypatch, capsys, location):
    english = {"save": "Save", "open": "Open {name}", "json": "JSON", "done": "Done"}
    invalid = {"save": "Save", "open": "Öffne {user}", "json": "JSON", "done": "Fertig"}
    cache = write_cache(fill, invalid if location == "cache" else {})
    if location == "module":
        (fill.I18N / "zz.ts").write_text(
            "export const zz = {\n" + fill.render(invalid) + "\n}\n", encoding="utf-8")
    calls = []

    def translate(items, *args):
        calls.extend(items)
        return {"save": "Speichern", "open": "Öffne {name}"}

    monkeypatch.setattr(fill, "translate_chunk", translate)
    fill.run_locale("zz", {"zz": "German"}, english, {}, SimpleNamespace(dry_run=False))
    assert dict(calls) == {"save": "Save", "open": "Open {name}"}
    assert json.loads(cache.read_text(encoding="utf-8")) == {
        "save": "Speichern", "open": "Öffne {name}", "json": "JSON", "done": "Fertig"}
    assert "rejected" in capsys.readouterr().out


@pytest.mark.parametrize("stub", [False, True])
def test_complete_cache_materializes_module_without_model_calls(fill, monkeypatch, stub):
    translated = {f"common{fill.SEP}save": "Speichern"}
    write_cache(fill, translated)
    path = fill.I18N / "zz.ts"
    if stub:
        path.write_text("import { defineLocale } from './define-locale'\n"
                        "export const zz = defineLocale({})\n", encoding="utf-8")

    def unexpected(*args):
        pytest.fail("A fully translated cache must not call a model")

    monkeypatch.setattr(fill, "translate_chunk", unexpected)
    fill.run_locale("zz", {"zz": "German"}, {f"common{fill.SEP}save": "Save"},
                    {}, SimpleNamespace(dry_run=False))
    assert path.exists(), "A full cache is not a materialized locale module"
    assert fill.existing_overrides("zz") == translated


@pytest.mark.parametrize("generated_header", [False, True])
def test_resume_preserves_mature_modules_byte_for_byte(fill, monkeypatch, capsys, generated_header):
    path = fill.I18N / "zz.ts"
    header = ("// German (zz): static literals translated;\n"
              "// interpolated template strings still fall back to English.\n") if generated_header else ""
    extra_import = "" if generated_header else "import { FIELD_LABELS } from './field-copy/zz'\n"
    original = (
        "import { defineLocale } from './define-locale'\n" + extra_import + "\n" + header +
        "export const zz = defineLocale({\n"
        "  common: { save: 'Speichern', welcome: name => `Hallo ${name}` },\n"
        "  fields: FIELD_LABELS,\n"
        "})\n").replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(original)
    monkeypatch.setattr(fill, "translate_chunk", lambda *args: {"open": "Öffnen"})
    fill.run_locale("zz", {"zz": "German"},
                    {f"common{fill.SEP}save": "Save", "open": "Open"},
                    {}, SimpleNamespace(dry_run=False))
    assert path.read_bytes() == original
    cache = fill.HOME / "tmp" / "desktop_zz.json"
    assert json.loads(cache.read_text(encoding="utf-8"))["open"] == "Öffnen"
    output = capsys.readouterr().out
    assert "preserved" in output and "cache" in output and "not applied" in output
    assert "0 gaps" in output and "0 unchanged machine tokens" in output


@pytest.mark.parametrize(("source", "translation"), [
    ("Delete", "Löschen"),
    ("Return to chat", "Zum Chat zurückkehren"),
    ("Command history", "Befehlsverlauf"),
    ("Alternative layout", "Alternatives Layout"),
])
def test_hotkey_validation_does_not_treat_normal_prose_as_keys(fill, monkeypatch, source, translation):
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: json.dumps({"0": translation}))
    assert fill.translate_chunk([("label", source)], "German", {"TEST": "test"}) == {"label": translation}


def test_delete_prose_is_not_an_unchanged_machine_token(fill, monkeypatch):
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: '{"0": "Delete"}')
    assert fill.translate_chunk([("label", "Delete")], "German", {"TEST": "test"}) == {}


@pytest.mark.parametrize(("source", "invalid"), [
    ("Press Delete", "Drücke Space"),
    ("Press ⌘⇧N", "Drücke ⌘⇧M"),
])
def test_additional_keyboard_chords_cannot_drift(fill, monkeypatch, source, invalid):
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: json.dumps({"0": invalid}))
    assert fill.translate_chunk([("label", source)], "German", {"TEST": "test"}) == {}


def test_failed_batch_remains_a_reported_gap_on_resume(fill, monkeypatch, capsys):
    english = {"save": "Save", "json": "JSON"}
    cache = write_cache(fill, english)
    monkeypatch.setattr(fill, "BACKENDS", [("test", "unused", "TEST", "model")])
    monkeypatch.setattr(fill, "call_model", lambda *args: '{"0": "Save"}')
    fill.run_locale("zz", {"zz": "German"}, english, {"TEST": "test"}, SimpleNamespace(dry_run=False))
    assert json.loads(cache.read_text(encoding="utf-8")) == {"json": "JSON"}
    assert fill.existing_overrides("zz") == {"json": "JSON"}
    output = capsys.readouterr().out
    assert "1 gaps" in output and "1 unchanged machine tokens" in output
    monkeypatch.setattr(fill, "call_model", lambda *args: '{"0": "Speichern"}')
    fill.run_locale("zz", {"zz": "German"}, english, {"TEST": "test"}, SimpleNamespace(dry_run=False))
    assert fill.existing_overrides("zz") == {"save": "Speichern", "json": "JSON"}


def test_dry_run_does_not_materialize_a_complete_cache(fill):
    cache = write_cache(fill, {"save": "Speichern"})
    before = cache.read_bytes()
    fill.run_locale("zz", {"zz": "German"}, {"save": "Save"}, {}, SimpleNamespace(dry_run=True))
    assert cache.read_bytes() == before
    assert not (fill.I18N / "zz.ts").exists()
