"""Contract: an approval prompt must advertise exactly the keys it accepts.

Displayed keys, accepted typed inputs and the prompt text live in three separate
catalog keys, so translating them independently drifts them apart. Measured on
tr before this fix: the labels offered '[b]ir kez | [r]eddet', the prompt said
'[b/R]' and the accepted inputs were still 'o,once' -- a prompt that offers a
key it rejects, in a safety prompt.

The normal (non smart-deny) path is stricter still: tools/approval.py hardcodes
o/s/a/d there, so those letters are surface in every language.

The generator now derives the typed inputs and the advertised keys from the
displayed labels, so all four catalog keys are consistent by construction. These
tests pin the derivation and check the locales whose keys the approval tests
exercise (tr, fr, ja); the remaining catalogs converge on their next generation
run, which is why the locale data itself is not asserted repo-wide here.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
LOCALES = REPO / "locales"
VERIFIED_LOCALES = ["tr", "fr", "ja"]


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "cli_i18n_keys", REPO / "scripts" / "i18n_fill_cli_locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("lang", VERIFIED_LOCALES)
def test_approval_prompt_advertises_its_accepted_keys(lang):
    path = LOCALES / f"{lang}.yaml"
    if not path.is_file():
        pytest.skip(f"{lang}.yaml not generated yet")
    approval = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("approval", {})
    labels = approval.get("choose_smart_deny", "")
    prompt = approval.get("prompt_smart_deny", "")
    once_inputs = approval.get("smart_deny_once_inputs", "")
    deny_inputs = approval.get("smart_deny_deny_inputs", "")

    shown = [segment.strip() for segment in labels.split("|")]
    assert len(shown) == 2, f"{lang}: smart deny must offer once/deny, got {labels!r}"
    keys = []
    for segment in shown:
        assert segment.startswith("[") and "]" in segment, (
            f"{lang}: label without a bracketed key: {segment!r}")
        keys.append(segment[1:segment.index("]")])

    advertised = re.search(r"\[([^\]]*)\]", prompt)
    assert advertised, f"{lang}: smart deny prompt shows no key run: {prompt!r}"
    assert [part.strip() for part in advertised.group(1).split("/")] == [
        keys[0], keys[1].upper()], (
        f"{lang}: prompt {prompt!r} does not advertise the labels' keys {keys}")
    assert once_inputs.split(",")[0] == keys[0], (
        f"{lang}: accepts {once_inputs!r} for once but shows key {keys[0]!r}")
    assert deny_inputs.split(",")[0] == keys[1], (
        f"{lang}: accepts {deny_inputs!r} for deny but shows key {keys[1]!r}")


@pytest.mark.parametrize("lang", VERIFIED_LOCALES)
def test_normal_prompt_keeps_the_hardcoded_keys(lang):
    """tools/approval.py accepts only o/s/a/d on the normal path."""
    path = LOCALES / f"{lang}.yaml"
    if not path.is_file():
        pytest.skip(f"{lang}.yaml not generated yet")
    approval = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("approval", {})
    for key, letters in (("prompt_long", ["o", "s", "a", "d"]),
                         ("prompt_short", ["o", "s", "d"])):
        prompt = approval.get(key, "")
        assert "[" in prompt and "]" in prompt, f"{lang}: {key} shows no key run: {prompt!r}"
        shown = [part.strip().lower() for part in
                 prompt[prompt.index("[") + 1:prompt.index("]")].split("/")]
        assert shown == letters, (
            f"{lang}: {key} advertises {shown} but the code accepts {letters}")


def test_alignment_derives_the_keys_from_the_labels():
    cli = _load_cli()
    values = {
        "approval.choose_smart_deny": "      [o] Bir kez  |  [d] Reddet",
        "approval.prompt_smart_deny": "      Seçim [x/Y]: ",
        "approval.smart_deny_once_inputs": "o,once",
        "approval.smart_deny_deny_inputs": "d,deny",
    }
    cli.align_smart_deny(values)
    assert values["approval.choose_smart_deny"] == "      [b]ir kez  |  [r]eddet"
    assert values["approval.prompt_smart_deny"] == "      Seçim [b/R]: "
    assert values["approval.smart_deny_once_inputs"] == "b,bir kez"
    assert values["approval.smart_deny_deny_inputs"] == "r,reddet"


def test_alignment_keeps_attached_keys_and_scripts_without_latin_letters():
    """'[o]ne fois' keeps its key; a CJK label keeps the key it was given."""
    cli = _load_cli()
    values = {
        "approval.choose_smart_deny": "      [o]ne fois  |  [r]efuser",
        "approval.prompt_smart_deny": "      Choix [o/D] : ",
        "approval.smart_deny_once_inputs": "o,once",
        "approval.smart_deny_deny_inputs": "d,deny",
    }
    cli.align_smart_deny(values)
    assert values["approval.choose_smart_deny"] == "      [o]ne fois  |  [r]efuser"
    assert values["approval.prompt_smart_deny"] == "      Choix [o/R] : "
    assert values["approval.smart_deny_once_inputs"] == "o,one fois"

    ja = {
        "approval.choose_smart_deny": "      [o]今回のみ  |  [d]拒否",
        "approval.prompt_smart_deny": "      選択 [x/Y]: ",
        "approval.smart_deny_once_inputs": "o,once",
        "approval.smart_deny_deny_inputs": "d,deny",
    }
    cli.align_smart_deny(ja)
    assert ja["approval.choose_smart_deny"] == "      [o]今回のみ  |  [d]拒否"
    assert ja["approval.prompt_smart_deny"] == "      選択 [o/D]: "


def test_alignment_is_idempotent():
    """Running the alignment twice must not change anything."""
    cli = _load_cli()
    values = {
        "approval.choose_smart_deny": "      [o] Bir kez  |  [d] Reddet",
        "approval.prompt_smart_deny": "      Seçim [x/Y]: ",
        "approval.smart_deny_once_inputs": "o,once",
        "approval.smart_deny_deny_inputs": "d,deny",
    }
    cli.align_smart_deny(values)
    once = dict(values)
    cli.align_smart_deny(values)
    assert values == once


def test_fixed_key_runs_are_restored_without_touching_the_prose():
    """Only the bracketed key is rewritten; the surrounding words stay put."""
    cli = _load_cli()
    values = {
        "approval.choose_long": "      [o] Bir kez  |  [s] Oturum  |  [a] Her zaman  |  [d] Reddet",
        "approval.prompt_long": "      Seçim [b/o/h/R]: ",
        "approval.prompt_short": "      Choix [o/s/D] : ",
    }
    cli.align_fixed_key_runs(values)
    assert values["approval.choose_long"] == (
        "      [o] Bir kez  |  [s] Oturum  |  [a] Her zaman  |  [d] Reddet")
    assert values["approval.prompt_long"] == "      Seçim [o/s/a/D]: "
    assert values["approval.prompt_short"] == "      Choix [o/s/D] : "
