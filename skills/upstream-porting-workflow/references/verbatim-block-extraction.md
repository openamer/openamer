# Verbatim block extraction: porting a method body without retyping it

Companion to the SKILL.md section **"A port can drop METHODS, not just modules"**.
Measured 2026-10-13 on `plugins/platforms/feishu/adapter.py` (suite `22 → 19`).

Three methods missing, all reachable from the same class body:

| method | upstream (`origin/main`) | local |
|---|---|---|
| `_text_batch_key` | present | **absent** |
| `_flush_text_batch` | present | **absent** |
| `_flush_text_batch_now` | present | **absent** |
| `_text_batch_is_compatible`, `_enqueue_text_event`, `_schedule_text_batch_flush`, `_reschedule_batch_task`, `_pop_text_batch`, `_dispatch_text_batch` | present | present, **byte-identical, only sited differently** |

The last row is the load-bearing one: the local file was not "an older version"
of upstream. It was upstream **minus exactly three methods**, with one helper
(`_reschedule_batch_task`) moved a few lines. So the repair is three insertions and
zero rewrites — and any repair that relocates or rewrites the intact helpers is
doing more than the bug requires.

## Rule 1 — the source is the git OBJECT, not your transcription

Retyping a body from a `sed` preview drifts in whitespace, blank lines and
comments, and you cannot then *prove* the result is upstream's. Pull it:

```bash
git show origin/main:plugins/platforms/feishu/adapter.py > /tmp/up.py
```

Pick the revision by which question you are answering:

- **`origin/main`** — when the file already exists in this lineage and upstream is
  simply ahead (this case). Three methods were dropped; the rest of the file is
  already current.
- **`<port_commit>^`** — when the *port itself* rebuilt the file (the 2026-10-08
  case). The pre-port revision is the only place the dropped body exists.

## Rule 2 — extract by SYMBOL, not by line number

Line slicing is where this goes wrong. `sed -n 'A,Bp'` and a Python slice of
`split("\n")` disagree by one, and the off-by-one is *silent* when the dropped line
is a closer:

```python
# what I wrote, and what it cost
blk = "\n".join(up_lines[2808:2817])     # lines 2809..2817 — ONE LINE SHORT
# 2809  def _text_batch_key(self, event: MessageEvent) -> str:
# ...
# 2817  profile=event.source.profile,
# 2818  )                                  <- never included
```

The inserted text left `return build_session_key(` unterminated:

```
SyntaxError: '(' was never closed            (py_compile)
ruff: Expected ')', found newline  -->  adapter.py:2817:42
```

Extract by name instead — the block is `def NAME` plus its body, with any
immediately-preceding decorators:

```python
import re
def extract_block(lines, name):
    pat = re.compile(rf"^(\s*)(?:async\s+)?def\s+{re.escape(name)}\s*\(")
    for i, l in enumerate(lines):
        m = pat.match(l)
        if not m:
            continue
        indent = len(m.group(1))
        start = i
        while start > 0 and lines[start-1].strip().startswith("@"):   # decorators
            start -= 1
        end = i + 1
        while end < len(lines):
            if lines[end].strip() and len(lines[end]) - len(lines[end].lstrip()) <= indent:
                break                                                  # next sibling
            end += 1
        while end > start and not lines[end-1].strip():                 # drop trailing blanks
            end -= 1
        return lines[start:end]
    raise SystemExit(f"NOT FOUND upstream: {name}")
```

Name-based extraction cannot be off by one, which is exactly why it is the right
default. `scripts/port_block.py` implements it.

## Rule 3 — prove byte-identity after writing

Do not eyeball the result. Assert it:

```python
block_with_file_eol = "\n".join(block).replace("\n", "\r\n")
after = open(path, encoding="utf-8", newline="").read()
assert after.count(block_with_file_eol) == 1, after.count(block_with_file_eol)
```

Observed output — this is what "ported verbatim" looks like as a measurement:

```
_text_batch_key: present verbatim = True  (occurrences=1)
_flush_text_batch+now: present verbatim = True  (occurrences=1)
```

The `== 1` (not `>= 1`) matters: two occurrences means you duplicated the method
instead of inserting it.

## Rule 4 — keep the file's EOL, and verify it with bytes, not with `cat -A`

The file is `core.autocrlf=true` (pure CRLF: 4,316 CRLF lines, 0 bare LF). The
safe scripted round-trip, used twice here, is:

