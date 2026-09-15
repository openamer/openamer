#!/usr/bin/env python3
"""Buffer Store — single source of truth for the online experience buffer.

Every writer (active_learn, internet_learner, online_learning.collect_new)
must append through `append()` so the cap is enforced on EVERY write, not
only in the replay branch. Before this module the cap lived inside
online_learning's replay path, so any cycle that produced new data grew the
buffer without bound (training on unbounded duplicates degrades loss).

Cap policy: keep the newest MAX_BUF examples, FIFO. Trimming is
best-effort/atomic-ish (write temp + replace) and never raises into callers —
a failed trim must not break a learning cycle.

Quality policy (added 11.09.26): the buffer is TRAINING DATA. Three classes
of non-signal were observed live in online_buffer.jsonl and are now rejected
before they can be written, because a LoRA fine-tuned on them learns the
garbage:

  1. reasoning-trace leaks  — thinking models emit "Here's a thinking
     process:" / "Analyze User Input:" into the completion (64 of 300
     entries on 11.09.26).
  2. degenerate repetition  — "Self\\n\\nSelf\\n\\nSelf..." (20 of 300):
     the model repeating one token; unique-token ratio near zero.
  3. raw tool-call JSON     — the completion is `{"tool": "web_search", ...}`
     instead of an answer (28 of 300).

`is_junk()` is the single predicate; `append()` refuses junk and returns the
unchanged count. Callers that need to report honestly check `is_junk()` (or
the count delta) rather than assuming their write landed.
"""
from collections import Counter
import json
import os
from pathlib import Path

_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    Path.home() / "AppData" / "Local" / "openamer-laptop",
))
DEFAULT_BUFFER = _HOME / "scripts" / "training" / "online_buffer.jsonl"
MAX_BUF = int(os.environ.get("OPENAMER_BUFFER_MAX", "300"))
# audit trail of rejected examples — never silent, always inspectable
JUNK_LOG = DEFAULT_BUFFER.with_name("buffer_junk.jsonl")

# --- junk markers: reasoning-trace leaks, meta-commentary, tool-call dumps ---
_JUNK_MARKERS = (
    "thinking process",          # "Here's a thinking process:"
    "analyze user input",        # reasoning-trace step header
    "analyze the user's request",
    "[tool_result",              # raw tool plumbing
    "tool_result:",              # raw tool plumbing
    '"tool":',                   # completion IS a tool call, not an answer
    "'tool':",
    "function_call",
    "<tool_call",
    "**analyze",                 # bolded reasoning header
    "self-critique",             # reasoning-trace segment (11.09.26 wave 3)
    "self-critique:",            # variant with colon
    # reasoning-header phrases that leaked on 14.09.26. Kept PRECISE: the
    # bolded header form, not the bare phrase, so real prose survives.
    "**identify the core",       # "2. **Identify the Core \"Technical Insight\"**"
    "text is mostly meta",       # "The text is mostly meta-information ..."
    "possible angles:",          # planning bullet header
    "first situation:",          # structural-connection reasoning step
    "let me break this down",    # planning voice, mid-text
)

# --- reasoning-trace OPENER: the model's planning voice, not an answer ---
# Added 11.09.26 (2nd wave): the marker list above missed traces that open in
# plain English first person ("We need to answer the question: ...", "Let me
# think about ..."). 26 of 300 live entries were this shape and trained the 2B
# to think out loud instead of answering.
import re as _re

_TRACE_OPENER = _re.compile(
    r"^[\s\"'\u201c\u201d]*(?:\d+[.)]\s+)?(?:we need|we have|we must|we should|i need|"
    r"i should|i will|i'?ll |let me|the user|the question|the prompt|"
    r"first,? i|okay,?\s+(?:so|let|the user|i\b|we\b)|alright,? |hmm,? |"
    r"here'?s? (?:a|my) (?:thinking|reasoning|plan)|"
    r"thinking process|analy[sz]e the)",
    _re.IGNORECASE,
)

