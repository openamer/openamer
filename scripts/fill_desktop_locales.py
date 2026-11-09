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
import json
import os
import re
import subprocess
import sys
import urllib.request
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
    ("ollama-deepseek", "https://ollama.com/v1/chat/completions", "OLLAMA_API_KEY", "deepseek-v4.1-flash"),
    ("ollama-minimax", "https://ollama.com/v1/chat/completions", "OLLAMA_API_KEY", "minimax-m3.1-flash"),
]

KEY_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")


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


def unflatten(flat: dict[str, str]) -> dict:
    tree: dict = {}
    for path, value in flat.items():
        parts = path.split(".")
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    return tree


def js(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


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
    if "ollama.com" in url:
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


def translate_chunk(items: list[tuple[str, str]], lang_name: str, env: dict) -> dict[str, str]:
    listing = "\n".join(f"{i}. {v}" for i, (_, v) in enumerate(items))
    prompt = (
        f"Translate these desktop UI strings into {lang_name}.\n"
        "Rules:\n"
        "- Output ONLY a JSON object mapping the index number (as a string) to the translation.\n"
        "- These are short interface labels (buttons, headings, hints). Keep them short.\n"
        "- Keep the literal characters \\n if present. Keep {placeholders} exactly.\n"
        "- Keep 'OpenAmer', file paths, URLs, and code in backticks unchanged.\n"
        "- Every index must appear exactly once. No explanations.\n\n"
        f"{listing}"
    )
    for cand in BACKENDS:
        name, url, keyenv, model = cand
        key = env.get(keyenv, "")
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
        out = {}
        for i, (path, src) in enumerate(items):
            got = obj.get(str(i))
            if isinstance(got, str) and got.strip():
                out[path] = got.strip()
        if len(out) == len(items):
            return out
    return {}


def existing_overrides(code: str) -> dict[str, str]:
    """Literal overrides already present in the module (flat)."""
    path = I18N / f"{code}.ts"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if "defineLocale({})" in text:
        return {}
    return {k: v for k, v in parse_literals(text).items()}


def parse_literals(text: str) -> dict[str, str]:
    out, stack = {}, []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = KEY_RE.match(line)
        if not m:
            if line.strip() in ("}", "},"):
                if stack:
                    stack.pop()
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3).strip()
        if rest.startswith("{"):
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, key))
            continue
        sm = re.fullmatch(r"""(["'])((?:[^\\]|\\.)*)\1,?""", rest)
        if sm and stack:
            out[".".join([k for _, k in stack] + [key])] = sm.group(2)
    return out


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
        cache_path = HOME / "tmp" / f"desktop_{code}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        have: dict[str, str] = {}
        if cache_path.exists():
            try:
                have = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                have = {}
        have.update(existing_overrides(code))
        todo = [(p, v) for p, v in en.items() if p not in have]
        if not todo:
            print(f"  {code}: complete")
            continue
        if args.dry_run:
            print(f"  {code}: would translate {len(todo)}")
            continue

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
                cache_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")
                if done % 10 == 0:
                    print(f"    {code}: {done}/{len(chunks)} chunks", flush=True)

        path = I18N / f"{code}.ts"
        ident = code.replace("-", "_")
        if path.exists():
            m = re.search(r"^export const (\w+)", path.read_text(encoding="utf-8"), re.M)
            if m:
                ident = m.group(1)
        body = (
            "import { defineLocale } from './define-locale'\n\n"
            f"// {names.get(code, code)} ({code}): static literals translated;\n"
            "// interpolated template strings still fall back to English.\n"
            f"export const {ident} = defineLocale({{\n"
            f"{render(unflatten(merged))}\n"
            "})\n"
        )
        path.write_text(body, encoding="utf-8", newline="\n")
        print(f"  {code}: {len(merged)}/{len(en)} literals", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
