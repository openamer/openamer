#!/usr/bin/env python3
"""Translate the missing strings of a desktop locale, in batches.

The desktop locales were created with the PARTIAL pattern: only a handful of
sections were translated, everything else fell back to English. This script
fills the gap. It reads the English source (en.ts), the target locale, and
asks a translation model for the strings the target locale does not have yet.

Safety rules that matter more than speed:

* **Placeholders are never translated.** A string containing ``${name}`` is
  sent to the model with the placeholder masked, and the mask is restored
  afterwards. A model that renames ``${count}`` breaks the UI silently.
* **The brand name is never translated.** "OpenAmer" stays "OpenAmer".
* **Untranslated strings keep their English text**, so a partial run never
  produces a broken file.
* **Every batch is verified** against the source: same count, same order,
  no empty output. A failed batch is retried, then given up on (the English
  text stays).

Usage:
    python i18n_translate_locale.py fr            # fill the gaps in fr.ts
    python i18n_translate_locale.py fr --dry-run  # show what would change
    python i18n_translate_locale.py fr --model <id>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
HOME = REPO.parent / "AppData" / "Local" / "openamer-laptop"
ENV_FILE = HOME / ".env"

# Placeholders that must survive verbatim.
#
# A naive regex cannot be used here: an interpolation may itself contain an
# interpolation, e.g.
#     ${count === ${count === 1 ? 'item' : 'items'} ? 'item' : 'items'}
# A regex that stops at the first "}" would mask only the inner part and let
# the model rewrite the outer one — which produced broken output like
#     ${count === ${count === 1 ? 'item' : 'items'} ? 'item' : 'items'}
# and, worse, dropped the outer condition entirely. So the scanner counts
# braces.
def find_placeholders(text: str) -> list[tuple[int, int, str]]:
    """Return [(start, end, placeholder)] for every ${…} in text.

    An unbalanced `${` (no matching `}`) is a broken string: it is reported
    as a placeholder that runs to the end of the text, so the integrity
    check rejects the translation instead of silently accepting it.
    """
    out = []
    i = 0
    while True:
        start = text.find("${", i)
        if start < 0:
            break
        depth = 0
        j = start
        closed = False
        while j < len(text):
            if text.startswith("${", j):
                depth += 1
                j += 2
                continue
            if text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    closed = True
                    break
            j += 1
        if not closed:
            # unbalanced — report it as a broken placeholder
            out.append((start, len(text), text[start:]))
            break
        out.append((start, j, text[start:j]))
        i = j
    return out

# Model backends, tried in order. Each is (name, url, env-var, model).
BACKENDS = [
    ("nemotron-free", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("ollama-deepseek", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "deepseek-v4.1-flash"),
    ("ollama-minimax", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "minimax-m3.1-flash"),
    ("ollama-gemma", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "gemma4:31b"),
]

# The language name to put in the prompt, per locale code.
#
# locales/_languages.json is the single source of truth: it already lists an
# English name for every registered locale. The overrides below only fix the
# codes whose display name is not what the translator must be told ("zh" has to
# say "Simplified Chinese", not "Chinese").
LANGUAGE_NAME_OVERRIDES = {
    "zh": "Simplified Chinese",
    "zh-hant": "Traditional Chinese",
    "torbeski": (
        "Torbeški (South Slavic spoken variety of the Polog/Debar region in "
        "North Macedonia, closely related to Macedonian and Bulgarian but a "
        "distinct variety — do NOT substitute standard Macedonian)"
    ),
}

LANGUAGE_NAMES_FILE = REPO / "locales" / "_languages.json"


def load_language_names() -> dict[str, str]:
    """Every locale code -> the English language name the model should hear.

    Reading the catalog instead of a hand-maintained dict is what keeps this
    correct for all 186 locales; a hard-coded map silently sent the bare code
    ("wa") to the model for every language it did not list.
    """
    names: dict[str, str] = {}
    try:
        raw = json.loads(LANGUAGE_NAMES_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            names = {str(k): str(v) for k, v in raw.items() if v}
    except (OSError, json.JSONDecodeError):
        names = {}
    names.update(LANGUAGE_NAME_OVERRIDES)
    return names


LANGUAGE_NAMES = load_language_names()

MASK = "\uE000"  # private use area marker


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def call_model(url: str, model: str, key: str, messages: list, max_tokens: int = 4000,
               timeout: int = 180) -> str:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def mask_placeholders(text: str) -> tuple[str, list[str]]:
    """Replace every ${…} with a stable marker, remembering the originals."""
    found: list[str] = []
    out = []
    last = 0
    for start, end, ph in find_placeholders(text):
        out.append(text[last:start])
        out.append(f"{MASK}{len(found)}{MASK}")
        found.append(ph)
        last = end
    out.append(text[last:])
    return "".join(out), found


def unmask_placeholders(text: str, found: list[str]) -> str:
    """Restore the original ${…} placeholders."""
    for i, ph in enumerate(found):
        text = text.replace(f"{MASK}{i}{MASK}", ph)
    # any leftover marker (the model mangled the count) is dropped
    text = re.sub(f"{re.escape(MASK)}\\d+{re.escape(MASK)}", "", text)
    return text


def extract_json_array(text: str) -> list[str] | None:
    """Pull a JSON array of strings out of a model reply."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("[")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                blob = text[start:i + 1]
                try:
                    parsed = json.loads(blob)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed
                return None
    return None


def placeholder_shape(placeholder: str) -> tuple[bool, frozenset[str], frozenset[str]]:
    """Describe a ${…} placeholder structurally.

    Returns (balanced, identifiers, operators).

    The literal words inside a ternary may legitimately differ between
    languages — `${count === 1 ? 'notification' : 'notifications'}` becomes
    `${count === 1 ? 'Benachrichtigung' : 'Benachrichtigungen'}` in German.
    What must not change is the structure: the same variables, the same
    operators, and a balanced brace.
    """
    body = placeholder[2:-1] if placeholder.endswith("}") else placeholder[2:]
    balanced = placeholder.endswith("}")
    # strip string literals so their contents do not count as identifiers
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "''", body)
    identifiers = frozenset(re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", stripped))
    operators = frozenset(re.findall(r"===|!==|==|!=|<=|>=|&&|\|\||\?|:|\+|\-|\*|/", stripped))
    return balanced, identifiers, operators


def placeholders_intact(original: str, translated: str) -> bool:
    """True when the translated string carries exactly the source placeholders.

    The model must not add, drop or rename an interpolation. The WORDS
    inside a ternary may change — that is the translation:

        ${count === 1 ? 'message' : 'messages'}
        -> ${count === 1 ? 'message' : 'messages'}

    The variable names and the brace structure must survive; the literal
    words are the translator's business.
    """
    src = [ph for _, _, ph in find_placeholders(original)]
    dst = [ph for _, _, ph in find_placeholders(translated)]
    if len(src) != len(dst):
        return False
    for a, b in zip(src, dst):
        if variables_in(a) != variables_in(b):
            return False
    return True


def variables_in(placeholder: str) -> list[str]:
    """The variable names referenced inside a ${…} placeholder.

    ``${count === 1 ? 'item' : 'items'}`` -> ['count']
    ``${ms !== null ? ` in ${ms}ms` : ''}`` -> ['ms', 'ms']
    """
    return re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", placeholder)


def mask_variables_only(text: str) -> tuple[str, list[str]]:
    """Mask only the VARIABLE names inside an interpolation, not the whole thing.

    The regular masking hides a complete ``${…}`` from the model. That is
    right for ordinary strings, but wrong for the overlay strings: the words
    inside a ternary (``${count === 1 ? 'message' : 'messages'}``) ARE the
    text to translate, and hiding them makes the model return the English
    source unchanged.

    So here we mask only the identifiers that are code — the variable names —
    and leave everything else visible.
    """
    found: list[str] = []
    out = []
    last = 0
    for start, end, ph in find_placeholders(text):
        out.append(text[last:start])
        # Split the placeholder into code and literal parts. The code is
        # everything outside a quoted string; the literals are user-facing
        # text and must stay visible.
        code_parts = []
        literals = []
        i = 0
        while i < len(ph):
            c = ph[i]
            if c in "'\"":
                j = i + 1
                while j < len(ph):
                    if ph[j] == "\\":
                        j += 2
                        continue
                    if ph[j] == c:
                        break
                    j += 1
                literals.append(ph[i:j + 1])
                code_parts.append(f"\x01{len(literals) - 1}\x01")
                i = j + 1
                continue
            code_parts.append(c)
            i += 1
        code = "".join(code_parts)
        # now mask the identifiers inside the CODE part only. The leading "$"
        # of "${" is not an identifier — it is the interpolation marker.
        def repl(m):
            name = m.group(0)
            if name in {"true", "false", "null", "undefined"}:
                return name
            idx = len(found)
            found.append(name)
            return f"{MASK}ID{idx}{MASK}"
        code = re.sub(r"(?<![A-Za-z0-9_$])[A-Za-z_][A-Za-z0-9_]*", repl, code)
        code = re.sub(r"\$", "$", code)
        # put the literals back
        def put_literal(m):
            return literals[int(m.group(1))]
        code = re.sub(r"\x01(\d+)\x01", put_literal, code)
        out.append(code)
        last = end
    out.append(text[last:])
    return "".join(out), found


def unmask_variables(text: str, found: list[str]) -> str:
    """Restore the variable names that mask_variables_only hid."""
    for i, name in enumerate(found):
        text = text.replace(f"{MASK}ID{i}{MASK}", name)
    text = re.sub(f"{re.escape(MASK)}ID\\d+{re.escape(MASK)}", "", text)
    return text


def translate_batch(items: list[str], language: str, backend: tuple, env: dict,
                   force_translate: bool = False, extra_hint: str = "") -> list[str] | None:
    name, url, keyenv, model = backend
    key = env.get(keyenv, "")
    if not key:
        return None
    masked = []
    placeholders = []
    for s in items:
        if force_translate:
            # Only the variable names are hidden — the words inside a ternary
            # must stay visible, they are what has to be translated.
            m, ph = mask_variables_only(s)
        else:
            m, ph = mask_placeholders(s)
        masked.append(m)
        placeholders.append(ph)
    payload = json.dumps(masked, ensure_ascii=False)
    if force_translate:
        # The overlay strings are interpolation-only. The model has to be
        # told explicitly that the WORDS inside the ternary are text and
        # must be translated, while the variable names must not change.
        system = (
            f"You are a professional software localizer translating a desktop app "
            f"into {language}. "
            f"Translate every element of the JSON array into {language}. "
            f"These strings are UI labels built from an interpolation. The text "
            f"inside the interpolation — for example the words in "
            f"`count === 1 ? 'message' : 'messages'` — IS user-facing text and "
            f"MUST be translated into {language}. Only the variable names and the "
            f"code around them stay as they are. "
            f"Rules: keep the array length and order; keep every U+E000 marker "
            f"(and the digits between two markers) exactly as it is; never translate "
            f"the product name OpenAmer; output ONLY a JSON array of strings, "
            f"no commentary, no code fence."
        )
    else:
        system = (
            f"You are a professional software localizer translating a desktop app "
            f"into {language}. "
            f"Translate every element of the JSON array into {language}. "
            "Rules: keep the array length and order; keep every U+E000 marker "
            "(and the digits between two markers) exactly as it is; never translate "
            "the product name OpenAmer; keep the UI tone short and direct; "
            "ALWAYS translate even short strings, single words, abbreviations "
            "like 'Version', 'Options', 'Minimal' or 'Terminal' — only the product "
            "name, acronyms like MCP and URLs stay as they are; "
            "output ONLY a JSON array of strings, no commentary, no code fence."
        )
    if extra_hint:
        system += " " + extra_hint
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": payload},
    ]
    try:
        reply = call_model(url, model, key, messages)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError, KeyError, ValueError,
            json.JSONDecodeError) as exc:
        print(f"    [{name}] failed: {type(exc).__name__} {str(exc)[:120]}", file=sys.stderr)
        return None
    parsed = extract_json_array(reply)
    if parsed is None or len(parsed) != len(items):
        print(f"    [{name}] bad reply (got {len(parsed) if parsed else 0}, want {len(items)})",
              file=sys.stderr)
        return None
    out = []
    broken = 0
    for src, text, ph in zip(items, parsed, placeholders):
        if force_translate:
            restored = unmask_variables(text, ph)
        else:
            restored = unmask_placeholders(text, ph)
        if not placeholders_intact(src, restored):
            broken += 1
            restored = src  # keep the English text, the model broke it
        out.append(restored)
    if broken:
        print(f"    [{name}] {broken} string(s) with broken placeholders -> English kept",
              file=sys.stderr)
    return out


