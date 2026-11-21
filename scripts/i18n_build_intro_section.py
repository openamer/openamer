#!/usr/bin/env python3
"""Generate the `intro` i18n section from the legacy intro-copy.jsonl.

The desktop intro copy lived in `apps/desktop/src/components/chat/intro-copy.jsonl`
as hardcoded English, outside the i18n catalog: 15 personalities x 5 lines x 2
fields = 150 user-visible strings that no locale could ever reach. This script
turns that file into a normal i18n section so the existing extract/translate/
audit pipeline covers it.

Also emits the two copy blocks that were hardcoded in intro.tsx itself
(FALLBACK_COPY and the `${label}` persona-mode templates).

    python scripts/i18n_build_intro_section.py --print   # show the TS block
    python scripts/i18n_build_intro_section.py --write    # patch en.ts + types.ts
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
DESKTOP = REPO / "apps/desktop/src"
JSONL = DESKTOP / "components/chat/intro-copy.jsonl"

# Neutral first: it is the block every user sees when no personality is set.
ORDER_FIRST = ["none"]

IDENT = re.compile(r"^[a-z][a-z0-9]*$")

FALLBACK = [
    {
        "headline": "What are we moving today?",
        "body": "Send a bug, branch, plan, or rough idea. I'll inspect the repo and turn it into the next concrete step.",
    },
    {
        "headline": "What's on your mind?",
        "body": "Bring the code, question, or stuck part. I'll read the room before making changes.",
    },
    {
        "headline": "What should OpenAmer look at?",
        "body": "Send the task, failing path, or half-formed plan. I'll help turn it into action.",
    },
    {
        "headline": "Where should we start?",
        "body": "Bring the problem, goal, or file. I'll inspect first and keep the next step concrete.",
    },
    {
        "headline": "What needs attention?",
        "body": "Send the context you have. I'll help sort it into a plan or a fix.",
    },
]

PERSONA_MODE = [
    ("${label} mode is on. What should we work on?",
     "Send the task, file, or rough idea. I'll use your configured voice and keep the work grounded in this repo."),
    ("What does ${label} OpenAmer need to see?",
     "Bring the context or the stuck part. I'll adapt to your configured personality."),
    ("${label} mode is ready.",
     "Send the problem, file, or idea. I'll follow the personality you've configured."),
    ("What should ${label} OpenAmer tackle?",
     "Drop the task here. I'll keep the work grounded in the repo."),
    ("Where should we begin?",
     "Give me the context and I'll answer in ${label} mode."),
]


def load_copy() -> dict[str, list[dict[str, str]]]:
    by_persona: dict[str, list[dict[str, str]]] = {}
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        by_persona.setdefault(rec["personality"], []).append(
            {"headline": rec["headline"].strip(), "body": rec["body"].strip()}
        )
    return by_persona


def persona_order(by_persona: dict[str, list[dict[str, str]]]) -> list[str]:
    rest = sorted(k for k in by_persona if k not in ORDER_FIRST)
    return [k for k in ORDER_FIRST if k in by_persona] + rest


def ts_str(value: str, quote: str = "'") -> str:
    out = value.replace("\\", "\\\\")
    if quote == "'":
        out = out.replace("'", "\\'")
    else:
        out = out.replace('"', '\\"')
    # ${...} must survive as literal text: escape the dollar so TS keeps it.
    out = out.replace("${", "\\${")
    return f"{quote}{out}{quote}"


def copy_block(name: str, entries: list[dict[str, str]], indent: str) -> str:
    inner = indent + "  "
    headlines = "\n".join(f"{inner}  {ts_str(e['headline'])}," for e in entries)
    bodies = "\n".join(f"{inner}  {ts_str(e['body'])}," for e in entries)
    return (
        f"{indent}{name}: {{\n"
        f"{inner}headlines: [\n{headlines}\n{inner}],\n"
        f"{inner}bodies: [\n{bodies}\n{inner}]\n"
        f"{indent}}},\n"
    )


def build_section(indent: str = "  ") -> str:
    by_persona = load_copy()
    order = persona_order(by_persona)
    inner = indent + "  "
    parts = [f"{indent}intro: {{\n", f"{inner}personas: {{\n"]
    for key in order:
        if not IDENT.match(key):
            raise SystemExit(f"persona key is not a TS identifier: {key!r}")
        parts.append(copy_block(key, by_persona[key], inner + "  "))
    parts.append(f"{inner}}},\n")
    parts.append(copy_block("fallback", FALLBACK, inner))
    pm = inner + "  "
    heads = "\n".join(f"{pm}  {ts_str(h)}," for h, _ in PERSONA_MODE)
    bodies = "\n".join(f"{pm}  {ts_str(b)}," for _, b in PERSONA_MODE)
    parts.append(
        f"{inner}personaMode: {{\n"
        f"{pm}headlines: [\n{heads}\n{pm}],\n"
        f"{pm}bodies: [\n{bodies}\n{pm}]\n"
        f"{inner}}}\n"
    )
    parts.append(f"{indent}}},\n")
    return "".join(parts)


def build_types(order: list[str]) -> str:
    keys = " | ".join(f"'{k}'" for k in order)
    return (
        "export interface IntroCopyBlock {\n"
        "  headlines: readonly string[]\n"
        "  bodies: readonly string[]\n"
        "}\n"
        "\n"
        f"export type IntroPersona = {keys}\n"
    )


def patch_types(order: list[str]) -> None:
    path = DESKTOP / "i18n/types.ts"
    text = path.read_text(encoding="utf-8")
    if "export interface IntroCopyBlock" not in text:
        anchor = "export interface Translations {"
        text = text.replace(anchor, build_types(order) + "\n" + anchor, 1)
    if "  intro: {\n" not in text:
        block = (
            "  intro: {\n"
            "    personas: Record<IntroPersona, IntroCopyBlock>\n"
            "    fallback: IntroCopyBlock\n"
            "    personaMode: IntroCopyBlock\n"
            "  }\n"
        )
        # Insert before the last section (`ui`) so the closing brace stays last.
        idx = text.rindex("\n  ui: {")
        text = text[:idx] + "\n" + block + text[idx:]
    path.write_text(text, encoding="utf-8", newline="")
    print(f"patched {path.relative_to(REPO)}")


def patch_en() -> None:
    path = DESKTOP / "i18n/en.ts"
    text = path.read_text(encoding="utf-8")
    if re.search(r"^  intro: \{", text, re.M):
        print("en.ts already carries an intro section — nothing to insert")
        return
    idx = text.rindex("\n  ui: {")
    text = text[:idx] + "\n" + build_section() + text[idx:]
    path.write_text(text, encoding="utf-8", newline="")
    print(f"patched {path.relative_to(REPO)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    by_persona = load_copy()
    order = persona_order(by_persona)
    strings = sum(len(v) for v in by_persona.values()) * 2 + len(FALLBACK) * 2 + len(PERSONA_MODE) * 2
    print(f"personas: {len(by_persona)}  strings: {strings}  order: {order}")
    if args.print:
        print(build_section())
    if args.write:
        patch_types(order)
        patch_en()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
