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

# Per-locale characters that CANNOT occur in that language. A value holding one
# was written in some other language — measured, not guessed:
#   mi.ts (Maori) held Polish    -> "Kopiowanie nie powiodło się", "Delegowanie"
#   ae.ts (Avestan) held Turkic  -> "Söndür", "Yenidən skan et"
#   ps.ts (Pashto) held Romanian -> Latin sentences in an Arabic-script catalog
FORBIDDEN_CHARS: dict[str, set[str]] = {
    "mi": set("ąćęłńśźżĄĆĘŁŃŚŹŻ"),   # Polish diacritics: impossible in Maori
    "ae": TURKIC,
    "ha": set("ąćęłńźżĄĆĘŁŃŹŻ"),     # Hausa writes ɓ ɗ ƙ, never Polish marks
}

# Locales whose writing system is not Latin at all: a Latin sentence in one of
# these is foreign by definition. Mirrors i18n_verify_locales.NON_LATIN_SCRIPT.
NON_LATIN_SCRIPT = {
    "ar": r"[\u0600-\u06FF\u0750-\u077F]",
    "fa": r"[\u0600-\u06FF\u0750-\u077F]",
    "ps": r"[\u0600-\u06FF\u0750-\u077F]",
    "ur": r"[\u0600-\u06FF\u0750-\u077F]",
    "he": r"[\u0590-\u05FF]",
    "yi": r"[\u0590-\u05FF]",
    "ru": r"[\u0400-\u04FF]",
    "uk": r"[\u0400-\u04FF]",
    "bg": r"[\u0400-\u04FF]",
    "sr": r"[\u0400-\u04FF]",
    "mk": r"[\u0400-\u04FF]",
    "el": r"[\u0370-\u03FF]",
    "hi": r"[\u0900-\u097F]",
    "mr": r"[\u0900-\u097F]",
    "ne": r"[\u0900-\u097F]",
    "th": r"[\u0E00-\u0E7F]",
    "ko": r"[\uAC00-\uD7AF\u1100-\u11FF]",
    "zh": r"[\u4E00-\u9FFF]",
    "ja": r"[\u3040-\u30FF\u4E00-\u9FFF]",
}

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


def is_foreign(text: str, locale: str = "ae") -> bool:
    """True when the value is visibly not written in ``locale``'s language.

    Two independent signals, both measured on real breakage:

    * a character that cannot occur in the language (Polish diacritics in Maori,
      Turkish letters in Avestan) — decisive when present;
    * a Latin sentence in a catalog that uses a different writing system
      (Romanian in Pashto) — decisive for non-Latin targets.

    Default ``locale='ae'`` keeps the original Turkic check callable on its own.
    """
    if not isinstance(text, str):
        return False
    if AVESTAN.search(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3:
        return False

    forbidden = FORBIDDEN_CHARS.get(locale)
    if forbidden and any(c in forbidden for c in text):
        return True

    pattern = NON_LATIN_SCRIPT.get(locale)
    if pattern and len(letters) >= 4 and not re.search(pattern, text):
        return True

    return False


def check(code: str, verbose: bool = True) -> int:
    path = I18N / f"{code}.ts"
    en = values_by_path(I18N / "en.ts")
    tokens = parse(path.read_text(encoding="utf-8"))
    foreign = [t for t in tokens
               if t.value != en.get(t.path) and is_foreign(t.value, code)]
    native = [t for t in tokens if AVESTAN.search(t.value)]
    english = [t for t in tokens if en.get(t.path) == t.value]
    if verbose:
        print(f"{code}.ts: {len(tokens)} values | native script {len(native)} | "
              f"english-source {len(english)} | foreign {len(foreign)}")
        for t in foreign[:8]:
            print(f"   FOREIGN {t.path} = {t.value[:64]}")
    return 0 if not foreign else 1


def _reencode(value: str, quote: str) -> str:
    """Re-delimit an already-escaped TS string value for a different quote.

    The value comes out of the *source text*, so it is already escaped for
    TypeScript. Escaping it again is a bug, not a safety net: a template holding
    a real newline came back as a literal backslash-n and the UI printed "\\n".
    Only the delimiter conflict is handled here — the target quote must be
    escaped (and backticks / `${` when the target is not a template).
    """
    SENTINEL = "\x00"
    if quote == "`":
        # Inside a template literal a bare backtick ends the string.
        return value.replace("\\`", SENTINEL).replace("`", "\\`").replace(SENTINEL, "\\`")
    if quote == "'":
        return value.replace("\\'", SENTINEL).replace("'", "\\'").replace(SENTINEL, "\\'")
    if quote == '"':
        return value.replace('\\"', SENTINEL).replace('"', '\\"').replace(SENTINEL, '\\"')
    return value  # pragma: no cover - defensive


def repair(code: str, dry: bool = False) -> int:
    path = I18N / f"{code}.ts"
    src = path.read_text(encoding="utf-8")
    en = values_by_path(I18N / "en.ts")
    tokens = parse(src)

    edits: list[tuple[int, int, str]] = []
    missing = 0
    for t in tokens:
        if t.value == en.get(t.path) or not is_foreign(t.value, code):
            continue
        if t.path not in en:
            missing += 1
            continue
        repl = _reencode(en[t.path], t.quote)
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
