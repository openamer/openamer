# The leading-chrome STRIP family (classes 12–16), live 16.09.26

Every row below was learned by a real `internet_learner.py --once` cycle and
cleared BOTH gates before being fixed. Class 12–15 are page furniture WELDED to
real prose → **STRIP** (the body is the knowledge). Class 16 is genuine chrome →
**REJECT**. Verbatim strings and the measured counter-cases are kept here so a
future session does not have to re-derive them.

## Class 12 — MediaWiki section-edit control

Learned (`cycle_g_security`):

```
Publications [ edit ] OWASP Top Ten The "Top Ten", first published in 2003 and
updated periodically (subsequent editions appeared in 2004, 2007, 2010, 2013,
2017, 2021 and 2025), is a listing of the most critical application security risks.
```

Fix: `_strip_wiki_section_prefix` (learner) + `_WIKI_EDIT_WORD_RE` (writer mirror),
wired first in `_clean_insight`.

Guards:
1. the leading section name must be **sentence case and apostrophe-free**
   (`Publications`, never `Wikipedia's`). The possessive cannot match at all —
   that is what keeps the counter-case alive.
2. the body after the marker must **open a sentence** (uppercase, digit, quote).
   An edit control is always followed by the article's first sentence; a lowercase
   continuation means the text MENTIONS an edit button.
3. leading position only (`re.match`) and a ≥ 5-word body must remain.

The edit word itself is localized and case-tolerant
(`edit|bearbeiten|editieren|source edit|modifier|modifica|bewerken|rediger|
redigera|muokkaa|edytuj|szerkesztés`); guard 1 rests on the NAME rule
deliberately NOT being case-insensitive.

**The bug the first version shipped** (caught by a counter-case before commit):
a `[A-Za-z]...` name prefix gutted the real sentence
`"Wikipedia's [ edit ] button is a MediaWiki control, not content; the RAG
pipeline should strip it before chunking documents for retrieval."` down to
`"button is a MediaWiki control, …"`. Two changes fixed it: the sentence-case
name rule, and replacing the `"[ edit ]"` entry in `buffer_store._NAV_CHROME`
(which had introduced the same damage at the writer gate) with the anchored rule.
**A blanket marker for a STRIP class is always wrong.**

## Class 13 — leading lowercase clock-dateline fragment

Learned (`cycle_e_competitors`):

```
at 11:44 am we asked four ai coding agents to In a recent experiment, four AI
coding agents were tasked with recreating the classic game Minesweeper, revealing
both the potential and limitations of modern AI in programming.
```

Fix: `_strip_dateline_fragment`, using `_DATELINE_FRAGMENT_RE =
r"^at\s+\d{1,2}:\d{2}\s*(?:am|pm)\b\s*"` (deliberately **not** case-insensitive),
boundary = first Capitalized token after the dateline, ≥ 5-word body required.

Counter-cases (all must stay untouched AND learnable):
- `"At 12:30 pm the batch job starts, so schedule the quantization sweep before noon."`
- `"The run finished at 11:44 am and the quantized model had lower latency."`
- `"at 11:44 we measured 40% lower decode latency, but the sentence has no am/pm marker."`

Note: a parallel cron independently added `_strip_clock_fragment` for the same
shape in the same session — check for an existing sibling before adding a new one.

## Class 14 — label-only nav stack terminated by a dateline

Learned (`cycle_g_security`):

```
SECURITY resources Whitepapers/Guides OWASP GenAI LLM Top 10 2026 August 3, 2026
About OWASP Top 10 for LLM Applications 2026 is the latest community-driven guide
to the most critical security risks facing applications powered by large language
models.
```

Fix: `_strip_nav_label_stack` + `_NAV_LABEL_STACK_RE` + `_NAV_LABEL_FUNC_WORDS`.

**Measured-and-REJECTED candidate (keep in the record):** the generic shape
`<nav-run> <date> <body>` matched **5 corpus rows** — four of them GitHub-advisory
prose that must survive:

```
Critical Authenticated Arbitrary Data Export Theft via Mass Assignment in
sendFileMessage GHSA-fhc2-x8cp-c5ch by julio-rocketchat High Previous 1 2 3 Next
Learn more about advisories.
```

plus two hand-written counter-cases. The surviving rule requires a
slash-joined Capitalized pair in the head AND `len(lowercase_words) <= 1` AND no
function word (`the/of/is/are/and/on/in/to/a/an/for/with/was/were/that/this/at/by/as/it`).
Result: 1 hit (the leaking row), 0 prose-like heads.