# --- truncated fragment: too little text to teach anything ---
# Added 11.09.26 (wave 3): single-token rows like "Both" leaked through. A
# one-word completion of natural-language length with no sentence punctuation
# is a cut-off generation, not an answer. Deliberately narrow: short synthetic
# test placeholders ("a1") and real one-word answers ("Ja.") must still pass,
# so the check needs BOTH a natural-word length AND no punctuation.
_MIN_CHARS_FOR_TOKEN_CHECK = 8
_MIN_WORDLEN_FOR_FRAGMENT = 3

# --- search-engine snippet posing as an answer ---
# Added 11.09.26 (2nd wave): internet_learner wrote raw SERP text ("<Title> —
# 1. Sept. 2026 · <snippet>") into the buffer as if it were the model's answer.
# 148 of 300 live entries (49 %) — the single largest junk class. The tell is
# the search UI's em-dash + German date + middle-dot separators; a real answer
# rarely carries two of them, and never the '· ' run-on.
_SERP_DATE = _re.compile(
    r"—\s*\d{1,2}\.\s*(?:Jan|Feb|Mär|Mrz|Apr|Mai|Jun|Jul|Aug|Sept?|Okt|Nov|Dez)\.?\s*\d{4}\s*·"
)
_SERP_TAIL = _re.compile(r"—\s*(?:…|\.\.\.)\s*$")
# Added 15.09.26: two more SERP shapes slipped past the checks above. (1) a
# truncated result title followed by the next result's title
# ("Jailbreaking ... Techniques, … — This article explores ...");
# (2) a GitHub result-list title ("GitHub - owner/repo: description").
# Measured on the live 300-row buffer: 14 rows matched, every one was
# search-result chrome and no real prose row matched.
_SERP_ELL_DASH = _re.compile(r"…\s*[—–]\s")
_SERP_REPO_TITLE = _re.compile(r"GitHub\s*-\s*[\w.\-]+/[\w.\-]+\s*:")
# Added 15.09.26: a fourth SERP shape, "<title> | <site> — <snippet>", which
# carries no ellipsis and therefore slipped past _SERP_ELL_DASH (found live in
# cycle_c_github). Measured on the live 300-row buffer: 13 hits, all
# search-result chrome, 0 real-prose rows affected — a tightening only.
_SERP_PIPE_DASH = _re.compile(r"\|[^|]{1,40}\s—\s")


def _is_serp_snippet(text):
    """True when text is search-result chrome rather than an answer."""
    if _SERP_DATE.search(text):
        return True
    # several ' — ' title separators + a middle dot = a results list
    if text.count(" — ") >= 2 and "·" in text:
        return True
    if _SERP_TAIL.search(text):
        return True
    if _SERP_ELL_DASH.search(text):
        return True
    if _SERP_PIPE_DASH.search(text):
        return True
    return bool(_SERP_REPO_TITLE.search(text))


# --- periodic repetition: a short unit repeated until it fills the text ---
# Added 11.09.26 (wave 3). The token-ratio check above misses a loop whose
# tokens cycle ("user [   \" user [   \" user [   \"") — uniq/total stays ~0.33
# even though the completion is pure repetition. Detect it structurally: find
# the shortest unit that repeats >=3x back-to-back and measure its coverage.
_REPEAT_UNIT = _re.compile(r"(.{3,40}?)\1{2,}", _re.DOTALL)


def _is_periodic_repeat(text):
    """True when the text is one short unit repeated to fill the whole string."""
    m = _REPEAT_UNIT.search(text)
    if m:
        unit = m.group(1)
        covered = len(unit) * text.count(unit)
        if covered / max(1, len(text)) > 0.5:
            return True
        if len(m.group(0)) / max(1, len(text)) > 0.6:
            return True
    # Short text built from a handful of distinct words repeated — catches
    # loops whose unit straddles line breaks ('user\\n[\\n  "\\n' x3), where the
    # backreference run can be one short of three. A genuine short answer never
    # has >=4 tokens drawn from <=3 distinct words. Requires >=4 DISTINCT
    # characters so a single repeated character ("aaaa…") is not misread as a
    # word loop — that shape is handled by the token-ratio check instead.
    toks = text.split()
    if 4 <= len(toks) and len(set(toks)) <= 3 and len(set(text)) >= 4:
        return True
    return False