def translate_labels(items: list[str], language: str, backend: tuple, env: dict) -> list[str] | None:
    """Translate SHORT UI LABELS — single words and short phrases.

    The regular prompt carries a sentence in every language ("Translate
    every element of the JSON array into {language}"). The model reads that
    as "these are sentences" and leaves a bare label alone: "Gateway",
    "Host", "System" come back in English. A label has to be asked for as a
    label, with an explicit instruction that an echo is a failure.

    Only the product name, the acronyms and the brand names stay
    untranslated — those are real exceptions, and they are named.
    """
    name, url, keyenv, model = backend
    key = env.get(keyenv, "")
    if not key:
        return None
    system = (
        f"You are a professional software localizer translating the desktop UI "
        f"of an app into {language}. "
        "You receive a JSON array of SHORT UI LABELS (single words and short "
        f"phrases). Translate EVERY element into {language}. "
        "IMPORTANT: even a single English word must be translated — do NOT echo "
        "the English back, not even when the word looks like a technical term, "
        "an acronym, a product name or a loanword that is usually left "
        "untranslated. The only exceptions are the product name 'OpenAmer', "
        "the acronyms 'MCP', 'SSH', 'JSON', 'URL' and the brand names "
        "'Telegram', 'Discord', 'Slack'. A lowercase 'm' used as a unit "
        "(minutes) stays 'm'. A state name such as 'error' must be "
        "translated. "
        "Keep the array length and the order. Output ONLY a JSON array of "
        "strings, no commentary, no code fence."
    )
    payload = json.dumps(items, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": payload},
    ]
    try:
        reply = call_model(url, model, key, messages)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError,
            KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"    [{name}] failed: {type(exc).__name__} {str(exc)[:120]}", file=sys.stderr)
        return None
    parsed = extract_json_array(reply)
    if parsed is None or len(parsed) != len(items):
        print(f"    [{name}] bad reply (got {len(parsed) if parsed else 0}, "
              f"want {len(items)})", file=sys.stderr)
        return None
    return parsed


