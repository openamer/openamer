"""Contract tests for the setup-window catalogues.

The installer offers exactly the languages it can speak, so every file under
`apps/bootstrap-installer/src/i18n/catalogs/` is a promise made on its first
screen. These tests keep the promise measurable: same keys as English, same
placeholders, same array lengths, nothing empty, and nothing left in a script the
language does not use.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CATALOGS = REPO / "apps" / "bootstrap-installer" / "src" / "i18n" / "catalogs"
NAMES = REPO / "apps" / "bootstrap-installer" / "src" / "i18n" / "language-names.json"

sys.path.insert(0, str(REPO / "scripts"))


def load(code: str) -> dict:
    return json.loads((CATALOGS / f"{code}.json").read_text(encoding="utf-8"))


def flat(node: object, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(node, dict):
        return [pair for key in node for pair in flat(node[key], f"{prefix}.{key}" if prefix else key)]
    if isinstance(node, list):
        return [pair for i, item in enumerate(node) for pair in flat(item, f"{prefix}.{i}" if prefix else str(i))]

    return [(prefix, str(node))]


def codes() -> list[str]:
    return sorted(path.stem for path in CATALOGS.glob("*.json"))


def test_english_source_exists() -> None:
    assert (CATALOGS / "en.json").is_file(), "the setup window needs a source catalogue"


def test_at_least_the_two_languages_we_hand_wrote() -> None:
    # Not a coverage target — a guard that the directory did not get emptied by a
    # failed generator run.
    assert {"de", "en"} <= set(codes())


@pytest.mark.parametrize("code", codes())
def test_catalogue_matches_the_english_shape(code: str) -> None:
    source = dict(flat(load("en")))
    target = dict(flat(load(code)))

    assert sorted(target) == sorted(source), f"{code}: key set drifted from en.json"


@pytest.mark.parametrize("code", codes())
def test_placeholders_survive_translation(code: str) -> None:
    import re

    placeholder = re.compile(r"\{(\w+)\}")

    for path, text in flat(load("en")):
        translated = dict(flat(load(code)))[path]
        assert placeholder.findall(text) == placeholder.findall(translated), f"{code}: placeholders changed at {path}"


@pytest.mark.parametrize("code", codes())
def test_no_empty_values(code: str) -> None:
    for path, text in flat(load(code)):
        assert text.strip(), f"{code}: empty value at {path}"


@pytest.mark.parametrize("code", codes())
def test_product_name_is_never_translated(code: str) -> None:
    source = dict(flat(load("en")))
    target = dict(flat(load(code)))

    for path, text in source.items():
        if "OpenAmer" in text and path != "success.command":
            assert "OpenAmer" in target[path], f"{code}: product name lost at {path}"


@pytest.mark.parametrize("code", codes())
def test_values_stay_in_their_own_script(code: str) -> None:
    import i18n_script_check as scriptcheck

    product_locale = REPO / "locales" / f"{code}.yaml"
    committed = product_locale.read_text(encoding="utf-8") if product_locale.exists() else ""
    allowed = scriptcheck.expected_script(code, committed)

    if not allowed:
        pytest.skip(f"{code}: Latin-only locale")

    texts = [text for _, text in flat(load(code))]
    foreign = scriptcheck.foreign_values(texts, allowed)

    assert not foreign, f"{code}: foreign script in {len(foreign)} value(s), first={foreign[0]!r}"


def test_language_names_cover_every_catalogue() -> None:
    names = json.loads(NAMES.read_text(encoding="utf-8"))

    missing = sorted(set(codes()) - set(names))

    assert not missing, f"language-names.json is missing endonyms for: {missing}"


def test_language_names_have_both_fields() -> None:
    names = json.loads(NAMES.read_text(encoding="utf-8"))

    for code, entry in names.items():
        assert entry.get("endonym"), f"{code}: no endonym"
        assert entry.get("englishName"), f"{code}: no englishName"


def test_no_catalogue_is_just_the_english_source() -> None:
    """A catalogue may not be an English echo dressed in a language code.

    Measured 2026-11-18: aa, gv, hz, iu, ki, kj, kw shipped at 0 % translated and
    ff/ho at 19.5 %/26.8 %, so the picker offered those languages and the window
    ran in English. The installer's own contract (src/i18n/index.ts): "a language
    offered and then answered in English mid-flow is worse than one that is not
    offered." Values that are legitimately identical stay below the bound.
    """
    source = dict(flat(load("en")))
    echo = []
    for code in codes():
        if code == "en":
            continue
        target = dict(flat(load(code)))
        identical = sum(1 for path, text in target.items() if text == source.get(path))
        share = identical / len(source)
        if share > 0.10:
            echo.append(f"{code} {share:.0%}")

    assert not echo, (
        "these catalogues echo the English source instead of translating it, so "
        "the setup window would offer a language and then run in English: "
        + ", ".join(echo)
    )


def test_the_english_echo_guard_rejects_an_echo() -> None:
    """The generator's own gate must reject what this test rejects."""
    sys.path.insert(0, str(REPO / "scripts"))
    import i18n_installer_catalogs as gen

    english = gen.flatten(load("en"))
    echo_reply = [text for _, text in english]

    reason = gen.verify("de", english, echo_reply)

    assert reason is not None and "English" in reason, (
        f"an untranslated reply must be rejected, got {reason!r}"
    )