# --- glued-motif degeneration (live 15.09.2026) ---
# The 2B extractor degenerated into a word salad that the periodic-repeat and
# token-ratio gates both miss because the motif sits INSIDE otherwise-distinct
# words: 'Here's a ali with aminoellsかけて subject et recessellsells deep this
# urbanellscriptsells ...' ('ells' inside 14 of ~43 tokens). Measured over the
# live 300-row buffer: that row scores 14 hits at a 0.056 char-rate; the
# highest-scoring REAL row scores 8 hits at 0.027, so both thresholds sit in a
# clean gap and no legitimate row is affected.
_GLUED_MOTIF_MIN_COUNT = 12
_GLUED_MOTIF_MIN_RATE = 0.045


def is_glued_motif(text):
    """True when ONE 4-char motif is glued into most tokens of the text.

    A distinct 4-char window repeated >=12 times AND covering >=4.5% of the
    characters is degeneration, not prose: real technical sentences never
    reuse a single 4-gram that densely (see the measurement above).
    """
    if len(text) < 60:
        return False
    n = len(text)
    _, count = Counter(text[i:i + 4] for i in range(n - 3)).most_common(1)[0]
    return (count >= _GLUED_MOTIF_MIN_COUNT
            and count * 4 / n >= _GLUED_MOTIF_MIN_RATE)


# --- HTML entity noise + course-landing-page chrome (11.09.26 wave 4) ---
# The learner's page fetch leaks raw HTML entities and marketing chrome into
# the completion. A LoRA trained on '&#39;' learns broken tokenization.
_ENTITY = _re.compile(r"&(?:#\d{1,5}|[a-z]{2,8});")
# --- binary noise: raw bytes mis-decoded as text (live 15.09.26) ---
# The deep read fetched a binary blob and the writer stored the mojibake
# ("T\ufffdp\ufffd%\ufffd\ufffd;...") as a learning. The extraction-side
# gate (internet_learner._looks_binary) only covers the cycle path; every
# other writer reached the buffer unguarded. Measured over the live
# 300-row buffer: worst row scores 0.576 non-printable ratio, the next
# highest real row scores 0.000 -> the thresholds sit in a clean gap.
_CTRL_NOISE = _re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]")
_BINARY_MIN_CHARS = 20
_BINARY_RATIO = 0.08
_NAV_CHROME = (
    "no thanks", "testimonial", "subscribe", "newsletter", "sign up",
    "all rights reserved", "read more", "click here", "follow us",
    "join our", "share this", "leave a reply", "cookie policy",
    "privacy policy", "welcome to the", "incredible educator",
    # prompt-template leaks: the completion echoes the instruction skeleton
    "key insight:", "<one sentence>", "focus on actionable",
    "focus actionable", "ensure it's actionable",
    # UI chrome from the app/terminal surfaces
    "switched accounts", "another tab or window", "automate any workflow",
    "mission control for everything", "operation interrupted",
    "waiting for model response", "documentation index",
    # doc-site chrome the learner's page fetch leaks
    "check this document", "fetch the complete",
    # github repo-page chrome the learner's page fetch leaks (live 15.09.26:
    # cycle_c_github stored "... Public Notifications You must be signed in to
    # change notification settings Fork 925 Star 6." as a learning)
    "signed in to change notification",
    # GitHub org/user-page chrome the learner's deep read leaks (live
    # 15.09.26: cycle_b_papers stored "Updated Dec 19, 2013 People This
    # organization has no public members." as a research insight)
    "has no public members",
    # prompt-template leak, second shape (live 15.09.26: cycle_d_docs stored
    # `" exactly). - Must be a single technical insight extracted from the
    # given text. - **Text Source:** ...` as a doc learning)
    "must be a single technical insight", "**text source:",
    # GitHub repo-page header (live 15.09.26: rows "Updated Jul 12, 2025
    # Jupyter Notebook owner/repo Star 1 Code Issues Pull requests ..." and
    # "Updated Sep 14, 2026 Python owner/repo Sponsor Star 294 ..." — 3
    # such rows measured, 0 real-prose rows carry this phrase)
    "code issues pull requests",
    # GitHub releases-page chrome (live 15.09.26: cycle_f_multi_domain
    # stored "No results found View all tags openai-sdks released this
    # 14 Sep 23:28 v3." — pure page meta, zero prose. Measured over the
    # live 300-row buffer: 1 hit, 0 real-prose rows carry the phrase.)
    "view all tags",
    # blog-post header chrome (live 15.09.26: cycle_c_github stored
    # "August 5, 2026 · 15 min Read article Guides What is MCP (Model
    # Context Protocol)?" — pure meta header, no prose. Measured over the
    # live 300-row buffer: 1 hit, 0 real-prose rows carry this phrase)
    # MediaWiki wikitext leak (live 16.09.26: cycle_d_docs stored
    # `Sum|143|150|154|165|149|114|127|}} minutes (7 films)"},
    # "distributor":{"wt":"{{Plainlist|* [[Paramount Pictures]] ...` -- raw
    # wikipedia film-box markup, zero prose, and BOTH gates passed it).
    # Measured over the live 300-row buffer: 1 hit, 0 real-prose rows carry it.
    '"wt":"',
    # GitHub pricing/plan chrome (live 16.09.26: cycle_c_github stored
    # "BILLED ANNUALLY $119 /yr Select First 7 days FREE then $119 billed
    # annually, cancel anytime Gaia+ $24 ." -- pure price-table copy, zero
    # prose, and no sentence shape. Measured over the live 300-row buffer:
    # 1 hit, 0 real-prose rows carry the phrase.)
    "billed annually",
    # AI-chat UI + review-site chrome (live 16.09.26: cycle_g_security
    # stored the chat feature list "Agent mode Let Chat calculate, ...
    # AI Chat can make mistakes." and cycle_f_multi_domain stored "
    # Home Product categories ... Based on 4,014 reviews Products
    # considered 726 ...". Measured over the live 300-row buffer: 1 hit
    # each, and that hit IS the leaking row -> 0 real-prose rows carry
    # any of these phrases.)
    "let chat calculate",
    "hand off real-world tasks",
    "ai chat can make mistakes",
    "products considered",
    "min read article",
)


