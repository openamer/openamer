"""Fill desktop locale modules from en.ts using the same model backends as the CLI.

Desktop strings live in TypeScript modules (apps/desktop/src/i18n/<code>.ts) as a
nested object of literals plus arrow functions for interpolated strings. A new
language ships as `defineLocale({})`, which falls back to English for everything
-- usable, but English.

This script translates the STATIC literals and writes them back as defineLocale
overrides. Interpolated functions are deliberately left alone: a template literal
with `${x}` has to keep its expression and its punctuation, and silently
rewriting one is worse than leaving it English.

Usage:
    python scripts/fill_desktop_locales.py de fr            # specific locales
    python scripts/fill_desktop_locales.py --all --limit 20 # next N pending
    python scripts/fill_desktop_locales.py --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
EN = I18N / "en.ts"
LANGS = REPO / "locales" / "_languages.json"
HOME = Path(os.environ.get("OPENAMER_HOME") or (Path.home() / "AppData" / "Local" / "openamer-laptop"))

BATCH = int(os.environ.get("OPENAMER_DESKTOP_BATCH", "20"))
WORKERS = max(1, int(os.environ.get("OPENAMER_DESKTOP_WORKERS", "2")))
BACKENDS = [
    # Prefer the configured free route; account quotas affect all Ollama models.
    ("openrouter-nemotron", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    # Second $0 pillar: a free rolling weekly window, so it keeps working when
    # the OpenRouter free route answers 429. Same model as the Ollama default.
    ("tokenharbor-deepseek", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "deepseek-v4.1-flash:free"),
    ("tokenharbor-mimo", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "mimo-v2.5:free"),
    ("ollama-deepseek", "https://ollama.com/v1/chat/completions", "OLLAMA_API_KEY", "deepseek-v4.1-flash"),
    ("ollama-minimax", "https://ollama.com/v1/chat/completions", "OLLAMA_API_KEY", "minimax-m3.1-flash"),
    # Keyless (key_env "-"): no account to exhaust. Anonymous tier, rate-limited
    # per IP, so it is a real pillar for a swarm, not a replacement.
    ("pollinations-openai-fast", "https://text.pollinations.ai/openai", "-", "openai-fast"),
]

# Swarm sharding: one worker process pins itself to one backend, so a 429 on a
# single provider can never stall the whole fleet (measured: OpenRouter free sits
# in 4x40s backoff while another provider answers immediately).
PINNED_BACKEND = os.environ.get("OPENAMER_I18N_BACKEND", "").strip()

# Dynamically discovered lanes (free models with their own rate pools) live in
# this file; a builder writes it from the live provider catalog. Fixed path so a
# detached worker needs no extra plumbing beyond the pin.
EXTRA_BACKENDS_FILE = HOME / "tmp" / "swarm-backends.json"


def _extra_backends() -> list[tuple]:
    if not EXTRA_BACKENDS_FILE.is_file():
        return []
    try:
        rows = json.loads(EXTRA_BACKENDS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("name") and row.get("url") and row.get("model"):
            out.append((str(row["name"]), str(row["url"]),
                        str(row.get("key_env") or "-"), str(row["model"])))
    return out


def backend_chain(env: dict[str, str]) -> list[tuple]:
    """Backends usable in this process: pinned if asked, keyless always."""
    chain = []
    for cand in BACKENDS + _extra_backends():
        name, _url, keyenv, _model = cand
        if PINNED_BACKEND and name != PINNED_BACKEND:
            continue
        if keyenv == "-" or env.get(keyenv):
            chain.append(cand)
    return chain

KEY_RE = re.compile(r"^(\s*)(?:'((?:[^'\\]|\\.)*)'|([A-Za-z_$][A-Za-z0-9_$]*))\s*:\s*(.*)$")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for p in (HOME / ".env", REPO / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def parse_en() -> dict[str, str]:
    """Flatten en.ts through the TypeScript AST.

    A regex parser was tried first and silently mis-nested keys: `foo: fn({`
    looked like an object open, so a nested call swallowed the following
    properties and the generated catalog had keys at the wrong depth -- tsc
    caught it only AFTER a 35-minute translation run. The AST gives exact paths.
    """
    proc = subprocess.run(
        ["node", str(REPO / "scripts" / "extract_locale_literals.js"), str(EN)],
        capture_output=True, text=True, cwd=str(REPO), timeout=180)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(f"literal extraction failed: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)


SEP = "\u001f"  # path separator; en.ts has keys that themselves contain dots


def unflatten(flat: dict[str, str]) -> dict:
    tree: dict = {}
    for path, value in flat.items():
        parts = path.split(SEP)
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    return tree


def js(value: str) -> str:
    escaped = json.dumps(value, ensure_ascii=False)[1:-1]
    escaped = escaped.replace("\\\"", '"').replace("'", "\\'")
    escaped = escaped.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "'" + escaped + "'"


IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def js_key(key: str) -> str:
    """Render an object key, quoting anything that is not a bare identifier.

    en.ts carries keys like `every-15-minutes` and `commandDescs./help`; emitting
    those unquoted would be a syntax error in 185 generated catalogs.
    """
    return key if IDENT_RE.match(key) else js(key)


def render(tree: dict, indent: int = 2) -> str:
    pad = " " * indent
    lines = []
    for key, value in tree.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{js_key(key)}: {{")
            lines.append(render(value, indent + 2))
            lines.append(f"{pad}}},")
        else:
            lines.append(f"{pad}{js_key(key)}: {js(value)},")
    return "\n".join(lines)


def call_model(url: str, model: str, key: str, prompt: str, timeout: int = 240) -> str:
    payload = {"model": model, "temperature": 0,
               "messages": [{"role": "user", "content": prompt}]}
    if "ollama.com" in url or "tokenharbor.ai" in url:
        payload["reasoning_effort"] = "low"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    import random
    import time
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(min(40.0, 10.0 * (2 ** attempt)) * (1 + 0.3 * random.random()))
                continue
            raise
    raise RuntimeError("unreachable")


PLACEHOLDER_RE = re.compile(
    r"\$\{[^{}]+\}|\{\{[^{}]+\}\}|\{[^{}]*\}"
    r"|%(?:\([^)]+\)|\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[sdfir]"
)
_MODIFIER = r"(?:Ctrl|Control|Cmd|Command|Alt|Option|Shift|Meta|Super|[⌘⌥⇧⌃])"
_KEY = rf"(?:{_MODIFIER}|[A-Za-z0-9]+|[+\-])"
HOTKEY_RE = re.compile(
    rf"(?<!\w){_MODIFIER}(?:[/+]\s*{_KEY})+(?!\w)"
    r"|[⌘⌥⇧⌃]+[A-Za-z0-9]?"
    r"|\bF\d{1,2}\b"
)
AMBIGUOUS_KEY_RE = re.compile(r"\b(?:Enter|Escape|Esc|Tab|Backspace|Return|Space|Delete)\b")
MACHINE_TOKENS = frozenset({
    "OpenAmer", "JSON", "API", "URL", "HTTP", "HTTPS", "SSH", "UTF-8",
    "HTML", "CSS", "SQL", "OAuth", "OAuth2", "GitHub", "GitLab",
})


def machine_token(value: str) -> bool:
    """Conservative exemptions, not an uppercase/one-word prose heuristic."""
    return bool(
        value in MACHINE_TOKENS
        or not any(c.isalpha() for c in value)
        or re.fullmatch(r"(?:https?://|/|[A-Za-z]:[\\/])\S+", value)
        or re.fullmatch(r"`[^`]+`", value)
        or HOTKEY_RE.fullmatch(value)
        or re.fullmatch(r"(?:Enter|Escape|Esc|Tab|Backspace)", value)
    )


def validation_error(source: str, value: object) -> str | None:
    """Validate both fresh responses and resumed data before counting coverage."""
    if not isinstance(value, str) or not value.strip():
        return "empty/non-string value"
    if value.strip() == source.strip() and not machine_token(source.strip()):
        return "unchanged English"
    if Counter(PLACEHOLDER_RE.findall(source)) != Counter(PLACEHOLDER_RE.findall(value)):
        return "placeholder drift"
    if Counter(HOTKEY_RE.findall(source)) != Counter(HOTKEY_RE.findall(value)):
        return "hotkey drift"
    # "Delete" and "Return to chat" are prose, not keyboard instructions.
    if (re.search(r"\b(?:press|hit|hold|key|shortcut)\b", source, re.I)
            or re.search(r"\b(?:Enter|Escape|Esc|Tab|Backspace) to\b", source)
            or re.fullmatch(r"(?:Enter|Escape|Esc|Tab|Backspace)", source.strip())):
        if Counter(AMBIGUOUS_KEY_RE.findall(source)) != Counter(AMBIGUOUS_KEY_RE.findall(value)):
            return "hotkey drift"
    return None


def translate_chunk(items: list[tuple[str, str]], lang_name: str, env: dict) -> dict[str, str]:
    listing = "\n".join(f"{i}. {v}" for i, (_, v) in enumerate(items))
    prompt = (
        f"Translate these desktop UI strings into {lang_name}.\n"
        "Rules:\n"
        "- Output ONLY a JSON object mapping the index number (as a string) to the translation.\n"
        "- These are short interface labels (buttons, headings, hints). Keep them short.\n"
        "- Keep the literal characters \\n if present. Keep {placeholders} exactly.\n"
        "- Preserve hotkeys (Ctrl/⌘+N, Enter, etc.) exactly.\n"
        "- Translate English prose; unchanged prose is rejected and retried.\n"
        "- Keep 'OpenAmer', file paths, URLs, and code in backticks unchanged.\n"
        "- Every index must appear exactly once. No explanations.\n\n"
        f"{listing}"
    )
    for cand in backend_chain(env):
        name, url, keyenv, model = cand
        key = "-" if keyenv == "-" else env.get(keyenv, "")
        if not key:
            continue
        try:
            reply = call_model(url, model, key, prompt)
        except Exception:
            continue
        t = reply.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
            t = re.sub(r"\n?```$", "", t)
        s, e = t.find("{"), t.rfind("}")
        if s < 0 or e < 0:
            continue
        try:
            obj = json.loads(t[s:e + 1])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        out = {}
        for i, (path, src) in enumerate(items):
            got = obj.get(str(i))
            reason = validation_error(src, got)
            if reason:
                print(f"    {lang_name}: {name} rejected index {i}: {reason}", flush=True)
                break
            out[path] = got.strip()
        if len(out) == len(items):
            return out
    return {}


def existing_overrides(code: str) -> dict[str, str]:
    """Literal overrides already present in the module (flat)."""
    path = I18N / f"{code}.ts"
    if not path.exists():
        return {}
    proc = subprocess.run(
        ["node", str(REPO / "scripts" / "extract_locale_literals.js"), str(path)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO), timeout=180)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"literal extraction failed for {code}: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)


def parse_literals(text: str) -> dict[str, str]:
    """Flat literal overrides already present in a module (SEP-joined paths)."""
    out, stack = {}, []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = KEY_RE.match(line)
        if not m:
            if line.strip() in ("}", "},"):
                if stack:
                    stack.pop()
            continue
        indent = len(m.group(1))
        key = m.group(2) if m.group(2) is not None else m.group(3)
        key = key.replace("\\'", "'") if m.group(2) is not None else key
        rest = m.group(4).strip()
        if rest.startswith("{"):
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, key))
            continue
        sm = re.fullmatch(r"""(["'])((?:[^\\]|\\.)*)\1,?""", rest)
        if sm and stack:
            out[SEP.join([k for _, k in stack] + [key])] = sm.group(2)
    return out


def _pid_alive(pid: int) -> bool:
    """True when the pid exists.

    Never ``os.kill(pid, 0)``: on Windows that is not a probe -- it delivers
    CTRL_C_EVENT to the target's console process group and hard-kills it, plus
    unrelated siblings (bpo-14484). psutil is a core dependency and probes
    correctly on every platform.
    """
    import psutil
    return psutil.pid_exists(pid)


@contextlib.contextmanager
def locale_lock(code: str):
    """Exclusive per-locale lock so two runs can never write the same module.

    Measured the hard way: three stale `bn` runs (started before a parser fix)
    each held the same output file. Last writer wins, not the best writer -- an
    outdated process can overwrite a newer, correct catalog and silently undo a
    fix. The cache prevented data loss but not ordering. Yields False when
    another live process owns the locale.
    """
    lockdir = HOME / "tmp" / "locks"
    lockdir.mkdir(parents=True, exist_ok=True)
    lock = lockdir / f"desktop-{code}.lock"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            owner = int(lock.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            owner = 0
        if owner and _pid_alive(owner):
            import psutil
            try:
                process = psutil.Process(owner)
                expected = os.path.normcase(os.path.abspath(__file__))
                owns_worker = owner == os.getpid() or any(
                    os.path.normcase(os.path.abspath(arg)) == expected
                    for arg in process.cmdline()[1:] if not arg.startswith("-"))
            except (psutil.Error, OSError, ValueError):
                owns_worker = False
            if owns_worker:
                yield False
                return
        # Stale lock from a dead process: take it over.
        try:
            lock.unlink()
        except OSError:
            pass
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            yield False
            return
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield True
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def atomic_write(path: Path, text: str) -> None:
    """Write via temp + replace so tsc never reads a half-written module."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    names = json.loads(LANGS.read_text(encoding="utf-8"))
    en = parse_en()
    print(f"en static literals: {len(en)}")

    targets = args.locales or ([c for c in names if c != "en"] if args.all else [])
    if not targets:
        print("no locales given (use --all)")
        return 2
    if args.limit:
        targets = targets[:args.limit]

    env = load_env()
    if not any(env.get(b[2]) for b in BACKENDS):
        print("no model backend credentials found", file=sys.stderr)
        return 2

    for code in targets:
        with locale_lock(code) as owned:
            if not owned:
                print(f"  {code}: in flight in another process, skipping")
                continue
            run_locale(code, names, en, env, args)
    return 0


def run_locale(code: str, names: dict, en: dict, env: dict, args) -> None:
    """Translate one locale while its lock is held."""
    cache_path = HOME / "tmp" / f"desktop_{code}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    have: dict[str, str] = {}
    if cache_path.exists():
        try:
            have = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            have = {}
    existing = existing_overrides(code)
    validated: dict[str, str] = {}
    for origin, entries in (("cache", have), ("module", existing)):
        if not isinstance(entries, dict):
            print(f"    {code}: rejected {origin}: expected an object", flush=True)
            continue
        for key, value in entries.items():
            if key not in en:
                continue
            reason = validation_error(en[key], value)
            if reason:
                print(f"    {code}: rejected {origin} {key!r}: {reason}; retrying", flush=True)
            else:
                validated[key] = value
    have = validated
    todo = [(p, v) for p, v in en.items() if p not in have]
    if args.dry_run:
        print(f"  {code}: would translate {len(todo)}; materialize validated literals")
        return

    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    merged = dict(have)
    print(f"  {code}: {len(todo)} literals in {len(chunks)} chunks", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(translate_chunk, c, names.get(code, code), env): c
                for c in chunks}
        done = 0
        for f in as_completed(futs):
            merged.update(f.result())
            done += 1
            # Persist as we go: a 1938-key locale is ~35 minutes of model
            # time, and a crash must not throw that away.
            atomic_write(cache_path, json.dumps(merged, ensure_ascii=False, indent=1))
            if done % 10 == 0:
                print(f"    {code}: {done}/{len(chunks)} chunks", flush=True)

    # A full cache must still be materialized. Mature modules, however, may
    # contain functions, spreads and imported field-copy data that are absent
    # from the static AST extraction. Never regenerate those as static-only.
    atomic_write(cache_path, json.dumps(merged, ensure_ascii=False, indent=1))
    path = I18N / f"{code}.ts"
    ident = code.replace("-", "_")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        match = re.fullmatch(
            r"import \{ defineLocale \} from './define-locale'\n"
            r"(?:\n|//[^\n]*\n)*export const (\w+) = defineLocale\(\{(.*)\}\)\n?",
            text, re.S)
        generated = bool(match and (
            not match.group(2).strip()
            or ("// interpolated template strings still fall back to English.\n" in text
                and match.group(2).strip() == render(unflatten(existing)).strip())
        ))
        if not generated:
            unchanged_tokens = sum(value.strip() == en[key].strip() for key, value in merged.items())
            print(f"  {code}: mature module preserved; {len(merged)}/{len(en)} validated "
                  f"literals in cache, not applied to module; {len(en) - len(merged)} gaps; "
                  f"{unchanged_tokens} unchanged machine tokens", flush=True)
            return
        ident = match.group(1)
    body = (
        "import { defineLocale } from './define-locale'\n\n"
        f"// {names.get(code, code)} ({code}): static literals translated;\n"
        "// interpolated template strings still fall back to English.\n"
        f"export const {ident} = defineLocale({{\n"
        f"{render(unflatten(merged))}\n"
        "})\n"
    )
    atomic_write(path, body)
    unchanged_tokens = sum(value.strip() == en[key].strip() for key, value in merged.items())
    print(f"  {code}: {len(merged)}/{len(en)} validated literals; "
          f"{unchanged_tokens} unchanged machine tokens; {len(en) - len(merged)} gaps", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
