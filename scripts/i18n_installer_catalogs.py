#!/usr/bin/env python3
"""Generate the setup-window catalogues from the English source catalogue.

The installer asks for a language on its first screen and then runs in it, so
its copy has to exist as data per language (`apps/bootstrap-installer/src/i18n/
catalogs/<code>.json`). This script turns `en.json` into those files using the
same measured backend chain as the product locales, and refuses a translation
that leaves its own writing system.

    python scripts/i18n_installer_catalogs.py            # fill what is missing
    python scripts/i18n_installer_catalogs.py --force de # redo one language
    python scripts/i18n_installer_catalogs.py --list     # what exists

A language is only written when the whole array came back, in order, with every
placeholder intact and inside the expected script. Anything else is dropped with
a reason: a half-translated setup window that falls back to English mid-flow is
worse than not offering the language at all.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import i18n_script_check as scriptcheck  # noqa: E402
import i18n_translate_locale as translate  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
CATALOGS = REPO / "apps" / "bootstrap-installer" / "src" / "i18n" / "catalogs"
NAMES = REPO / "apps" / "bootstrap-installer" / "src" / "i18n" / "language-names.json"
DESKTOP_LANGUAGES = REPO / "apps" / "desktop" / "src" / "i18n" / "languages.ts"
PRODUCT_LOCALES = REPO / "locales"

# The languages the setup window offers. Chosen to cover the people who install
# software in their own language rather than in English, minus the ones we cannot
# verify: `torbeski` has no ISO code and its native strings are authored by the
# project owner, never machine-generated.
# The setup window speaks exactly what the product speaks: the target set is
# derived from `locales/*.yaml`, so the two cannot drift apart. Only the codes
# below are excluded, and each for a stated reason.
EXCLUDED = {
    # No ISO code. Its native strings are authored by the project owner; a model
    # would invent them, which is worse than an English setup window.
    "torbeski",
}


def targets() -> list[str]:
    codes = sorted(path.stem for path in PRODUCT_LOCALES.glob("*.yaml"))

    return [code for code in codes if code not in EXCLUDED]

PLACEHOLDER = re.compile(r"\{(\w+)\}")
INT = re.compile(r"^\d+$")


def flatten(node: object, prefix: str = "") -> list[tuple[str, str]]:
    """Ordered (path, text) pairs. Array indices become numeric path segments."""
    if isinstance(node, dict):
        return [pair for key in node for pair in flatten(node[key], f"{prefix}.{key}" if prefix else key)]
    if isinstance(node, list):
        return [pair for i, item in enumerate(node) for pair in flatten(item, f"{prefix}.{i}" if prefix else str(i))]

    return [(prefix, str(node))]


def rebuild(pairs: list[tuple[str, str]]) -> dict:
    """Inverse of flatten: numeric segments become list indices via `to_lists`."""
    root: dict = {}
    for path, text in pairs:
        parts = path.split(".")
        cursor = root
        for part in parts[:-1]:
            nxt = cursor.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[part] = nxt
            cursor = nxt
        cursor[parts[-1]] = text

    return to_lists(root)


def to_lists(node: object) -> object:
    if isinstance(node, dict):
        if node and all(INT.match(k) for k in node):
            return [to_lists(node[k]) for k in sorted(node, key=int)]
        return {k: to_lists(v) for k, v in sorted(node.items())}

    return node


def language_name(code: str) -> str:
    return translate.LANGUAGE_NAMES.get(code, code)


def expected_scripts(code: str) -> frozenset[str]:
    """Scripts this locale is allowed to use, learned from the product locale."""
    source = PRODUCT_LOCALES / f"{code}.yaml"
    committed = source.read_text(encoding="utf-8") if source.exists() else ""

    return scriptcheck.expected_script(code, committed)


def verify(code: str, english: list[tuple[str, str]], translated: list[str]) -> str | None:
    """Return a rejection reason, or None when the catalogue is usable."""
    if len(translated) != len(english):
        return f"length {len(translated)} != {len(english)}"

    for (path, source), value in zip(english, translated):
        if not isinstance(value, str) or not value.strip():
            return f"empty value at {path}"
        if PLACEHOLDER.findall(source) != PLACEHOLDER.findall(value):
            return f"placeholder drift at {path}"
        if "openamer" in source.lower() and "openamer" not in value.lower() and path != "success.command":
            return f"product name lost at {path}"

    allowed = expected_scripts(code)
    foreign = scriptcheck.foreign_values(translated, allowed) if allowed else []

    if foreign:
        return f"foreign script in {len(foreign)} value(s): {foreign[0]!r}"

    return None


def repair_placeholders(
    code: str,
    english: list[tuple[str, str]],
    translated: list[str],
    env: dict,
    prefer: tuple | None = None,
) -> list[str] | None:
    """Re-ask for the few strings whose {placeholders} drifted, keep the rest.

    A model that translates 81 of 82 strings well and drops `{done}` in the
    82nd has not failed — one line has. Throwing the whole reply away (and then
    walking the entire backend chain) is what made small languages take minutes.
    The repair is constrained: only the offending strings are re-requested, and
    the result still has to pass `verify` before anything is written.
    """
    bad = [
        index
        for index, ((_, source), value) in enumerate(zip(english, translated))
        if PLACEHOLDER.findall(source) != PLACEHOLDER.findall(str(value))
    ]

    if not bad:
        return translated

    subset = [english[index][1] for index in bad]

    # Retry the backend that just got everything else right, first. The rest of
    # the chain stays as a fallback, but it is not walked for a one-line fix.
    chain = backend_chain(env)
    if prefer:
        chain = [prefer] + [b for b in chain if b[0] != prefer[0]]

    for backend in chain:
        got = translate.translate_batch(
            subset,
            language_name(code),
            backend,
            env,
            locale=code,
            extra_hint=(
                "Keep every {placeholder} exactly as written, same spelling, same "
                "number of them. Everything else must be translated."
            ),
        )

        if not got or len(got) != len(subset):
            continue

        if all(
            PLACEHOLDER.findall(source) == PLACEHOLDER.findall(str(value))
            for source, value in zip(subset, got)
        ):
            patched = list(translated)
            for offset, index in enumerate(bad):
                patched[index] = got[offset]
            return patched

        print(f"    repair still drifts at {english[bad[0]][0]}")

    return None


def backend_chain(env: dict) -> list[tuple]:
    return translate.BACKENDS


def translate_locale(code: str, english: list[tuple[str, str]], env: dict, force: bool) -> str:
    """Translate what this language is missing, then merge.

    A first run writes the whole catalogue; a later run that adds strings to
    `en.json` only pays for the new ones. Either way the file is rewritten from
    the English key order, so stale keys cannot accumulate.
    """
    out = CATALOGS / f"{code}.json"
    existing: dict[str, str] = {}

    if out.exists() and not force:
        existing = dict(flatten(json.loads(out.read_text(encoding="utf-8"))))

    todo = [(path, text) for path, text in english if path not in existing]

    if not todo:
        return "skip (complete)"

    texts = [text for _, text in todo]

    for backend in backend_chain(env):
        try:
            translated = translate.translate_batch(texts, language_name(code), backend, env, locale=code)
        except Exception as exc:  # noqa: BLE001 - a dead backend is a retry, not a crash
            print(f"  {backend[0]}: {type(exc).__name__}: {exc}".rstrip())
            continue

        if not translated:
            continue

        reason = verify(code, todo, translated)

        if reason and reason.startswith("placeholder drift"):
            repaired = repair_placeholders(code, todo, translated, env, prefer=backend)

            if repaired is not None:
                translated = repaired
                reason = verify(code, todo, translated)

                if reason is None:
                    print(f"  {backend[0]}: ok after repairing the placeholder line")

        if reason:
            print(f"  {backend[0]}: rejected — {reason}")
            continue

        merged = existing | {path: value for (path, _), value in zip(todo, translated)}
        ordered = [(path, merged[path]) for path, _ in english if path in merged]
        out.write_text(
            json.dumps(rebuild(ordered), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        added = f"+{len(todo)}" if existing else f"{len(todo)}"
        return f"ok via {backend[0]} ({added} strings)"

    return "FAILED (no backend produced a usable catalogue)"


def write_language_names() -> int:
    """Endonyms for the picker, taken from the desktop's own locale table."""
    if not DESKTOP_LANGUAGES.exists():
        return 0

    source = DESKTOP_LANGUAGES.read_text(encoding="utf-8")
    entries = {}
    pattern = re.compile(
        r"\{\s*id:\s*'([^']+)',\s*name:\s*'((?:[^'\\]|\\.)*)',\s*englishName:\s*'((?:[^'\\]|\\.)*)'",
        re.MULTILINE,
    )

    for code, endonym, english in pattern.findall(source):
        if (CATALOGS / f"{code}.json").exists():
            entries[code] = {"endonym": endonym.replace("\\'", "'"), "englishName": english.replace("\\'", "'")}

    NAMES.write_text(json.dumps(entries, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return len(entries)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", nargs="*", metavar="CODE", help="re-translate these (default: only missing)")
    ap.add_argument("--list", action="store_true", help="list catalogues and exit")
    args = ap.parse_args()

    CATALOGS.mkdir(parents=True, exist_ok=True)
    english = flatten(json.loads((CATALOGS / "en.json").read_text(encoding="utf-8")))

    if args.list:
        for path in sorted(CATALOGS.glob("*.json")):
            print(path.stem)
        return 0

    env = translate.load_env()
    force = bool(args.force)
    selected = args.force or targets()

    print(f"{len(english)} strings x {len(selected)} languages")

    failures = []
    for code in selected:
        if code == "en":
            continue
        result = translate_locale(code, english, env, force)
        print(f"{code:8} {result}")
        if result.startswith("FAILED"):
            failures.append(code)
        else:
            # After every catalogue, not just at the end: the picker's names file
            # and the catalogue set are one invariant, and an interrupted run must
            # not leave a catalogue the picker cannot name.
            write_language_names()

    count = write_language_names()
    print(f"\nlanguage-names.json: {count} entries")

    if failures:
        print(f"failed: {', '.join(failures)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