def _is_binary_noise(text):
    """True when text is raw bytes mis-decoded as text (PDF/zip blob).

    Counts C0/C1 control chars and U+FFFD REPLACEMENT CHARACTER. The
    live mojibake row measured 0.576; the highest-scoring real row of
    the 300-row buffer measured 0.000, so 0.08 is a wide margin.
    """
    if len(text) < _BINARY_MIN_CHARS:
        return False
    return len(_CTRL_NOISE.findall(text)) / len(text) > _BINARY_RATIO


def _is_nav_chrome(text):
    """True when text is page chrome (entities, marketing, UI, template leaks)."""
    if _ENTITY.search(text):
        return True
    low = text.lower()
    if any(c in low for c in _NAV_CHROME):
        return True
    # a header repeated back-to-back ("Welcome to the X Welcome to the X")
    first = text[:40].strip()
    if len(first) > 12 and text.count(first) >= 2:
        return True
    return False


# a completion this short carries no trainable content
_MIN_CHARS = 12
# degenerate-repetition thresholds (measured: junk ~0.14 unique-ratio,
# real prose ~0.5+; a 4-token floor catches short loops like 4x "Self" —
# lowered from 6 on 11.09.26 after a 4x-Self row slipped through)
_MIN_TOKENS_FOR_REPEAT_CHECK = 4
_MIN_UNIQUE_RATIO = 0.15
_MAX_TOP_TOKEN_SHARE = 0.5