```python
raw  = open(path, "rb").read()
assert raw.count(b"\r") == raw.count(b"\r\n"), "lone CR present — stop and inspect"
text = raw.decode("utf-8")
lf   = text.replace("\r\n", "\n")          # edit in LF
lf   = lf.replace(anchor_old, anchor_new)  # exact counts asserted: assert lf.count(old) == 1
open(path, "wb").write(lf.replace("\n", "\r\n").encode("utf-8"))

d = open(path, "rb").read()
assert d.count(b"\r") == d.count(b"\r\n") == d.count(b"\n")   # still pure CRLF
assert d.count(b"\r\r") == 0                                  # no doubled CR
```

**The trap: `cat -A` did NOT show `^M` on this CRLF file.** The terminal output
rendered `return True$` and `    def _text_batch_key...$` with no `^M` marker, which
reads as LF-only — and would have sent the whole edit down the wrong path. The
byte counts are authoritative:

```
$ python -c "d=open('plugins/platforms/feishu/adapter.py','rb').read(); \
    print(d.count(b'\r\n'), d.count(b'\n')-d.count(b'\r\n'))"
4316 0
$ od -c plugins/.../adapter.py | head -3
0000000   "   "   "  \r  \n   F   e   i   s   h   u   /   L   a   r   k
```

So: verify line endings with `od -c`, a Python byte count, or `git config
core.autocrlf` — never with the rendered `cat -A` output through this terminal.
(The same class of blindness is noted in `crlf-normalization-windows.md`.)

## Rule 5 — lint before you sweep

A byte-level scripted edit gets **no editor syntax check**. The order that saves a
multi-minute test run:

```bash
ruff check plugins/platforms/feishu/adapter.py          # must print: All checks passed!
"$VENV/python.exe" -m py_compile plugins/platforms/feishu/adapter.py
git diff --stat plugins/platforms/feishu/adapter.py      # expect: N insertions(+), 0 deletions(-)
```

That is exactly what caught the dropped `)` above — ruff failed in under a second
with the precise line, before any test ran.

## Rule 6 — report the fixed class apart from the untouched ones

`22 → 19` is not a result on its own. Read the `E       ` lines of the failure block
and group them; then say which group you closed:

```
FAILED ...::test_text_batch_merges_rapid_messages_into_single_event      <- FIXED (ported)
FAILED ...::test_text_batch_flushes_when_message_count_limit_is_hit      <- FIXED (ported)
FAILED ...::test_media_batch_merges_rapid_photo_messages                 <- FIXED (`_text_batch_key`)

E  AttributeError: 'FeishuAdapter' object has no attribute '_build_post_payload'   x6
      -> a DIFFERENT dropped method (upstream has 1 def, local 0)
E  AssertionError: <coroutine object FeishuAdapter._is_duplicate ...> is not false x2
      -> `_is_duplicate` is `async def` in BOTH lineages; the TEST asserts on the
         un-awaited coroutine (test-side async mismatch, not a port gap)
E  AssertionError: False is not true                                     x4  (connect/lock/UA)
E  AssertionError: 'ou_env' != 'ou_probe_DIFFERENT'                      x3  (hydration)
E  KeyError: 'ou_nameless' / None != 'Peer Bot'                          x2  (bot name)
```

Two of those are *near misses* worth naming explicitly, because a reader will
assume they share the cause you just fixed:

- `_build_post_payload` is a **sibling dropped method** — same bug class, different
  symbol. Do not silently fix it inside a task scoped to the text-batch methods; it
  is the next task, and it is cheap now that the extraction recipe is known.
- `_is_duplicate` is **not** a port gap at all: the grep proves the `async def` is
  identical on both sides, so the drift is in the test's call shape. Saying so
  prevents the next agent from "restoring" a method that was never missing.

## Checklist

1. `git show <rev>:<path> > /tmp/up.py` — object, not transcription.
2. Extract each symbol by name (`scripts/port_block.py`), never by line range.
3. Insert; keep existing identical helpers in place. Expect `N insertions(+), 0
   deletions(-)`.
4. `ruff check` + `py_compile` — before the sweep, not after.
5. Byte-identity assertion: `count(block) == 1` for each block.
6. EOL assertion: `\r == \r\n == \n`, no `\r\r`. Verify with bytes or `od -c`,
   never `cat -A`.
7. Run the canonical sweep; report before → after **and** the per-root-cause
   grouping of what is left.