**Fixture trap that cost a cycle:** the GHSA row is rejected by the
**pre-existing** `_is_nav_list` rule (≥ 6 TitleCase tokens with no comma), not by
the new code. Do not assert it "learnable" and do not widen the new pattern to
rescue it — assert the strip leaves it byte-identical and note which rule gates it.

## Class 15 — leading byline stack (name + date + counters + Share)

Learned (`cycle_b_papers`):

```
Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: We show that LLM agents can figure
out who you are from your anonymous online posts.
```

Fix: `_strip_byline_stack` + `_BYLINE_STACK_RE`. The signature is the welded
ORDER: Name, `_DATE_ALT`, **bare** counters, then the widget's `Share` control.

Counter-cases (untouched):
- `"Alice Smith Jan 5, 2026 reported 40% lower decode latency in the quantized model."` (counters carry nouns → no match)
- `"The Feb 24, 2026 release of vLLM adds 3 new quantized kernels and 2 fixes."` (not anchored at the author)
- `"We show that LLM agents can figure out who you are from your anonymous online posts."`
- `"Simon Lermen Feb 24, 2026 54 5 8 TL;DR: …"` (no `Share` control → untouched)

**Silent-failure trap:** the first regex never matched because `_DATE_ALT` is
written in lowercase (`(?:jan|feb|…)`) and the pattern omitted `re.IGNORECASE`.
`py_compile` and the import both pass; only the delta showed `touched=0`.
Every other pattern built on `_DATE_ALT` in this file carries the flag.

## Class 16 — German bank referral/promo chrome (REJECT)

Learned (`cycle_c_github`):

```
Auch die neue Kundin oder der neue Kunde erhält eine Prämie von 300 €, was eine
Gesamtprämie von 600 € ergibt!
```

Both gates passed it: the euro amounts fed the technical-signal gate and 100
chars cleared the ≥ 25 length floor. This is a REJECT class — there is no body to
preserve.

Fix: new fragments in `internet_learner._JUNK_RE` **and** mirrored in
`buffer_store._NAV_CHROME` (every writer path must agree):
`prämie von|gesamtprämie|erhält eine prämie|neukundenprämie|kunden-werben|empfehlungsprämie`.

Keyed on the offer's OWN phrases, never on a bare `Prämie`/`Rabatt`/`Bonus`, so
counter-cases stay learnable:
- `"Der Rabatt auf die Cloud-GPU beträgt 30 %, was die Kosten pro Token senkt."`
- `"Quantization recovers 97% of fp16 accuracy at INT4 on the reasoning benchmark."`

Corpus check: 1 row hit (the leaking row), 0 real-prose rows.

**Delta-script trap:** do not disable the whole `_JUNK_RE` as the "old"
reference to isolate new fragments — that reports a dozen unrelated rows as
newly-rejected. Instead check which corpus rows contain the new fragments and
assert each of those is chrome (`_clean_insight(...) == ""`).

## Verification recipe used for every class

```bash
# 1. delta: NEW vs REF (identity-patched, same file) over buffer + junk log
#    -> newly_rejected = N (all junk), regressions = 0, touched = 1 body-pristine
# 2. suites
$OPENAMER_HOME/venv/Scripts/python.exe -m pytest \
    tests/scripts/test_internet_learner_gate.py scripts/training/test_internet_learner.py -q
#    -> 54 passed after classes 12-15
# 3. sync repo -> HOME, then ONE real cycle and read the LAST buffer row
cp ~/openamer-repo/scripts/training/internet_learner.py $OPENAMER_HOME/scripts/training/
python $OPENAMER_HOME/scripts/training/internet_learner.py --once
```

Each class landed with its own regression test in
`tests/scripts/test_internet_learner_gate.py`
(`test_wikipedia_section_edit_prefix_is_stripped_not_stored`,
`test_leading_clock_dateline_fragment_is_stripped_not_stored`,
`test_leading_nav_label_stack_is_stripped_not_stored`,
`test_leading_byline_stack_is_stripped_not_stored`,
`test_german_bank_promo_chrome_is_rejected`), each asserting the body is the
original minus the prefix AND carrying its counter-cases.

All edits were byte-level (read_bytes/write_bytes + CRLF conversion,
`assert b.count(anchor) == 1`, post-check `dblCR == 0`) — see
`eol-safe-editing`. `patch` on these CRLF files is risky; the temp-script +
`crlf()` pattern worked reliably.
