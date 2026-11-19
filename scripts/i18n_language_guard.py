"""Audit + repair a locale catalog that was filled with the wrong language.

Failure found in `ae.ts` (Avestan): ~82% of its values were Azerbaijani, ~18%
Avestan. A user who picks Avestan reads Turkish.

Two modes:
  check  -> report how much of a locale is in a language that is not its own
  repair -> replace values carrying another language's markers with the English
            source string (the documented fallback), keeping native values

The parser is a small tokenizer rather than line regexes: catalogs contain
inline objects (`light: { label: 'Light' }`), arrow callbacks returning
template literals (``toggleFailed: (n) => `Failed ${n}` ``) and nested blocks.
A line-regex parser silently skips the last two — and those were exactly the
values that survived the first repair pass.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

I18N = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src" / "i18n"
AVESTAN = re.compile(r"[\U00010B00-\U00010B3F]")

# Markers of Turkic languages (Azerbaijani specifically, given the content):
# schwa, dotless/dotted i, and the Turkish-specific consonants. ASCII `I` is
# deliberately NOT here — it flagged every English sentence starting with "If".
TURKIC = set("əğıöüşçƏĞİÖÜŞÇ")

KEY_RE = re.compile(r"[A-Za-z_$][\w$]*")


class Token:
    """One parsed scalar value with the source span needed to replace it."""

    __slots__ = ("path", "start", "end", "quote", "value")

    def __init__(self, path: str, start: int, end: int, quote: str, value: str):
        self.path, self.start, self.end = path, start, end
        self.quote, self.value = quote, value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.path!r}, {self.quote!r}, {self.value[:24]!r})"


def parse(src: str) -> list[Token]:
    """Extract every string-valued property with its dotted path and span.

    Handles single quotes, double quotes and template literals, in objects,
    arrays, inline objects and arrow callbacks.

    Two traps this must survive:

    * ``disabled: (name: string) => `Off: ${name}` `` — a parameter type
      annotation looks exactly like a property (identifier + colon). Without
      paren tracking, ``name:`` becomes the "key" and the real value is
      attached to the wrong path (or dropped entirely, which is how 455
      Azerbaijani template values escaped the first repair pass).
    * object *keys* must never be recorded as values.
    """
    tokens: list[Token] = []
    stack: list[str] = []
    paren_depth = 0
    pending_key: str | None = None
    expect_key = False
    i, n = 0, len(src)

    while i < n:
        ch = src[i]

        if ch == "{":
            stack.append(pending_key if pending_key is not None else "-")
            pending_key = None
            expect_key = True
            # A brace opens a fresh object context: any enclosing call
            # parentheses (`defineLocale({ ... })`) are irrelevant inside it.
            paren_depth = 0
            i += 1
            continue

        if ch == "}":
            if stack:
                stack.pop()
            pending_key = None
            expect_key = False
            paren_depth = 0
            i += 1
            continue

        if ch in "([":
            paren_depth += 1
            i += 1
            continue

        if ch in ")]":
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue

        # A key is an identifier followed by ':' at object level.
        if expect_key and paren_depth == 0 and (ch.isalpha() or ch in "_$"):
            m = KEY_RE.match(src, i)
            if m:
                j = m.end()
                while j < n and src[j] in " \t":
                    j += 1
                if j < n and src[j] == ":":
                    pending_key = m.group(0)
                    expect_key = False
                    i = j + 1
                    continue
                i = m.end()
                continue

        if ch in "'\"`":
            quote = ch
            j = i + 1
            buf = []
            while j < n:
                c = src[j]
                if c == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if c == quote:
                    break
                buf.append(c)
                j += 1
            if pending_key is not None:
                path = ".".join([p for p in stack if p != "-"] + [pending_key])
                tokens.append(Token(path, i, j + 1, quote, "".join(buf)))
                pending_key = None
            expect_key = False
            i = j + 1
            continue

        if ch == ",":
            expect_key = True
            i += 1
            continue

        i += 1

    return tokens


def values_by_path(path: Path) -> dict[str, str]:
    return {t.path: t.value for t in parse(path.read_text(encoding="utf-8"))}


def is_foreign(text: str) -> bool:
    """True when the value is visibly in a Turkic language."""
    if AVESTAN.search(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3:
        return False
    return any(c in TURKIC for c in letters)


def check(code: str, verbose: bool = True) -> int:
    path = I18N / f"{code}.ts"
    en = values_by_path(I18N / "en.ts")
    tokens = parse(path.read_text(encoding="utf-8"))
    foreign = [t for t in tokens if is_foreign(t.value)]
    native = [t for t in tokens if AVESTAN.search(t.value)]
    english = [t for t in tokens if en.get(t.path) == t.value]
    if verbose:
        print(f"{code}.ts: {len(tokens)} values | native script {len(native)} | "
              f"english-source {len(english)} | foreign {len(foreign)}")
        for t in foreign[:8]:
            print(f"   FOREIGN {t.path} = {t.value[:64]}")
    return 0 if not foreign else 1


def repair(code: str, dry: bool = False) -> int:
    path = I18N / f"{code}.ts"
    src = path.read_text(encoding="utf-8")
    en = values_by_path(I18N / "en.ts")
    tokens = parse(src)

    edits: list[tuple[int, int, str]] = []
    missing = 0
    for t in tokens:
        if not is_foreign(t.value):
            continue
        if t.path not in en:
            missing += 1
            continue
        repl = en[t.path]
        if t.quote == "'":
            repl = repl.replace("\\", "\\\\").replace("'", "\\'")
        elif t.quote == '"':
            repl = repl.replace("\\", "\\\\").replace('"', '\\"')
        # template literal: keep ${...} interpolations live, escape the rest
        repl = repl.replace("\\", "\\\\").replace(t.quote, "\\" + t.quote) \
            if t.quote == "`" else repl
        edits.append((t.start, t.end, t.quote + repl + t.quote))

    for start, end, text in sorted(edits, reverse=True):
        src = src[:start] + text + src[end:]

    if not dry:
        path.write_text(src, encoding="utf-8")
    print(f"{code}: replaced {len(edits)} foreign value(s) with the English "
          f"source; {missing} had no English counterpart; dry={dry}")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    code = sys.argv[2] if len(sys.argv) > 2 else "ae"
    if mode == "check":
        raise SystemExit(check(code))
    if mode == "repair":
        raise SystemExit(repair(code, dry="--dry" in sys.argv))
    print(__doc__)
    raise SystemExit(2)
