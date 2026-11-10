#!/usr/bin/env python3
"""Fill the missing CLI locale catalogs (``locales/<lang>.yaml``).

Why this exists: ``agent/i18n.py`` advertises every locale the desktop app
ships (41 codes), but the CLI static-message catalog only ever had 17 files.
For the other 24 the CLI silently fell back to English *and*
``tests/agent/test_i18n.py`` was red on 49 parametrised cases (5 missing
files + 24 placeholder/parity failures), which is exactly what the nightly
watchdog had been reporting.

Design rules, in order of importance:

* **The key set is never allowed to drift.** Output is built from the English
  source structure, so a translation can only ever change *values*. A key
  missing from the model reply keeps its English text — never an empty string.
* **Placeholders are masked before the model sees them.** ``{count}`` sent to a
  model comes back renamed often enough to matter; the mask makes renaming
  impossible rather than merely unlikely, and any leftover marker is dropped.
* **Input tokens are not prose.** ``approval.smart_deny_once_inputs`` is
  ``"o,once"`` — the literal keystrokes the prompt accepts. Translating it
  breaks the approval prompt. Those keys are copied verbatim.
* **Everything is cached.** ``tmp/i18n_cli_<lang>_translations.json`` is
  rewritten after every batch, so a rerun (or a crash) costs only the rest.
* **Every batch is verified.** Same index count, same placeholder set per key.
  A batch that fails verification is retried once, then left in English.

Usage:
    python i18n_fill_cli_locales.py                 # every missing locale
    python i18n_fill_cli_locales.py sl hr et lv lt  # specific ones
    python i18n_fill_cli_locales.py --force nl      # re-translate a full file
    python i18n_fill_cli_locales.py --dry-run nl    # report, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCALES = REPO / "locales"
TMP = REPO / "tmp"
HOME = Path(os.environ.get("OPENAMER_HOME")
            or str(Path.home() / "AppData" / "Local" / "openamer-laptop"
                   if os.name == "nt" else Path.home() / ".openamer-laptop"))

BATCH = max(1, int(os.environ.get("OPENAMER_I18N_BATCH", "6")))
# The provider rate-limits hard when several batches run concurrently: five
# worker processes x four threads produced a wall of HTTP 429s and left locales
# 90% English. Default to a single request in flight and let the operator raise
# it explicitly (OPENAMER_I18N_WORKERS) for a provider they know tolerates it.
MAX_WORKERS = max(1, int(os.environ.get("OPENAMER_I18N_WORKERS", "1")))
# Pause between batches in the same worker. A translation batch costs ~5s, so a
# small sleep keeps the request rate under the provider's per-minute ceiling
# without materially slowing a 55-batch locale.
BATCH_PAUSE_S = float(os.environ.get("OPENAMER_I18N_BATCH_PAUSE", "1.0"))
RETRIES = 3

# Model backends, tried in order: (name, url, env var, model).
BACKENDS = [
    # Prefer the configured free route; Ollama session quota is shared by models.
    ("openrouter-nemotron", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("ollama-deepseek", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "deepseek-v4.1-flash"),
    ("ollama-minimax", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "minimax-m3.1-flash"),
]

# English names used in the prompt. locales/_languages.json is the single source
# of truth for the advertised set (agent/i18n.py is generated from it), so the
# translator never has to guess what "aa" or "za" stands for. The literal below
# is only the fallback for a checkout that predates that file.
_LANG_NAMES_FALLBACK = {
    "ar": "Arabic", "bg": "Bulgarian", "bs": "Bosnian", "cs": "Czech",
    "da": "Danish", "el": "Greek", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French",
    "ga": "Irish", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian",
    "id": "Indonesian", "it": "Italian", "ja": "Japanese", "ko": "Korean",
    "lt": "Lithuanian", "lv": "Latvian", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "sk": "Slovak", "sl": "Slovenian", "sq": "Albanian", "sv": "Swedish",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese",
    "zh": "Simplified Chinese", "zh-hant": "Traditional Chinese",
}


def _load_language_names() -> dict[str, str]:
    path = REPO / "locales" / "_languages.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_LANG_NAMES_FALLBACK)


LANGUAGE_NAMES = _load_language_names()

# Literal keystrokes / machine tokens -- never translated.
VERBATIM_KEYS = {"approval.smart_deny_once_inputs", "approval.smart_deny_deny_inputs"}

MASK = "\uE000"
PH_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ---------------------------------------------------------------------------
# catalog helpers
# ---------------------------------------------------------------------------

def load_yaml(lang: str) -> dict | None:
    import yaml
    p = LOCALES / f"{lang}.yaml"
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def flatten(d: dict, prefix: str = "") -> dict:
    out: dict[str, str] = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = "" if v is None else str(v)
    return out


def unflatten(flat: dict, structure: dict, prefix: str = "") -> dict:
    """Rebuild nested YAML using ``structure`` for shape, ``flat`` for values."""
    out: dict = {}
    for k, v in structure.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out[k] = unflatten(flat, v, key)
        else:
            out[k] = flat.get(key, "" if v is None else str(v))
    return out


def supported_languages() -> list[str]:
    """Read the advertised list from agent/i18n.py itself -- no second copy."""
    sys.path.insert(0, str(REPO))
    try:
        from agent import i18n  # type: ignore
        return list(i18n.SUPPORTED_LANGUAGES)
    finally:
        try:
            sys.path.remove(str(REPO))
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# model plumbing
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for p in (HOME / ".env", REPO / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
            if m:
                env.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
    return env


def call_model(url: str, model: str, key: str, messages: list,
               max_tokens: int = 4000, timeout: int = 180) -> str:
    payload = {
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": 0,
    }
    # A reasoning model spends the whole completion budget thinking and then
    # returns an EMPTY content field with finish_reason="length" (measured on
    # deepseek-v4.1-flash: 20k chars of reasoning, 0 chars of output). Asking
    # for low effort is what makes the translation actually come back.
    if "ollama.com" in url:
        payload["reasoning_effort"] = "low"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    for attempt in range(4):  # up to 3 retries (0,1,2,3)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                # The provider's window is roughly a minute; a 2s/4s/8s ladder
                # walks straight back into it. Start at 10s and grow to 40s so a
                # throttled batch actually clears instead of burning its retries.
                wait = min(40.0, 10.0 * (2 ** attempt)) * (1 + 0.3 * random.random())
                time.sleep(wait)
                continue
            raise


def mask(text: str) -> tuple[str, list[str]]:
    found, out, last = [], [], 0
    for m in PH_RE.finditer(text):
        out.append(text[last:m.start()])
        out.append(f"{MASK}{len(found)}{MASK}")
        found.append(m.group(0))
        last = m.end()
    out.append(text[last:])
    return "".join(out), found


def unmask(text: str, found: list[str]) -> str:
    for i, ph in enumerate(found):
        text = text.replace(f"{MASK}{i}{MASK}", ph)
    return re.sub(f"{re.escape(MASK)}\\d+{re.escape(MASK)}", "", text)


def parse_json_object(reply: str) -> dict | None:
    if not isinstance(reply, str):
        return None
    t = reply.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def translate_batch(keys: list[str], texts: list[str], lang: str,
                    backend: tuple, env: dict) -> dict[str, str] | None:
    name, url, keyenv, model = backend
    api_key = env.get(keyenv, "")
    if not api_key:
        return None
    masked = [mask(t) for t in texts]
    listing = "\n".join(f"{i}. {m}" for i, m in enumerate(x[0] for x in masked))
    prompt = (
        f"Translate the following CLI interface strings into {LANGUAGE_NAMES.get(lang, lang)}.\n"
        "Rules:\n"
        "- Output ONLY a JSON object mapping the index number (as a string) to the translation.\n"
        "- Preserve every \uE000<number>\uE000 marker exactly as it appears; never translate it.\n"
        "- A letter in square brackets is a KEYBOARD INPUT, not a word: [o] [s] [a] [d]\n"
        "  must stay [o] [s] [a] [d] -- in that order and with those exact letters.\n"
        "  The typed key is fixed and the label is free, so when the translated word\n"
        "  starts with a different letter keep the bracketed key and put the whole\n"
        "  word after it: '[a] Toujours', never '[t]oujours'. A prompt that offers a\n"
        "  key it does not accept is a broken prompt.\n"
        "- Keep 'OpenAmer', 'config.yaml', slash commands (/model, /resume, ...), "
        "code in backticks, URLs and file paths unchanged.\n"
        "- Keep line breaks and the per-line indentation layout; these are terminal prompts.\n"
        "- Do not add explanations. Every index must appear exactly once.\n\n"
        f"{listing}"
    )
    last_err = ""
    for attempt in range(RETRIES):
        try:
            reply = call_model(url, model, api_key,
                               [{"role": "user", "content": prompt}],
                               max_tokens=8000)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                TimeoutError, KeyError, ValueError) as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
        obj = parse_json_object(reply)
        if obj is None:
            last_err = "reply was not a JSON object"
            continue
        out: dict[str, str] = {}
        ok = True
        for i, key in enumerate(keys):
            raw = obj.get(str(i))
            if not isinstance(raw, str) or not raw.strip():
                ok = False
                break
            restored = unmask(raw, masked[i][1])
            src = texts[i]
            # Outer whitespace is layout, not prose: a terminal prompt that
            # loses its indentation misaligns. Restore it from the source.
            lead = re.match(r"\s*", src)
            trail = re.search(r"\s*$", src)
            restored = ((lead.group(0) if lead else "")
                        + restored.strip()
                        + (trail.group(0) if trail else ""))
            # Placeholder parity: the test asserts it, but failing here (and
            # retrying) is cheaper than writing a broken catalog.
            if set(PH_RE.findall(restored)) != set(PH_RE.findall(src)):
                ok = False
                break
            # Bracketed runs are machine surface ([o/s/a/D] keys, [kanban]):
            # they must survive byte-identical, whatever the language.
            if re.findall(r"\[[^\]\n]*\]", src) != re.findall(r"\[[^\]\n]*\]", restored):
                ok = False
                break
            out[key] = restored
        if ok and len(out) == len(keys):
            return out
        last_err = "batch failed verification (missing index or placeholder drift)"
    print(f"    ! {name} batch failed: {last_err}", flush=True)
    return None


def is_machine_text(text: str) -> bool:
    """Conservatively recognize short literals, never ordinary English labels."""
    text = text.strip()
    if len(text) > 20:
        return False
    if text in {"OpenAmer", "OK", "ms", "s", "KB", "MB", "GB", "TB", "Hz"}:
        return True
    return bool(re.fullmatch(
        r"(?:`[^`\s]+`|/[\w/-]+|[\w-]+\.(?:yaml|yml|json|toml|py)|\{\w+\})", text
    ))


def write_catalog(lang: str, table: dict[str, str], en_flat: dict[str, str]) -> None:
    """Materialize cached translations with the English shape and safe fallbacks."""
    values = {k: table.get(k) or v for k, v in en_flat.items()}
    for k in VERBATIM_KEYS:
        if k in en_flat:
            values[k] = en_flat[k]
    doc = unflatten(values, load_yaml("en"))
    header = (
        f"# OpenAmer static-message catalog -- {LANGUAGE_NAMES.get(lang, lang)} ({lang})\n"
        "# Generated by scripts/i18n_fill_cli_locales.py from locales/en.yaml.\n"
        "# See locales/en.yaml for the source of truth; keep keys in sync.\n\n"
    )
    import yaml
    body = yaml.dump(doc, allow_unicode=True, default_flow_style=False,
                     sort_keys=False, width=100000)
    (LOCALES / f"{lang}.yaml").write_text(header + body, encoding="utf-8", newline="\n")


def translate_locale(lang: str, en_flat: dict[str, str], force: bool,
                     dry_run: bool) -> tuple[str, int, int]:
    """Returns (status, translated_count, total)."""
    cache = TMP / f"i18n_cli_{lang}_translations.json"
    TMP.mkdir(exist_ok=True)
    table: dict[str, str] = {}
    if cache.exists() and not force:
        try:
            table = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            table = {}

    # An existing catalog is a translation source too: keep what is already right.
    existing = flatten(load_yaml(lang) or {})
    for k, v in existing.items():
        if k in en_flat and v:
            cached = table.get(k)
            if not cached or not cached.strip() or (cached.strip() == en_flat[k].strip()
                              and v.strip() != en_flat[k].strip()):
                table[k] = v

    # Keys with no entry, OR an entry still byte-identical to English, are gaps.
    # A shipped catalog can hold all 330 keys and still be 90% English: the
    # English text was written back as a fallback, so "key present" says nothing
    # about whether it was translated. Keys the model deliberately leaves
    # identical (product names, "OK", bare units) are recorded once in an
    # accept-list file so a later run does not retry them forever.
    ident_file = TMP / f"i18n_cli_{lang}_identical.json"
    accepted_same: set[str] = set()
    if ident_file.exists() and not force:
        try:
            accepted_same = set(json.loads(ident_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            accepted_same = set()

    def _is_gap(k: str) -> bool:
        if k in VERBATIM_KEYS:
            return False
        v = table.get(k)
        if not v:
            return True
        if v.strip() != en_flat[k].strip():
            return False  # changed text, not proof of linguistic quality
        return k not in accepted_same or not is_machine_text(en_flat[k])

    todo = [k for k in en_flat if _is_gap(k)]
    total = len(en_flat)
    if dry_run:
        return ("would-translate", len(todo), total)
    if not todo:
        write_catalog(lang, table, en_flat)
        return ("cached", 0, total)

    env = load_env()
    backends = [cand for cand in BACKENDS if env.get(cand[2])]
    if not backends:
        write_catalog(lang, table, en_flat)
        return ("no-backend", len(todo), total)

    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    done = 0
    returned: set[str] = set()
    lock = threading.Lock()

    def work(batch: list[str]) -> list[str]:
        nonlocal done
        texts = [en_flat[k] for k in batch]
        res = None
        for backend in backends:
            res = translate_batch(batch, texts, lang, backend, env)
            if res:
                break
        if res:
            with lock:
                table.update(res)
                returned.update(res)
                # Changed text is progress, not proof of linguistic quality.
                done += sum(v.strip() != en_flat[k].strip() for k, v in res.items())
                cache.write_text(json.dumps(table, ensure_ascii=False, indent=1),
                                 encoding="utf-8", newline="\n")
            # Throttle this worker: measured 429s arrive as soon as requests
            # come faster than roughly one per couple of seconds.
            time.sleep(BATCH_PAUSE_S)
            return list(res)
        time.sleep(BATCH_PAUSE_S)
        return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(work, b) for b in batches]
        for f in as_completed(futures):
            f.result()

    # Verbatim keys stay byte-identical.
    for k in VERBATIM_KEYS:
        if k in en_flat:
            table[k] = en_flat[k]

    # Anything still missing keeps its English text -- never blank.
    for k in en_flat:
        table.setdefault(k, en_flat[k])

    # Failed requests are not evidence that an unchanged value is intentional.
    accepted_same = {k for k in en_flat
                     if k not in VERBATIM_KEYS
                     and table.get(k) == en_flat[k]
                     and is_machine_text(en_flat[k])
                     and (k in accepted_same or k in returned)}
    try:
        ident_file.write_text(json.dumps(sorted(accepted_same), ensure_ascii=False, indent=1),
                              encoding="utf-8", newline="\n")
    except OSError:
        pass

    write_catalog(lang, table, en_flat)
    return ("written", done, total)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("locales", nargs="*", help="locale codes (default: all advertised)")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--dry-run", action="store_true", help="report only")
    args = ap.parse_args()

    en_flat = flatten(load_yaml("en"))
    if not en_flat:
        print("locales/en.yaml is missing or empty", file=sys.stderr)
        return 2

    targets = args.locales or supported_languages()
    if not targets:
        print("no locales", file=sys.stderr)
        return 2

    def _gap_count(lang: str) -> int:
        """Keys with no entry, or an entry still byte-identical to English.

        Existence of <lang>.yaml is NOT evidence of translation: the writer
        fills every missing key with the English text so no prompt is ever
        blank, which means a catalog can hold all 330 keys and still be
        untranslated. Counting gaps is the only honest completeness check.
        """
        path = LOCALES / f"{lang}.yaml"
        if not path.exists():
            return len(en_flat)
        try:
            have = flatten(load_yaml(lang) or {})
        except Exception:
            return len(en_flat)
        ident_file = TMP / f"i18n_cli_{lang}_identical.json"
        accepted: set[str] = set()
        if ident_file.exists() and not args.force:
            try:
                accepted = set(json.loads(ident_file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                accepted = set()
        gaps = 0
        for k, v in en_flat.items():
            if k in VERBATIM_KEYS:
                continue
            got = have.get(k)
            if not got:
                gaps += 1
            elif (str(got).strip() == str(v).strip()
                  and (k not in accepted or not is_machine_text(v))):
                gaps += 1
        return gaps

    missing = [l for l in targets if l != "en" and (args.force or _gap_count(l) > 0)]
    print(f"en source keys: {len(en_flat)}")
    detail = " ".join(f"{l}({_gap_count(l)})" for l in missing)
    print(f"targets: {len(missing)} -> {detail or '(none missing)'}")

    failures = 0
    for lang in missing:
        status, n, total = translate_locale(lang, en_flat, args.force, args.dry_run)
        flag = "OK " if status in ("written", "cached", "would-translate") else "ERR"
        print(f"  {flag} {lang:<8} {status:<16} {n}/{total}", flush=True)
        if flag == "ERR":
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