def load_leaves(locale: str) -> list[dict]:
    """Extract the leaves of a locale via the Node extractor."""
    out_file = REPO / "tmp" / f"i18n_{locale}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    src = I18N / f"{locale}.ts"
    r = subprocess.run(
        ["node", str(REPO / "scripts" / "i18n_extract_locale.mjs"), str(src), str(out_file)],
        capture_output=True, text=True, cwd=str(REPO),
        encoding='utf-8',
        errors='replace',
    )
    if r.returncode != 0:
        raise SystemExit(f"extract failed for {locale}: {r.stderr[-500:]}")
    return json.loads(out_file.read_text(encoding="utf-8"))["leaves"]


def load_overlay(locale: str) -> dict[str, str]:
    """Hand-written translations that override the model output.

    The translation model leaves interpolation-only strings alone
    (``${count} ${count === 1 ? 'message' : 'messages'}``), because it cannot
    tell that the plural forms inside the ternary are translatable text.
    Those strings are supplied per locale in scripts/i18n_overlays/<locale>.json.
    """
    path = REPO / "scripts" / "i18n_overlays" / f"{locale}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  overlay {locale}: invalid JSON ({exc})", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"  overlay {locale}: not an object", file=sys.stderr)
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locale")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="max batches (0 = all)")
    ap.add_argument("--model", default="", help="force one backend by name")
    args = ap.parse_args()

    locale = args.locale
    language = LANGUAGE_NAMES.get(locale, locale)

    env = load_env()
    backends = BACKENDS
    if args.model:
        backends = [b for b in BACKENDS if b[0] == args.model]
        if not backends:
            raise SystemExit(f"unknown backend {args.model}")

    en_leaves = load_leaves("en")
    tgt_leaves = load_leaves(locale)

    en_text = {l["path"]: l["text"] for l in en_leaves if l["kind"] in ("string", "func")}
    tgt_text = {l["path"]: l["text"] for l in tgt_leaves if l["kind"] in ("string", "func")}

    # A previous run may already have produced translations that were not
    # written back to the locale file yet. They count as done — otherwise
    # every run would redo the same work.
    cache = REPO / "tmp" / f"i18n_{locale}_translations.json"
    if cache.exists():
        try:
            prev = json.loads(cache.read_text(encoding="utf-8"))
            for k, v in prev.items():
                tgt_text.setdefault(k, v)
        except (json.JSONDecodeError, OSError):
            pass

    # A path counts as translated when the target text differs from English
    # AND its placeholders are intact. Identical text is either untranslated
    # or a proper noun — either way there is nothing to translate. A broken
    # interpolation counts as NOT translated: English text is better than a
    # string that would render wrong.
    def is_broken(p: str, tgt: str) -> bool:
        src_ph = [x for _, _, x in find_placeholders(en_text[p])]
        tgt_ph = [x for _, _, x in find_placeholders(tgt)]
        return src_ph != tgt_ph

    missing = []
    for p, t in en_text.items():
        if p not in tgt_text:
            missing.append(p)
            continue
        if tgt_text[p] == t:
            missing.append(p)
            continue
        if is_broken(p, tgt_text[p]):
            print(f"  re-translating {p} (broken placeholders)", file=sys.stderr)
            missing.append(p)
    print(f"{locale}: {len(en_text)} English strings, {len(missing)} to translate")
    if args.dry_run:
        for p in missing[:30]:
            print(f"  {p}: {en_text[p][:70]}")
        return 0

    # keep only translatable kinds
    todo = [p for p in missing if en_text[p].strip()]
    translations: dict[str, str] = {}

    # Translate the batches concurrently. The backends answer 8 parallel
    # requests in 1.5 s, so the wall time is bound by the slowest batch,
    # not by their sum.
    batches = [todo[i:i + args.batch_size] for i in range(0, len(todo), args.batch_size)]
    if args.limit:
        batches = batches[:args.limit]

    lock = threading.Lock()
    done_count = 0

    def run_batch(bi: int, batch: list[str]) -> None:
        nonlocal done_count
        items = [en_text[p] for p in batch]
        result = None
        for backend in backends:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        with lock:
            if result is None:
                print(f"  batch {bi}/{len(batches)}: FAILED (English kept)", file=sys.stderr)
            else:
                n = 0
                for p, t in zip(batch, result):
                    if t and t.strip():
                        translations[p] = t
                        n += 1
                done_count += 1
                print(f"  batch {bi}/{len(batches)}: {n}/{len(batch)} translated "
                      f"({done_count}/{len(batches)} done)", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_batch, bi, b) for bi, b in enumerate(batches, 1)]
        for f in futures:
            f.result()

    # merge with what the locale already has
    merged = dict(tgt_text)
    merged.update(translations)

    # the hand-written overlay wins over the model output
    overlay = load_overlay(locale)
    if overlay:
        for k, v in overlay.items():
            if k in en_text:
                merged[k] = v
        print(f"overlay: {len(overlay)} hand-written strings applied")

    out = REPO / "tmp" / f"i18n_{locale}_translations.json"
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(merged)} strings, {len(translations)} new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