def is_junk(text):
    """True when a completion is not trainable signal.

    Structural markers first (cheap + unambiguous), then degenerate
    repetition. Empty/whitespace text is NOT classified here — callers may
    legitimately record a placeholder and the historical contract tolerates
    it; this predicate only rejects content that actively poisons training.
    """
    if text is None:
        return False
    s = text.strip()
    if not s:
        return False
    low = s.lower()
    if any(m in low for m in _JUNK_MARKERS):
        return True
    if _TRACE_OPENER.match(s):
        return True
    if _is_serp_snippet(s):
        return True
    if _is_periodic_repeat(s):
        return True
    if is_glued_motif(s):
        return True
    if _is_binary_noise(s):
        return True
    if _is_nav_chrome(s):
        return True
    tokens = s.split()
    # A short single-word fragment with a LOWERCASE run and no punctuation is a
    # cut-off generation ("Both"). Requires >=2 letters so synthetic test
    # placeholders ("a1") and real answers ("Ja.", "Nein!") both survive.
    if (len(s) < _MIN_CHARS_FOR_TOKEN_CHECK and len(tokens) == 1
            and _re.fullmatch(r"[A-Za-zÄÖÜäöüß]{2,}", s)
            and not _re.search(r"[.!?,;:]", s)
            and not s.islower()):
        return True
    if len(tokens) >= _MIN_TOKENS_FOR_REPEAT_CHECK:
        uniq = len(set(tokens))
        if uniq / len(tokens) < _MIN_UNIQUE_RATIO:
            return True
        top = max(tokens.count(t) for t in set(tokens))
        if top / len(tokens) > _MAX_TOP_TOKEN_SHARE:
            return True
    return False


def _audit(user_text, assistant_text, reason):
    """Append a rejected example to the audit log (best-effort)."""
    try:
        with open(JUNK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "reason": reason,
                "u": (user_text or "")[:300],
                "a": (assistant_text or "")[:300],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _is_duplicate(rec, buf):
    """True when (u, a) already sits in the buffer — the learner re-observes
    the same fact on every cycle, and a LoRA trained on 3x identical rows
    over-weights that one example. Added 11.09.26 (vLLM doc seen 3x live)."""
    try:
        target = (rec.get("u", ""), rec.get("a", ""))
        for line in open(buf, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if (d.get("u", ""), d.get("a", "")) == target:
                return True
    except FileNotFoundError:
        return False
    return False


def append(user_text, assistant_text, buffer=None, max_buf=None):
    """Append one (u, a) example and enforce the cap. Returns buffer line count.

    Junk completions (see `is_junk`) are refused: nothing is written, the
    rejection is logged to `buffer_junk.jsonl`, and the current count is
    returned so callers can detect the no-op by comparing counts. Exact
    duplicates are refused the same way — a training set must not repeat a row.
    """
    buf = Path(buffer or DEFAULT_BUFFER)
    cap = int(max_buf or MAX_BUF)
    buf.parent.mkdir(parents=True, exist_ok=True)
    if is_junk(assistant_text):
        _audit(user_text, assistant_text, "junk")
        return count(buf)
    rec = {
        "u": (user_text or "")[:3000],
        "a": (assistant_text or "")[:4000],
    }
    if _is_duplicate(rec, buf):
        _audit(user_text, assistant_text, "duplicate")
        return count(buf)
    with open(buf, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return enforce_cap(buf, cap)


def count(buffer=None):
    """Number of examples currently in the buffer."""
    buf = Path(buffer or DEFAULT_BUFFER)
    try:
        return sum(1 for _ in open(buf, encoding="utf-8"))
    except FileNotFoundError:
        return 0


def enforce_cap(buffer=None, max_buf=None):
    """Trim the buffer to the newest `max_buf` lines. Returns the new count."""
    buf = Path(buffer or DEFAULT_BUFFER)
    cap = int(max_buf or MAX_BUF)
    try:
        lines = open(buf, encoding="utf-8").readlines()
        if len(lines) > cap:
            tmp = buf.with_suffix(buf.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(lines[-cap:])
            os.replace(tmp, buf)
            return cap
        return len(lines)
    except Exception:
        # never let a trim failure break a learning cycle
        return count(buf)
