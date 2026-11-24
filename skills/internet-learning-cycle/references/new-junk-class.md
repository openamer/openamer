# Adding a new junk class to the learner gate

Learned the hard way on 22.09.26 while gating **class 142** (article
byline/dateline chrome). Each of the four rules below cost a cycle or a scare.

## The leak

`cycle_a_technews` stored a page header as knowledge:

```
Written by Gus Mallett Published on April 29, 2026 Key Takeaways PocketOS,
a company that designs software for car rental businesses, had its entire
database mistakenly wiped by an AI agent .
```

The dates and the numeral in `11 min read` satisfy the technical-signal gate,
so **the page's voice is the only reliable discriminator**.

`_is_byline_published_article_header` (class 40) misses every shape here: it
requires a *leading* byline, while these pages lead with a headline
(`NVIDIA RTX PRO 5500 Blackwell: … 11 min read Sep 15, 2026`), with the date
(`April 29, 2026 Key Takeaways …`), or with a comment affordance
(`OpenClaw Like Like Posted by kim Bruning | February 13, 2026, 5:05 pm
Reply to this comment ps.`). 4 of 276 `online_buffer` rows carried the class.

## Rule 1 — Gate BOTH paths

`internet_learner._is_junk` (extractor) **and** `buffer_store.is_junk`
(writer). Fixing only one leaves the cycle spending itself on a write the
writer drops — that is the class-26 convention. The regression test must
assert both:

```python
assert IL._is_junk(leak), leak
assert IL._clean_insight(leak) == "", leak
assert BS.is_junk(leak), leak
```

## Rule 2 — Case-SENSITIVE affordances, header-region only

A case-insensitive `Published on` fired on genuine prose:

```
The photo credit reads Getty Images; the article it illustrates was
published on April 29, 2026 and updated later that day.
```

These are **rendered page labels** — match the page's capitalisation.
Require an affordance **AND** a full dateline, both inside the first 200
chars:

```python
_ARTICLE_BYLINE_AFFORDANCE_RE = re.compile(
    r"(?:\bKey Takeaways\b)"
    r"|(?:\bWritten by\s+[A-Z])"
    r"|(?:\bReply to this comment\b)"
    r"|(?:\bPosted by\s+[A-Z][\w.\-]*\s*\|)"
    r"|(?:\b\d{1,3} min read\b)"          # NO re.I
)
_ARTICLE_DATELINE_RE = re.compile(
    r"(?:\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"\d{1,2},?\s+20\d\d\b)"
    r"|(?:20\d\d-\d{2}-\d{2})"
    r"|(?:\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+20\d\d\b)",
)
```

## Rule 3 — Measure before you patch

Extract **every** string literal in both test files and assert the candidate
gates the leaks while hitting **zero** non-chrome literals:

```python
import ast
tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
lits = [n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and len(n.value) >= 30]
```

The suite's prose controls *are* the spec — guessing the regex overfires on
them. Measured for class 142: **5/5 leaks, 0/5 prose controls, 0/1,301 test
literals that are not chrome, 0/3,064 longterm_episodes, 83/8,836
already-refused buffer_junk rows.**

## Rule 4 — Select backups by mtime, never by sort

```python
# WRONG — picked internet_learner.py.bak.cls35 (17.09) over today's backup
# and silently reverted a 300 KB file to 129 KB
backup = sorted(D.glob("internet_learner.py.bak.*"))[-1]

# RIGHT
backups = sorted(D.glob("internet_learner.py.bak.20260922_*"),
                 key=lambda p: p.stat().st_mtime, reverse=True)
raw = backups[0].read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "not pure CRLF"
assert len(raw) > 250000, "backup too small: %d" % len(raw)
```

When inserting into a pure-CRLF file, join the new lines with `"\r\n"` —
`"\n".join(...)` leaves bare-LF behind. Verify with:

```bash
python -c "d=open(F,'rb').read(); print('CRLF',d.count(b'\r\n'),'bare-LF',d.count(b'\n')-d.count(b'\r\n'))"
```

## Rule 5 — Sync, then verify the remote hash

The repo copy (`~/openamer-repo`) and the live cron copy
(`$OPENAMER_HOME/scripts/training/`) are **separate files**. `md5sum` both
*before* copying so you know the copy is a real subset-diff and not a clobber
of newer live work; `md5sum` again after to confirm agreement.

**Sync the TEST file too, not just the modules.** 22.09.26: the two modules
were synced but `tests/scripts/test_internet_learner_gate.py` was not, so the
live suite still collected **170** while the repo collected **172**. The fix
looked unverified from the live tree and the two new regression tests were
missing exactly where cron runs. Before syncing, confirm the live test file is
the untouched pre-patch version (`git show HEAD~1:<path> | md5sum` must equal
the live file) — then the copy is a clean forward update.

A count mismatch between live and repo is the tell. Always compare
`--collect-only -q` counts, not just pass/fail.

Then confirm the push landed — `git ls-remote` must print the local HEAD hash:

```bash
git ls-remote origin refs/heads/<branch>
git rev-parse HEAD
```

Finish with a **negative control**: load the pre-patch modules from
`git show HEAD~1:<path>` in a temp dir and assert the leak is *not* gated
there. A suite that passes both before and after proves nothing.
