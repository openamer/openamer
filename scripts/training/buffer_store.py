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
    # GitHub repo-page toolbar chrome (live 16.09.26, second sighting): four
    # rows reached the buffer through BOTH gates as
    # `Code Pull requests Actions Projects Security and quality Insights
    #  main Branches Tags Go to file Code Open more actions menu Latest
    #  commit History 4,190 Commits ...`. >230 chars with digits, so the
    # length trust and the technical-signal gate both fired. Measured: 4
    # buffer hits, all chrome -> 0 real-prose FPs (284-row corpus) and 0
    # test-asserted-clean FPs (77 strings); a bare "go to file" would also
    # hit 1 longterm_episodes row.
    "open more actions menu",
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
    # HN comment-listing pagination chain (live 16.09.26: cycle_c_github
    # stored "... | prev | next [–] ... | prev [–] ..."). Pipe+nav
    # adjacency is page markup; a markdown table row carries no nav token.
    "| prev | next", "| next | prev", "| prev [–]",
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
    "watch live key points",
    # Social-share widget chrome (live 16.09.26: cycle_a_technews stored the
    # row "March 17, 2026 (UPDATED Sep 8, 2026) ... Reddit Post Share Threads
    # Support my work." — a share/subscribe widget, zero prose). Concrete
    # phrase only: "support my work" is a donation/podcast CTA, never a
    # technical statement.)
    "support my work",
# German-dictionary chrome (live 16.09.26: cycle_c_github stored "... Duden
# — Definition, Rechtschreibung, Synonyme und Grammatik von 'Agent' ... Auf
# Duden online nachschlagen ... Wörterbuch der deutschen ...; Agent
# (Nachrichtendienst) – Wikipedia ..." — two dictionary SERP snippets
# joined by ";", zero technical prose). Marker is the dictionary's own call to
# action; measured over the live buffer: 1 hit and that hit IS the leaking row
# -> 0 real-prose rows carry it. A structural "…;" gate was REJECTED: 7 of
# the 16 such rows (vLLM, quantization) carry genuine technical prose.)
    "auf duden online",
    # German bank referral/promo chrome (live 16.09.26: cycle_c_github
    # stored "Auch die neue Kundin oder der neue Kunde erhält eine Prämie
    # von 300 €, was eine Gesamtprämie von 600 € ergibt!"). Mirror of
    # internet_learner._JUNK_RE — every writer path must agree. Measured
    # over the live 5080-row corpus: 1 hit (the leaking row), 0 real-prose
    # rows carry these phrases.)
    "prämie von",
    "gesamtprämie",
    "erhält eine prämie",
    "neukundenprämie",
    "empfehlungsprämie",
    # 16.09.26 measured leaks: HN listing chrome (cycle_f) and the Wikipedia
    # infobox label chain (cycle_g). Measured on the live buffer: 1-2 hits
    # each, 0 real-prose FPs on a 12-sentence hand-written prose set.
    # NOTE: bank T&C balance figures were left UNGATED on purpose — the
    # candidate markers `consumer account` / `checking account` /
    # `savings account` each hit 1-3 hand-written real-prose sentences, i.e.
    # they are topic words, not chrome. Only that one row is affected.
    "visit website",
    "points by ",
    "points ·",
    "comments ·",
    "connector type",
    " months ago (",
    # 16.09.26 product-page header (cycle_e_competitors): date + read time
    # + section label ("July 30, 2026 2 min read Explore the desk Every
    # Frontierbeat desk, organized Artificial Intelligence"). 1 hit, 0
    # real-prose FPs. NOTE: bare `min read` is deliberately NOT used; the
    # tight `min read explore` tail fires only on this header shape.
    "every frontierbeat desk",
    "min read explore",
    # German Wikipedia list/glossary page chrome (live 16.09.26:
    # cycle_g_security stored "Liste aller Wikipedia-Artikel, deren Titel
    # Agent enthaelt Wiktionary: Agent - Bedeutungserklaerungen,
    # Wortherkunft, Synonyme, Uebersetzungen Dies ist eine
    # Begriffsklaerungsseite ..." -- 210 chars cleared the >=90 length trust
    # and its digits satisfied the technical-signal gate). Concrete page
    # phrases only, never the bare topic words: measured over the live buffer
    # 1 hit and that hit IS the leaking row -> 0 real-prose false positives.
    "liste aller wikipedia-artikel",
    "deren titel",
    "wiktionary:",
    # A 2B self-critique echo (live 16.09.26: cycle_d_docs stored
    # '"\n   - **Context:** The user pasted a long documentation page from vLLM,
    # but the actual content is just the table of contents ...') -- the
    # extractor echoed its own review scaffold and cleared the >=90 length
    # trust. Concrete scaffold phrases only; measured over the live buffer:
    # 1 hit and that hit IS the leaking row -> 0 real-prose false positives
    # on the 280-row non-junk corpus.
    "the user pasted",
    # A 2B PLAN-scaffold echo (live 16.09.26, cycle_h_efficiency): the row
    # '"\n   - **Content:** I need to browse the provided list of papers,
    # identify the most relevant/valuable technical insight for an autonomous
    # AI agent, and output it in the exact format.\n\n2.  **Survey the Papers:**
    # ...' cleared BOTH gates: ~300 chars fed the >=90 length trust and the
    # digits ("2.") fed the technical-signal gate. No existing marker matched --
    # the echo opens on the model's OWN numbered plan, not on the documented
    # scaffold phrases. Markers are the task-voice tail and the plan heading.
    # Measured: 1 buffer hit and that hit IS the leaking row -> 0 real-prose
    # FPs on a 10-sentence set, 0 hits over the 433-row world_model corpus.
    # NOTE: `provided list of papers` alone was REJECTED (flags the prose
    # sentence "The agent should browse a provided list of papers only
    # when ..."), as was `identify the most relevant`; the /-joined adjective
    # pair is the tight discriminator (0 hits in the prose set).
    "most relevant/valuable technical insight",
    "**survey the papers:**",
    # Microsoft SERP/landing-page copy reached the buffer via
    # cycle_h_efficiency (live 16.09.26): "Microsoft - AI, Cloud,
    # Productivity, Computing, Gaming & Apps - Explore Microsoft products
    # and services ... Shop Microsoft 365, Copilot ...". Same marker as
    # internet_learner._JUNK_RE; keep both files in sync. Measured over
    # the live buffer: 1 hit and that hit IS the leaking row -> 0 prose FPs.
    "explore microsoft products and services and support for your home or business",
    # news-site market-ticker chrome the deep read leaks (live 17.09.26:
    # cycle_f_multi_domain stored "Walmart investors reject AI workplace
    # report as automation expands in the US - The Economic Times Benchmarks
    # CLOSED Nifty 23,118." as a domain learning; 129 chars with digits, so
    # the length trust and the technical-signal gate both fired).
    # Same markers as internet_learner._JUNK_RE; keep both files in sync.
    # Measured over the live buffer: 1 hit and that hit IS the leaking row
    # -> 0 prose FPs (284-row corpus), 0 hand-written counter-case FPs.
    # A bare "nifty" was measured and REJECTED (1 hand-written + 1 live
    # prose FP: "Benchmarks from the Nifty index showed a 2% gain ...").
    "closed nifty",
    # GitHub README changelog/news bullet list the deep read leaks (live
    # 17.09.26: cycle_h_efficiency stored "Inference: low decode overhead,
    # best throughput, and TTFT News [2024-10-14] Add Rocm support
    # [2024-10-6] Try it on Google Colab [2024-10-5] Add free Huggingface
    # Demo : Huggingface Demo [2024-10-4] Updated the VPTQ tech report" --
    # 251 chars with digits, so the length trust AND the technical-signal
    # gate both fired). Same marker as internet_learner._JUNK_RE; keep both
    # files in sync. Measured over the live buffer: 2 hits (the same row
    # duplicated) and BOTH are the leak -> 0 prose FPs (283-row corpus),
    # 0/8 hand-written counter-case FPs. Rejected candidates, each hitting
    # real prose: "add rocm support", "try it on google colab",
    # "low decode overhead" (1 hand FP each). A structural >=3-bracketed-date
    # count also measured 0 FP both corpora -- candidate for a class-wide
    # detector later; not needed for this single leak.
    "the economic times benchmarks",
    "add free huggingface demo",
)


# A social counter truncated at its own digit ("K followers") means the text
# starts mid-widget: the count's number was cut off. Anchored at the START and
# requiring NO leading digits, so real prose that merely reports a follower
# count ("Mistral has 30k followers on GitHub") is untouched — measured over
# the live 282-row buffer: 1 hit (the leaking row), 0 real-prose rows.
# A sports-fixture list from a results page (live 16.09.26: cycle_c_github
# stored "Napoli vs Lazio 0-2 | 12/04/2026 Parma vs Napoli 1-1 | ... SSC
# NAPOLI OFFICIAL APP" as a GitHub learning -- 246 chars cleared the length
# trust and the scoreline digits fed the technical-signal gate). Structural:
# a scoreline immediately followed by a pipe and a fixture date, i.e. a
# results-table row, never prose. Measured over the live buffer: 1 hit and
# that hit IS the leaking row -> 0 real-prose false positives on the
# 280-row non-junk corpus. A bare 'A vs B' is deliberately NOT gated --
# measured 6 hits, all real prose ('CUDA vs ROCm vs Vulkan vs Metal').
_FIXTURE_LIST_RE = _re.compile(
    r"\b\w+\s+vs\.?\s+\w+[^|]{0,25}\d{1,2}\s*[-\u2013]\s*\d{1,2}\s*\|\s*"
    r"\d{1,2}[/.]\d{1,2}[/.]\d{2,4}",
    _re.IGNORECASE)
_DETACHED_COUNT_RE = _re.compile(r"^\W*[kKmM]\s+followers\b")

# A clock time, used ONLY together with a self-repeated phrase (ticker loop).
_TIME_CODE_RE = _re.compile(r"\b\d{1,2}:\d{2}\b")

# arXiv abstract-page chrome (live 16.09.26, class 10) — mirror of
# internet_learner._is_arxiv_abstract_chrome. The extraction gate drops the
# label chain, but every other writer path reaches this gate, so the rule is
# kept here too. `buffer_store` must not import the learner (circular), hence
# the duplication. Measured over the live 275-row buffer: 1 hit (the leaking
# row), 0 real-prose rows.
_ARXIV_CHROME_MARKERS = (
    "view email",
    "submission history",
    "full-text links",
    "view a pdf of the paper titled",
    "cite as arxiv",
    "xiv-issued doi",
    "bibliographic explorer",
)
_ARXIV_CHROME_MIN_MARKERS = 2
# The "View PDF / HTML (experimental)" LISTING header (live 18.09.26, class 52):
# cycle_h_efficiency stored
#   "PDF of the paper titled QuIP: 2-Bit Quantization of Large Language Models
#    With Guarantees, by Jerry Chee and 3 other authors View PDF HTML
#    (experimental) Abstract: This work studies post-training parameter
#    quantization in large language models (LLMs)."
# - a 251-char arXiv listing/abstract-modal header: the title (often truncated,
# with no leading "PDF of the paper titled") welded to a byline count and the
# page's own "View PDF HTML (experimental)" controls. Both gates passed it: the
# digits fed the technical-signal gate and the length cleared the >=90 "long
# prose" trust.
#
# Sibling shape of the marker tuple above, NOT the same row: class-10 rows carry
# the ABSTRACT PAGE label chain, these carry the listing controls with one or
# zero class-10 labels, so `view a pdf of the paper titled` never fired. The
# control pair is unique to the document viewer: a real sentence that merely
# mentions viewing a PDF or an experimental HTML build carries neither half.
# Measured (18.09.26): 3/3 live buffer hits are the leak; 0 of 1,003 asserted
# gate-test literals; 0 of 3,058 longterm_episodes; 0 hand-prose controls.
_ARXIV_PDF_LABEL_RE = _re.compile(
    r"view\s+pdf\s+html\s*\(\s*experimental\s*\)",
    _re.IGNORECASE)


def _is_arxiv_abstract_chrome(text):
    """True when `text` is an arXiv-style abstract page's label chain."""
    low = (text or "").lower()
    if not low:
        return False
    if _ARXIV_PDF_LABEL_RE.search(low):
        return True
    return sum(1 for m in _ARXIV_CHROME_MARKERS if m in low) >= _ARXIV_CHROME_MIN_MARKERS


# Chinese Q&A / answer-portal chrome (live 16.09.26, class 12) — mirror of
# internet_learner._is_qa_portal_chrome. The extraction gate drops the label
# chain, but every other writer path reaches this gate, so the rule is kept
# here too (`buffer_store` must not import the learner — circular). Measured
# over the live 5013-row corpus: 5 hits, all chrome, 0 real-prose rows.
_QA_PORTAL_CHROME_MARKERS = (
    "百度认证",
    "高粉答主",
    "已赞过",
    "已踩过",
    "向ta提问",
    "回答量",
    "你对这个回答的评价是",
    "展开全部",
    "经验内容仅供参考",
    "本篇经验系本人",
    "展开阅读全部",
    "作者声明",
)
_QA_PORTAL_CHROME_MIN_MARKERS = 2


# MediaWiki section-edit control (live 16.09.26, class 12) -- mirror of
# internet_learner._strip_wiki_section_prefix. The learner STRIPS a LEADING
# marker, but every other writer path reaches this gate, so the same narrow
# rule is enforced here. Deliberately NOT a blanket "[ edit ]" marker:
# that would reject a real sentence ABOUT an edit button
#   ("Wikipedia's [ edit ] button is a MediaWiki control, not content ..."),
# which the strip rule keeps learnable. Anchored + sentence-case name +
# sentence-opening body -- the same guards, so the two agree by construction.
_WIKI_EDIT_WORD_RE = _re.compile(
    r"^(?:[A-Z\d]\w*(?:\s+[a-z]\w*){0,5}\s*)?"
    r"\[+\s*(?:[Ee]dit|[Bb]earbeiten|[Ee]ditieren|[Ss]ource\s+[Ee]dit|"
    r"[Mm]odifier|[Mm]odifica|[Bb]ewerken|[Rr]ediger|[Rr]edigera|[Mm]uokkaa|"
    r"[Ee]dytuj|[Ss]zerkeszt[e\u00e9]s)\s*\]+"
    r"(?=\s*[A-Z\x22\x27\u201c\u2018\d])")


def _is_qa_portal_chrome(text):
    """True when `text` is a Chinese Q&A/answer-portal label chain.

    Structural, not topical: TWO independent portal markers, so a genuine
    insight written in Chinese still passes.
    """
    low = (text or "").lower()
    if not low:
        return False
    return sum(1 for m in _QA_PORTAL_CHROME_MARKERS if m in low) >= _QA_PORTAL_CHROME_MIN_MARKERS


# German SaaS pricing/checkout chrome (live 16.09.26, class 13) — mirror of
# internet_learner._is_de_pricing_chrome. The extraction gate drops the label
# chain, but every other writer path reaches this gate, so the rule is kept
# here too (`buffer_store` must not import the learner — circular). Measured
# over the live 4855-row corpus: 6 marker hits, all in ONE row (the leaking
# row), 0 real-prose rows. The English twin, "billed annually", already lives
# in _NAV_CHROME above.
_DE_PRICING_CHROME_MARKERS = (
    "monatlich kündbar",
    "jahrespaket",
    "lastschrift",
    "auf rechnung",
    "pro nutzer und monat",
    "€ / jahr",
)
_DE_PRICING_CHROME_MIN_MARKERS = 2


def _is_de_pricing_chrome(text):
    """True when `text` is a German pricing/checkout label chain.

    Structural, not topical: TWO independent billing markers, so real prose
    that happens to cite a price still passes.
    """
    low = (text or "").lower()
    if not low:
        return False
    return sum(1 for m in _DE_PRICING_CHROME_MARKERS if m in low) >= _DE_PRICING_CHROME_MIN_MARKERS


# An ad-blocker-off / subscribe notice is a CTA chain, not knowledge (live
# 17.09.26, class 28; same rule as internet_learner._is_adwall_notice, mirrored
# here because the writer gate must agree with the extraction gate by
# construction -- and buffer_store must not import the learner, circular).
_ADWALL_NOTICE_RE = _re.compile(
    r"(?:adblocker|werbeblocker)\s*(?:bitte\s*)?(?:ausschalten|deaktivieren|entfernen)"
    r"[\s\S]{0,240}?"
    r"(?:ohne\s+werbung|werbefrei|im\s+abo|f[üu]r\s+nur\s+\d|\d+[,.]\d{2}\s*€)",
    _re.IGNORECASE)


def _is_adwall_notice(text):
    """True when `text` is an ad-blocker-off / subscribe notice (page chrome)."""
    return bool(_ADWALL_NOTICE_RE.search(text or ""))


# A numbered-prompt ECHO is a loop buffering its own task text back at
# itself (live 16.09.26: active_learn.cross_connect stored
# `Situation 2 learning process: Continuous Learning Loop: error capture +
# categorization + memory + auto-skill generation + trend.` and the quoted
# variant `Situation 1: "learning process: ..." German: ...`). Anchored on
# the numbered PROMPT MARKER plus a topic word or colon, so genuine
# declarative answers survive -- `Situation 1 and situation 2 share a common
# failure mode ...` and `The shared underlying pattern is ...` both pass.
# Measured: 2/2 leaks caught, 0/5 real answers killed.
_ECHO_SITUATION_RE = _re.compile(
    r"^\s*\**\s*situation\s*\d\s*(?::|\b(?:learning|system|energy|tool)\b)",
    _re.IGNORECASE)


# Prompt-echo, FOURTH shape (live 16.09.26): active_learn.cross_connect
# buffered TWO more of its own prompt fragments back at itself --
# `User asks: "Find the structural connection between these two situations:  1.`
# and the bare `Shared underlying pattern?` (26 chars, just clearing the
# producer's 25-char floor), plus the `... + Trend\n\nWhat is the shared
# underlying pattern?` variant. _ECHO_SITUATION_RE is anchored on the numbered
# `situation N` marker and cannot see any of them. So: a FRAGMENT rule (a
# colon-terminated prompt artefact anywhere in the text) and a TAIL rule (the
# question sitting at the END of a stub). Measured over the live 300-row
# buffer: 3 hits and all 3 ARE the leaking rows -> 0 real-prose false positives
# on a 12-sentence hand-written set, 0 hits over 3,169 longterm_episodes rows.
# A genuine declarative answer on the same topic ("The shared underlying
# pattern is a closed-loop feedback system ...") and an ordinary sentence that
# merely uses the words ("A user asks the agent to summarize a document") both
# survive -- the colon and the end-anchor are the discriminators.
_ECHO_FRAGMENT_RE = _re.compile(
    r"user\s+asks\s*:|"
    r"find\s+the\s+structural\s+connection\s+between\s+these\s+two\s+situations\s*:",
    _re.IGNORECASE)
_ECHO_TAIL_RE = _re.compile(
    r"(?:what\s+is\s+the\s+)?shared\s+underlying\s+pattern\s*\??\s*$",
    _re.IGNORECASE)
_ECHO_TEMPLATE_RE = _re.compile(
    r"identify\s+the\s+goal\s*:|the\s+insight\s+should\s+be",
    _re.IGNORECASE)


# Prompt-echo, SIXTH shape (live 16.09.26): active_learn.cross_connect buffered
# its own prompt opener back at itself as
#   `Question: Find structural connection between these two situations. What`
# The earlier fragment rule needs `find the structural connection` WITH the
# article and a trailing colon, while this parroting drops the article and ends
# on a period -- and every opener rule is anchored on OTHER words, so `Question:`
# was never a candidate. Measured over the live 300-row buffer: 1 hit and that
# hit IS the leaking row -> 0 real-prose false positives; 0 hits across 11,342
# longterm_episodes/world_model values. The `^` anchor plus the
# find/identify/what|how|why shape is what keeps genuine prose clean --
# "Structural connection between these two situations is a shared bottleneck."
# and "The shared underlying pattern is a closed-loop feedback system ..." both
# survive. This is a *question the agent is ASKING*, never an answer.
_ECHO_QUESTION_RE = _re.compile(
    r"^\s*\**\s*question\s*:\s*(?:find|identify|what|how|why)\b",
    _re.IGNORECASE)


# A bare section-ordinal tail: a SHORT extract ending on a numbered heading with
# no verb is a chopped table-of-contents item, not an insight. Live 16.09.26:
# cycle_f_multi_domain stored "Probabilistic methods for uncertain reasoning 2."
# (48 chars) as multi-domain knowledge. The earlier _has_alpha_signal fix was
# added for the same class ("Distinction between classical and modern physics
# 2.") but cannot see it, because "reasoning" IS an alphabetic technical keyword.
# Structural instead: <=120 chars + ends on a bare `N.` + NO verb anywhere.
# Measured over the live buffer: 2 hits, both junk (this row and the
# cross-connect plan stub); 0 hits across 11,342 longterm_episodes/world_model
# values. The verb guard is the discriminator that keeps short real answers
# ("LoRA reduces VRAM usage at inference time.") untouched.
# A genuine section heading carries NO other digits -- "Probabilistic methods
# for uncertain reasoning 2." has none, while "…at an effective batch of 16."
# and "…Tel. +49 40 42838-0." are sentences that merely END on a number. The
# no-other-digits test plus the <=120 cap is what separates a chopped TOC item
# from real prose; measured: 2/2 leaks caught, 0 FPs over 73 test-asserted-clean
# strings + 285 buffer prose rows + 11,342 corpus values.
_ORDINAL_TAIL_RE = _re.compile(r"^(.*)\s(\d{1,2})\.\s*$", _re.S)
_ORDINAL_MAX_CHARS = 120
_ORDINAL_VERB_RE = _re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|do|does|did|can|could|will|"
    r"would|should|may|might|must|use[sd]?|using|show[s]?|provide[sd]?|"
    r"require[sd]?|enable[sd]?|reduce[sd]?|improve[sd]?|allow[sd]?|makes?|"
    r"gives?|give|offers?|supports?|increases?|decreases?|runs?|run|works?|"
    r"work|means?|helps?|needs?|lets?|let|takes?|finds?|found|adds?|added|"
    r"removes?|introduces?|keeps?|gets|become[s]?|remains?|appears?|seems?|"
    r"contains?|includes?|verwendet|bietet|reduziert|verbessert|nutzt|ist|"
    r"sind|wird|werden)\b",
    _re.IGNORECASE)


def is_ordinal_stub(text):
    """True when `text` is a short extract ending on a bare numbered heading.

    Consumed by internet_learner._is_junk and clean_buffer via this module, so
    there is exactly one implementation. The three conditions are all load-
    bearing: a whitespace-plus-"N." tail, NO digits before the ordinal,
    and no verb.
    """
    if not text:
        return False
    s = text.strip()
    if len(s) > _ORDINAL_MAX_CHARS:
        return False
    m = _ORDINAL_TAIL_RE.match(s)
    if not m:
        return False
    if _re.search(r"\d", m.group(1)):
        return False
    return not _ORDINAL_VERB_RE.search(s)


def is_prompt_echo(text):
    """True when `text` is the loop's own prompt, or a bare fragment of it."""
    if not text:
        return False
    s = text.strip()
    # Fifth shape (live 16.09.26, cycle_h_efficiency): the 2B extractor
    # echoed its own numbered template -- `2.  **Identify the Goal:** -
    # I need to look at the provided list of papers, ... and extract a
    # single, high-value technical insight ...`. The earlier template
    # markers key on other phrasings ("identify the core task", "extract
    # one technical insight"), so this variant cleared both gates.
    # Colon-terminated, never the bare words: measured 1 buffer hit and
    # that hit IS the leak -> 0 real-prose FPs; a genuine sentence like
    # "The first step is to identify the goal function" stays clean.
    return bool(_ECHO_SITUATION_RE.match(s)
                or _ECHO_FRAGMENT_RE.search(s)
                or _ECHO_TAIL_RE.search(s)
                or _ECHO_TEMPLATE_RE.search(s)
                or _ECHO_QUESTION_RE.search(s))


# A legal-imprint / "Transparenzliste" contact block carries no learning
# signal (live 16.09.26: cycle_c_github stored "Transparenzliste GAIA AG
# Hans-Henny-Jahnn-Weg 53 22085 Hamburg Deutschland +49 40 3510520
# info@gaia-group." as a github learning -- 106 chars cleared the length
# trust and its house number / postcode satisfied the technical-signal gate).
# Structural, not topical: requires a 5-digit postcode AND an international
# phone number AND an e-mail address, so an insight that merely cites a
# count, a port or a version number is untouched. Measured over the live
# 300-row buffer: exactly 1 hit and that hit IS the leaking row -> 0
# real-prose false positives on a 22-sentence hand-written set; 0 hits over
# 3,834 rows of longterm_episodes/train/world_model corpora.
_CONTACT_ZIP_RE = _re.compile(r"\b\d{5}\b")
_CONTACT_PHONE_RE = _re.compile(r"\+\d{1,3}[\s-]?\d")
_CONTACT_EMAIL_RE = _re.compile(r"[\w.+-]+@[\w-]+")
_CONTACT_MAX_CHARS = 600


def is_contact_block(text):
    """True when `text` is a legal-imprint / contact block, not prose.

    All THREE signals must be present, so genuine technical prose that
    happens to mention a number survives.
    """
    if not text or len(text) > _CONTACT_MAX_CHARS:
        return False
    return bool(_CONTACT_ZIP_RE.search(text)
                and _CONTACT_PHONE_RE.search(text)
                and _CONTACT_EMAIL_RE.search(text))


def _is_binary_noise(text):
    """True when text is raw bytes mis-decoded as text (PDF/zip blob).

    Counts C0/C1 control chars and U+FFFD REPLACEMENT CHARACTER. The
    live mojibake row measured 0.576; the highest-scoring real row of
    the 300-row buffer measured 0.000, so 0.08 is a wide margin.
    """
    if len(text) < _BINARY_MIN_CHARS:
        return False
    return len(_CTRL_NOISE.findall(text)) / len(text) > _BINARY_RATIO


def _is_ticker_loop(text):
    """True when text is a news-ticker loop: a time code + a self-repeated phrase.

    Live 16.09.26: cycle_a_technews learned
      "Trump praised Bezos for reversal 03:15 White House blasted Amazon for
       tariffs explainer, Trump praised Bezos for reversal (03:15) OpenAI backs
       measure ... The AI bubble is leaking air, some economists say."
    A live ticker re-renders the same headline with a fresh clock, so the
    extractor receives several unrelated headlines glued together with one
    phrase present twice. Structure, not topic: a real insight does not repeat
    a >=15-char phrase of itself. Measured over the live 270-row buffer:
    catches the leaking row, 0 real-prose rows.
    """
    t = text or ""
    if not _TIME_CODE_RE.search(t):
        return False
    words = t.split()
    for i in range(len(words)):          # O(n^2) but n is one sentence
        for j in range(i + 1, len(words)):
            ph = " ".join(words[i:j])
            if len(ph) >= 15 and t.count(ph) >= 2:
                return True
    return False


# Diagram SOURCE (Mermaid / graphviz-DOT markup), same rule as
# internet_learner._is_diagram_markup. Mirrored here because buffer_store
# must not import the learner (circular) -- the writer gate has to refuse
# the row too, or any other writer path still lands it in the buffer.
_DIAGRAM_DSL_RE = _re.compile(
    r"\b(?:flowchart\s+(?:TD|TB|BT|RL|LR)|sequenceDiagram|classDiagram|"
    r"stateDiagram|erDiagram|subgraph\s+[A-Za-z_]\w*|"
    r"digraph\s+[A-Za-z_]\w*|graph\s+(?:TD|TB|BT|RL|LR)|"
    r"styling\s+node)\b",
    _re.IGNORECASE)
_DIAGRAM_MARKUP_RE = _re.compile(
    r"[A-Za-z_]\w*\s*\[\s*\x22|-->|---|==>|--x|--o|-.->")


def _is_diagram_markup(text):
    """True when `text` is diagram DSL source, not prose (see learner)."""
    t = text or ""
    for m in _DIAGRAM_DSL_RE.finditer(t):
        if _DIAGRAM_MARKUP_RE.search(t[m.end():m.end() + 400]):
            return True
    return False


# Package-INDEX / file-listing chrome (live 16.09.26: cycle_f_multi_domain
# stored 'B view details ) Uploaded Jun 28, 2024 Python 2 Python 3 File
# details Details for the file openpyxl-3.' -- a PyPI files-page label
# chain with zero prose. 105 chars cleared the >=25 floor and the version
# digits fed the technical-signal gate.)
#
# TWO INDEPENDENT label markers required, keyed on the page's OWN label
# chain -- never a topic word or a bare version number, so prose that
# merely mentions a release ("openpyxl 3.1 was uploaded in June 2024 and
# …") carries at most one marker and stays learnable. Measured over the
# live 295-row buffer + 1673 cycle results + 759 kta rows: 2 hits, both the
# SAME leaking row -> 0 prose false positives.
_PKG_INDEX_MARKER_RES = (
    _re.compile(r"view details", _re.IGNORECASE),
    _re.compile(r"file details", _re.IGNORECASE),
    _re.compile(r"details for the file", _re.IGNORECASE),
    _re.compile(
        r"uploaded\s+(?:[A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}|"
        r"\d{4}-\d{2}-\d{2})", _re.IGNORECASE),
    _re.compile(r"python\s+2\s+python\s+3", _re.IGNORECASE),
)
_PKG_INDEX_MIN_MARKERS = 2


def _is_package_index_chrome(text):
    """True when `text` is a package-index / file-listing label chain."""
    t = text or ""
    if len(t) > 600:
        return False
    return (sum(1 for r in _PKG_INDEX_MARKER_RES if r.search(t))
            >= _PKG_INDEX_MIN_MARKERS)


# Course / certification LANDING-PAGE CTA chrome (live 16.09.26:
# cycle_g_security stored 'Certified Agentic AI Security Expert (CAASE)
# Coming Soon Attack, poison, & harden AI agents: reasoning loops, memory
# stores, tool-calling, & multi-agent identity.' -- a sales headline plus
# a feature bundle with zero prose. It is ON-TOPIC for the security cycle,
# which is what makes it sneaky: relevance is not the discriminator, page
# VOICE is.)
#
# Requires the promo voice (an enrollment/launch CTA) AND a course-bundle
# phrase, both keyed on the page's own wording. An insight that merely
# mentions a course, a certification or the words attack/poison in their
# technical sense stays learnable (measured as counter-cases).
_COURSE_CTA_RE = _re.compile(
    r"\b(?:coming soon|enroll now|enrol now|register now|sign up today|"
    r"limited (?:seats|spots)|early bird|waitlist)\b",
    _re.IGNORECASE)
_COURSE_BUNDLE_RE = _re.compile(
    r"\b(?:certified|accredited)\b[^.]{0,60}" r"\b(?:expert|professional|"
    r"specialist|practitioner)\b|"
    r"\b(?:attack,\s*poison|poison\s*&\s*harden|curriculum\b|"
    r"what you'?ll learn)",
    _re.IGNORECASE)


def _is_course_cta_chrome(text):
    """True when `text` is a course/certification landing-page CTA."""
    t = text or ""
    if len(t) > 500:
        return False
    return bool(_COURSE_CTA_RE.search(t) and _COURSE_BUNDLE_RE.search(t))


_ARCHIVE_LABEL_DATE_RE = _re.compile(
    r"\b(?:insights|white-?paper|news|blog|articles?|posts?|press)\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+\d{1,2},?\s+\d{4}",
    _re.IGNORECASE)


def _is_archive_listing(text):
    """True when `text` is a blog ARCHIVE listing (date-stamped post titles).

    Live 17.09.26: `LM Serving white-paper July 24, 2026 Thinking Machines Lab
    Inkling, Explained: ... insights July 17, 2026 Top 7 ... insights July 6,
    2026 What Is a Good AI Harness?` -- pure listing chrome, zero prose, and the
    dates satisfied the technical-signal gate while the length cleared the
    >=90 "long prose" trust.

    Structural signature (measured, not topic-keyed): TWO OR MORE
    `<label> <Month D, YYYY>` occurrences AND no period anywhere.  A listing
    concatenates entry titles and never ends a sentence; prose that merely
    *names* two labels always carries a full stop.  Measured over the live
    buffer + world_model (435) + kta_log (764) + internet_learn_log (1695):
    1 hit, and that hit IS the leaking row -> 0 real-prose FPs; 10/10
    hand-written counter-cases survive.
    """
    if not text:
        return False
    if len(_ARCHIVE_LABEL_DATE_RE.findall(text)) < 2:
        return False
    return "." not in text


_ISSUE_ACTION_RE = _re.compile(r"issue body actions", _re.IGNORECASE)
_ISSUE_TEMPLATE_RE = _re.compile(
    r"confirm this is an issue with|describe the bug|underlying openai api|"
    r"this is an issue with the \w+ library",
    _re.IGNORECASE)


def _is_github_issue_chrome(text):
    """True when `text` is a GitHub ISSUE page (template label chain).

    Live 17.09.26: `Description AnasBenAmor10 opened on Jul 23, 2024 Issue body
    actions Confirm this is an issue with the Python library and not an
    underlying OpenAI API This is an issue with the Python library Describe the
    bug Error: You tried to access openai.embeddings ...` -- page furniture,
    zero insight; the date satisfied the technical-signal gate and the length
    cleared the >=90 trust.

    Keyed on TWO independent template markers, ANDed -- never one.  Measured:
    each marker ALONE hits a real-prose counter-case (`The issue body actions
    menu on GitHub ... should skip`, `A maintainer opened on Jul 23, 2024 an
    issue about the embedding client`, `Confirm this is an issue with the Python
    library and not an unrelated bug`, `Describe the bug in two sentences ...`),
    so a single phrase is a topic word, not chrome.  Requiring two keeps prose
    ABOUT issues learnable: measured 1 hit over the live buffer (the leaking
    row), 0 real-prose FPs, 0 hits over world_model/kta_log/internet_learn_log.
    """
    t = text or ""
    if len(t) > 900:
        return False
    return bool(_ISSUE_ACTION_RE.search(t) and _ISSUE_TEMPLATE_RE.search(t))


_PLAN_BULLET_RE = _re.compile(
    r"^[\s\"'\u201c\u201d]*[-*\u2022]\s*(?:input text|goal|content|task|"
    r"text source|output format)\s*:",
    _re.IGNORECASE | _re.MULTILINE)


def _is_plan_scaffold_echo(text):
    """True when `text` is the extractor's OWN plan echoed back as an insight.

    Live 17.09.26: `"\n   - Input text: A very long, fragmented, and repetitive
    list of vLLM documentation topics/headings. It's essentially a dump of
    section titles ...\n   - Goal: Extract the "ONE most valuable technical
    insight" from this` -- the 2B model returned its task plan instead of an
    insight. Same family as root cause AE (the plan voice), new paraphrase.

    Keyed on the plan's BULLET+LABEL form (a bullet whose field name is one of
    the extractor's own labels).  Measured: the bare phrases are topic words --
    `input text:` and `one most valuable technical insight` each hit a
    hand-written real-prose counter-case; the leading bullet-dash separates a
    plan line from a sentence and both FP counts drop to 0.
    """
    if not text:
        return False
    if len(text) > 1200:
        return False
    return bool(_PLAN_BULLET_RE.search(text))


# Wikipedia/company infobox FINANCIAL label chain (live 17.09.26: cycle_e_competitors
# stored the JetBrains infobox -- "CEO [ 1 ] Revenue 15,065,029,000 Czech koruna
# (2024) Operating income 2,041,654,000 Czech koruna (2024) Net income
# 2,479,110,000 Czech koruna (2024) Total assets 17,426,568,000 Czech koruna
# (2024) Number of employees 2,800 [ 2 ] Website jetbrains ." -- 248 chars WITH
# digits, so the >=90 long-prose trust and the technical-signal gate both fired).
#
# STRICTLY structural: >=2 occurrences of (financial-label, then a year in
# parens). Every naive literal was measured and REJECTED as a topic-word trap --
# `operating income` hit 3 hand-written real-prose counter-cases, `czech koruna`
# hit 3, `revenue [\d,]{6,}` hit 1. The label+year-paren co-occurrence is the
# discriminator: an infobox row repeats "Label <huge grouped number> ... (yyyy)",
# real prose does not. Measured: leak=True; 0 FP on 13 hostile counter-cases
# (incl. "Llama 2 (2023) and Llama 3 (2024) ...", "GPT-4 (2023) scored 91.2%
# while GPT-5 (2024) reached 95.1%", "Total assets ( 2023 ) were
# 17,426,568,000 koruna ..."); 0 hits over 3,056 longterm_episodes texts.
_FINANCIAL_LABEL_RE = _re.compile(
    r"(?:revenue|operating income|net income|total assets|number of employees)"
    r"[^()\n]{0,30}\(\s*(?:19|20)\d\d\s*\)", _re.IGNORECASE)


def is_financial_infobox(text):
    """True when text is a company/Wikipedia infobox financial label chain."""
    if not text:
        return False
    if len(text) > 1200:
        return False
    return len(_FINANCIAL_LABEL_RE.findall(text)) >= 2


# Service-status / maintenance BANNER chrome (live 17.09.26, class 26):
# mirror of internet_learner._is_maintenance_banner. The writer gate must
# refuse it too, or any other writer path lands a status-page announcement
# in the buffer. TWO structural markers ANDed (a dated window + the
# announcement voice) plus the head/tail condition that keeps prose ABOUT
# a downtime window learnable. Measured over 7,070 live corpus rows:
# 1 hit (the leaking row), 0 real-prose false positives.
_MAINT_STAMP = (r"[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}[ ,]+\d{1,2}:\d{2}\s*"
                r"(?:[APap][Mm]\s*)?[A-Z]{2,4}\b")
_MAINT_WINDOW_RE = _re.compile(
    r"%s\s*(?:to|\u2013|\u2014|-)\s*%s" % (_MAINT_STAMP, _MAINT_STAMP),
    _re.IGNORECASE)
_MAINT_VOICE_RE = _re.compile(
    r"\bthis service\b|\bdue to maintenance\b|\bfor maintenance\b"
    r"|^\s*login\b",
    _re.IGNORECASE)
_MAINT_EDGE = " \t\r\n.,;:!?-\u2013\u2014|/()[]\"'"


def _is_maintenance_banner(text, head_max=40, tail_max=40):
    """True when `text` is a service-status / maintenance BANNER.

    Same predicate as internet_learner._is_maintenance_banner: a dated
    downtime window announced in banner voice, with at most 40 chars of
    context before and after the announcement span.
    """
    t = text or ""
    w = _MAINT_WINDOW_RE.search(t)
    if not w:
        return False
    v = _MAINT_VOICE_RE.search(t)
    if not v:
        return False
    start = min(w.start(), v.start())
    end = max(w.end(), v.end())
    head = t[:start].strip(_MAINT_EDGE)
    tail = t[end:].strip(_MAINT_EDGE)
    return len(head) <= head_max and len(tail) <= tail_max

# Release-note CHANGELOG bullet chain (live 17.09.26, class 27): mirror of
# internet_learner._is_changelog_chain. The writer gate must refuse it too,
# or any other writer path lands a rendered release listing in the buffer.
_CV_VERB = (r"(?:added|enabled|released|improved|fixed|introduced|updated|"
            r"removed|deprecated|supported|launched|migrated|bumped)\b")
_CV_VERTOK = (r"(?:\[\s*\d{1,2}/\d{4}\s*\]|\[\s*v?\d+(?:\.\d+){1,3}\s*\]|"
              r"\bv?\d+\.\d+(?:\.\d+){1,2}\b|\[\s*[a-z-]+\s+\d{4}\s*\])")
_CHANGELOG_CHAIN_RE = _re.compile(
    r"(?:%s\s{0,3}(?:%s)[^,;.!?\n]{0,150}(?:\s|$)){3,}"
    % (_CV_VERTOK, _CV_VERB),
    _re.IGNORECASE)
_CHANGELOG_CONN_RE = _re.compile(
    r"\b(?:which|so|because|therefore|thus|hence|although|whereas|while)\b"
    r"|\bis exactly\b|\bmaking\b|\ballowing\b|\bgiving\b",
    _re.IGNORECASE)


def _is_changelog_chain(text):
    """True when `text` is a rendered release-note / changelog bullet chain."""
    t = text or ""
    if not t or not _CHANGELOG_CHAIN_RE.search(t):
        return False
    return not _CHANGELOG_CONN_RE.search(t)


def _is_metric_row_fragment(text):
    """True when `text` is a METRIC-LABEL block with no sentence in it.

    Writer-side mirror of internet_learner._is_metric_row_fragment --
    buffer_store must not import the learner (circular). Keep the two
    bodies identical in shape: a parenthesised ratio of counts
    (`(360 runs \u2014 60 payloads`) or a tilde-approximated product
    (`\u00d7 ~3 reps`) AND no finite verb. Measured 1 hit over the live
    buffer, 0 real-prose FPs on 11 counter-cases.
    """
    t = text or ""
    if not (_METRIC_RATIO_RE.search(t) or _METRIC_XTILDE_RE.search(t)):
        return False
    return not _FINITE_VERB_RE.search(t)

_METRIC_RATIO_RE = _re.compile(
    "\\([^)]{0,90}?\\d+\\s+\\w+\\s*[\u2014\u2013-]\\s*\\d+\\s+\\w+")
_METRIC_XTILDE_RE = _re.compile("\u00d7\\s*~\\s*\\d")
_FINITE_VERB_RE = _re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|can|could|will|would|should|must|"
    r"shows?|showed|uses?|used|adds?|added|improves?|improved|reduces?|reduced|"
    r"requires?|required|means|meant|allows?|allowed|gives?|gave|makes?|made|"
    r"takes?|took|found|finds?|reports?|reported|achieves?|achieved|provides?|provided|"
    r"measures?|measured|compares?|compared|covers?|covered|enables?|enabled|"
    r"offers?|delivers?|drops?|raises?|falls?|grows?|stays?|keeps?|holds?|writes?|reads?|"
    r"landed|remains?|differs?|validates|prefers|matters|assigns|sits?|came|comes?|"
    r"stores?|needs?|reached|published|conspired|trust)\b",
    _re.IGNORECASE)

def _is_sidebar_listing_chrome(text):
    """True when `text` is a blog-sidebar post-listing widget, not prose.

    Same narrow rule as `internet_learner._is_sidebar_listing_chrome`
    (root cause AH pitfall: a marker must live in BOTH files, or a leak passes
    the extraction gate and is caught only -- or never -- at the writer).
    Live 17.09.26 (class 29): a two-entry "recent posts" sidebar
    (`September 2, 2026 5 Views <headline> ... September 3, 2026 3 Views Our
    Picks <headline>.`) was stored by `cycle_a_technews`.
    Measured on the live buffer: 1 hit, IS the leak, 0 real-prose FPs.
    """
    return "views our picks" in (text or "").lower()


def _is_byline_counter_chrome(text):
    """True when `text` starts with a byline + timestamp + a `| N` counter.

    Live 17.09.26 (class 30): `cycle_e_competitors` stored
    `Kyle Orland and Benj Edwards - Dec 19, 2025 12:29 pm | 192 Which mines are
    mine, and which are AI?` -- an Ars Technica article-header chrome run
    (two-author byline, dateline, comment-counter) whose prose tail is a
    headline. Carries digits and a `?`, so every existing gate passed it.

    Measured on the live 300-row buffer: 1 hit and it IS the leak -> 0
    real-prose FPs on an 8-sentence control corpus. The broad `\|\s*\d{1,4}`
    was REJECTED: 1 hand FP (`We compared | 192 | and | 256 | batch sizes`)
    plus 3 live buffer hits. The time-anchored form is the one that is safe.
    """
    return bool(_re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)\s*\|\s*\d{1,4}\b",
                          text or "", _re.IGNORECASE))


# class 33/34 markers (live 17.09.26) -- see the two helpers below.
_REL_TIME_AGO_RE = _re.compile(
    r"\d{1,3}\s+(?:minutes?|hours?|days?)\s+ago", _re.IGNORECASE)
_NAV_WIDGET_LABEL_RE = _re.compile(
    r"\bfor\s+you\b[\s\S]{0,40}\blatest\b[\s\S]{0,40}\btrending\b",
    _re.IGNORECASE)


def _is_news_card_stub(text):
    """True when `text` is a news-card stub: dangling relative date + counter.

    Live 17.09.26 (class 33): `cycle_e_competitors` stored
    `OpenAI introduces framework for reporting model misalignment Sep 17 7.`
    -- a card headline whose relative-date label and its truncated counter
    tail were glued on. Only 70 chars, so the long-prose trust never applied
    and the trailing `7.` read as a digit-bearing sentence.

    Measured on the live 300-row buffer: 1 hit and it IS the leak -> 0
    real-prose FPs on a control corpus; 0/3,056 `longterm_episodes` texts.
    The counter must stay anchored at the very END: a bare `<Mon> <day>` is
    an ordinary date and matches real prose.
    """
    return bool(_re.search(
        r"\b[A-Z][a-z]{2}\s+(?:[1-9]|[12]\d|3[01])\s+\d{1,4}\.\s*$",
        text or ""))


def _is_relative_time_nav_chain(text):
    """True when `text` glues a relative-time bullet to a nav label chain.

    Live 17.09.26 (class 34): `cycle_e_competitors` stored
    `Game Developer * 4 hours, 34 minutes ago For You Latest Trending Tech
    Updates: Week of Sep 14 4 updates Babylon.` -- a site widget whose
    relative-time bullet, its `For You / Latest / Trending` nav labels and a
    `Tech Updates: Week of` roundup header ran together, with the counters
    reading as technical signal.

    Measured: 1 buffer hit and it IS the leak -> 0 real-prose FPs; 0/3,056
    `longterm_episodes`. Each part alone was REJECTED on measurement: the bare
    relative time matches `The job finished 4 hours, 34 minutes ago` and the
    `Tech Updates: Week of` header matches declarative prose -- only the
    ANDed pair is safe.
    """
    t = text or ""
    if not _REL_TIME_AGO_RE.search(t):
        return False
    return bool(_NAV_WIDGET_LABEL_RE.search(t))


# class 35 markers (live 17.09.26) -- see _is_date_heading_listing.
_FULL_DATE_RE = _re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4}\b")
_TITLE_WORD_RE = _re.compile(r"[A-Za-z][A-Za-z'./-]*")


# class 36 markers (live 17.09.26) -- see _is_repo_tab_statbar_chrome.
_REPO_TAB_CHAIN_RE = _re.compile(
    r"\bCode\s+Issues\s+Releases\b", _re.IGNORECASE)
_REPO_STATBAR_RE = _re.compile(
    r"\d+(?:\.\d+)?\s+MiB\s+[A-Za-z+#.]+\s+\d")


def _is_repo_tab_statbar_chrome(text):
    """True when `text` is a GitHub repo-page tab bar + language/size stat bar.

    Live 17.09.26 (class 36): `cycle_e_competitors` stored

      `Code Issues Releases 91 Packages Activity The glamourous AI coding agent
       for your favourite terminal <emoji> agentic-ai ai llms ravishing 4,181
       commits 161 branches 203 tags 972 MiB Go 98.`

    -- the repo page's tab chain, its one-line description, its topic tags and
    the stat bar, all in one run. Carries counters, so the technical-signal
    gate fired and no existing marker matched (`_is_gh_listing_row` keys on
    `Updated <date>` + `Public ...`, which this row has neither of).

    Measured on the live buffer: 1 hit and it IS the leak -> 0 real-prose FPs
    on 8 hostile counter-cases; 0/3,056 `longterm_episodes` texts. Each part
    alone was REJECTED on measurement: the bare tab words match
    `We filed code issues releases were delayed`, the counts match
    `The project has 4,181 commits, 161 branches and 203 tags`, and the bare
    language bar matches `The binary is 972 MiB and written in Go with 98%
    coverage`. Only the ANDed pair is page-specific.
    """
    t = text or ""
    if not _REPO_TAB_CHAIN_RE.search(t):
        return False
    return bool(_REPO_STATBAR_RE.search(t))


def _is_date_heading_listing(text):
    """True when `text` is a date-stamped headline listing (blog archive).

    Live 17.09.26 (class 35): two rows were buffered as insights --

      `June 27, 2025 Lessons Learned from Major Incident Response Cases June 8,
       2025 Top Cybersecurity Business Solutions You Need To Know February 1,
       2025 Hotel Hackers Using Fake Booking.`
      `July 2023 September 16, 2026 Building Materials/Construction ECMD Expands
       Southeast Presence with New DC in Ocala, FL September 16, 2026 AI
       Fastenal Quietly Acquired an ...`

    A date label glued to a headline, repeated across entries -- the archive
    listing shape. Carries dates, so the technical-signal gate fires.

    Measured on the live buffer: 2 hits and BOTH are the leak -> 0 real-prose
    FPs on 15 hostile counter-cases; 0/3,056 `longterm_episodes` texts. A bare
    `>=2 full dates` was REJECTED (15 buffer hits + 2 hand FPs -- real
    article/prose rows also carry a published AND an updated date), and BOTH
    `>=3 dates` and `>=2 dates plus a slash-breadcrumb` were rejected too: each
    re-flagged the class-24 archive-listing counter-case prose. The safe
    discriminator is the Title-Case density of a title listing.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    if len(_FULL_DATE_RE.findall(t)) < 2:
        return False
    # A title listing is Title-Case throughout; prose about the same dates is
    # not. (The `>=3 dates` and `>=2 dates AND slash-breadcrumb` forms were both
    # measured and REJECTED: they also flag the class-24 counter-case prose
    # `...posts under headings like Insights July 17, 2026 and News May 29, 2026,
    # but the agent should parse the article body.` -- see
    # test_blog_archive_listing_is_gated_on_both_paths, which caught it.)
    words = _TITLE_WORD_RE.findall(t)
    if not words:
        return False
    upper = sum(1 for w in words if w[:1].isupper())
    return upper >= 8 and upper / len(words) >= 0.5




# A page's own META blurb: `About <Title> ... is the latest <description>`
# (live 17.09.26, class 31). `cycle_g_security` stored the OWASP landing
# page's self-description as if it were a fact about the world -- the
# instance is ON-TOPIC, so relevance cannot be the discriminator (the
# class-22 lesson): the page's own promotional VOICE is.
#
# Two markers ANDed, both anchored: the leading `About` nav label AND the
# self-descriptive `is the latest` predicate. Measured over 8,078 live rows
# (buffer + junk + kta_log + learn log + world_model): 1 unique hit --
# exactly the leaking row -- and 0 FPs on a 10-sentence control corpus.
# Each marker ALONE was measured and REJECTED: `^About +token` matches 5
# real prose sentences (`About half of the quantized models ...`, `About
# GDPR compliance, ...`) and a bare `is the latest` matches 2 (`This paper
# is the latest work on post-training quantization ...`).
_PAGE_META_BLURB_RE = _re.compile(
    r"^About\s+\S[\s\S]{0,200}?\bis the latest\b")


def _is_page_meta_blurb(text):
    """True when `text` is the page's own `About <Title> ... is the latest` blurb."""
    return bool(_PAGE_META_BLURB_RE.search(text or ""))


# A GitHub repo-LISTING row (live 17.09.26, class 32) -- same narrow rule as
# internet_learner._is_gh_listing_row; keep both files in sync (root cause AH
# pitfall). `cycle_c_github` stored `Python 0 MIT 3,612 0 0 Updated Jun 13,
# 2025 ComfyUI Public Forked from Comfy-Org/ComfyUI The most powerful and
# modular stable diffusion GUI ...` -- language + counters + license + updated
# date + the repo's one-line description, zero insight.
#
# Measured on the live corpora: 2 buffer hits (both ARE the leak), 0 of 3,056
# longterm episodes, 0 of 323 test-asserted clean control literals. `Updated
# <Mon DD, YYYY>` alone is ordinary dates and `Public` alone is ordinary
# English ("Public health agencies ..."), so only the anchored PAIR is the
# listing label. A bare `Forked from` was REJECTED -- it hits a real episode.
_GH_LISTING_ROW_RE = _re.compile(
    r"\bUpdated\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b[\s\S]{0,40}?"
    r"\bPublic\s+(?:Forked|Code|Archive|Mirror)\b")


def _is_gh_listing_row(text):
    """True when `text` is a GitHub repo-listing row (counters + Updated + label)."""
    return bool(_GH_LISTING_ROW_RE.search(text or ""))


# class 37 markers (live 17.09.26) -- see _is_hn_feed_listing_chrome.
_AGO_PIPE_COMMENTS_RE = _re.compile(
    r"\b(?:minutes?|hours?|days?|weeks?|months?)\s+ago\s*\|\s*\d{1,5}\s*comments\b",
    _re.IGNORECASE)


def _is_hn_feed_listing_chrome(text):
    """True when `text` is a repeated aggregator feed listing (>=2 items).

    Live 17.09.26 (class 37): `cycle_b_papers` stored
    `AshleysBrain 3 hours ago | 9 comments 77 Neovim have a ~$800k Bitcoin
    donation sitting untouched since 2023 by jakemanger 1 hour ago | 6 comments
    741 Nvidia announces native GPU programming in Rust (developer.` -- a
    Hacker-News-style front-page listing: submitter handle + relative time +
    `| N comments` + points + headline, repeated for a second item and cut off
    mid-word. It carries digits and real headline prose, so the `>=90` length
    trust and the technical-signal gate both fired and no existing marker
    matched; the class-34 rule needs the `For You / Latest / Trending` labels.

    The discriminator is REPETITION: a feed row repeats the
    `<relative-time> | N comments` unit; real prose uses it at most once.
    Measured on the live 300-row buffer: 1 hit and it IS the leak -> 0
    real-prose FPs on a 12-sentence control corpus (incl. `The review took
    2 days ago | 4 comments per reviewer were recorded.` which the
    single-occurrence form would wrongly flag); 0/3,056 `longterm_episodes`.
    """
    t = text or ""
    return len(_AGO_PIPE_COMMENTS_RE.findall(t)) >= 2


# class 49 markers (live 18.09.26) -- see _is_hn_item_chrome.
_HN_ITEM_CHROME_RE = _re.compile(
    r"\bby\s+[\w.\-]+\s*\|\s*\d{1,5}\s+comments?\b[\s\S]{0,40}?\bon\s+Hacker\s+News\b"
    r"|\bNew ask Hacker News story\b",
    _re.IGNORECASE)


def _is_hn_item_chrome(text):
    """True when `text` is a single Hacker-News item row with its feed tail.

    Live 18.09.26 (class 49): `cycle_b_papers` stored

        September 16, 2026 New ask Hacker News story: Open-sourced jev
        architecture last year with model,paper and dataset Open-sourced jev
        architecture last year with model,paper and dataset 4 by
        nandakishor_ml | 2 comments on Hacker News.

    A single aggregator item: dateline + `New ask Hacker News story:` label +
    the headline twice + points + submitter handle + `| N comments` + the
    feed's own trailing `on Hacker News`. It carries digits, so the `>=90`
    length trust and the technical-signal gate both fired and no existing
    marker matched -- class 37 keys on REPETITION (`>=2` of the
    `<relative-time> | N comments` unit), and this row holds the unit once.

    The discriminator is the welded PAIR (submitter + `| N comments` + the
    aggregator's own name) or the feed's own item label -- never the bare
    words `Hacker News`, which are ordinary English topic words.
    Measured: 1 buffer hit and it IS the leak -> 0 real-prose FPs on a
    10-sentence control corpus and 0 of 518 test-asserted literals; 0/3,058
    `longterm_episodes`. The bare `by <handle> | N comments` form was
    REJECTED (2 control FPs: `A handle by someuser | 5 comments appeared ...`,
    `The model was reviewed by 3 authors | 2 comments each.`).
    """
    return bool(_HN_ITEM_CHROME_RE.search(text or ""))


# class 50 markers (live 18.09.26) -- see _is_nav_widget_run_chrome.
_NAV_WIDGET_RE = _re.compile(
    r"skip carousel|go to (?:previous|next) items|footer menu|back to top"
    r"|about scribd",
    _re.IGNORECASE)


def _is_nav_widget_run_chrome(text):
    """True when `text` is a run of a document-hosting page's nav widgets.

    Live 18.09.26 (class 50): `cycle_f_multi_domain` stored

        Language , English Upload Sign in Sign in Download free for 30 days
        Documents Get started with the community's uploads Skip carousel Go to
        previous items Overview (selected) Categories Go to next items Footer
        menu Back to top About About Scribd, Inc.

    A Scribd document page's own furniture chain: a language selector, two
    `Sign in` links, an upload CTA, the reader's widget labels and the footer
    menu labels. It carries digits (`30 days`), so the `>=90` length trust and
    the technical-signal gate both fired and no existing marker matched -- it
    is a label chain, not a `_is_nav_list` (that wants >=6 TitleCase tokens
    with no comma).

    The discriminator is REPETITION of the reader's/site's own furniture
    labels: one such label is ordinary prose (`Skip the carousel and go to
    the previous items`), a run of >=4 is a widget strip. Measured: 1 buffer
    hit and it IS the leak -> 0 real-prose FPs on an 18-sentence control
    corpus, 0 of the gate test file's 511 asserted literals; 0/3,058
    `longterm_episodes`. The lower thresholds were REJECTED: >=2 gave 4
    control FPs (`Back to top of the article, the footer menu lists the
    licence.`), >=3 still gave 2.
    """
    t = text or ""
    return len(_NAV_WIDGET_RE.findall(t)) >= 4


# class 64 markers (live 18.09.26) -- see _is_de_portal_fact_box_chrome.
_DE_PORTAL_FACTBOX_RE = _re.compile(
    r"\bAutor(?:in)?\s*:\s*[A-Z][A-Za-z]+\b[\s\S]{0,140}?K[\u00fc]rze\s*:")


def _is_de_portal_fact_box_chrome(text):
    """True when `text` is a German news portal's own fact-box label chain.

    Live 18.09.26 (class 64): `cycle_f_multi_domain` / root-cause-AG rotation
    stored a Banff travel article whose page furniture is

        Autor: Patrick Banff Nationalpark in Kuerze: Banff ist Kanadas
        aeltester Nationalpark (gegruendet 1885), liegt in Alberta auf 1.

    The portal's byline label (`Autor:`) welded to its summary label
    (`In Kuerze:`) plus body text. It carries digits (`1885`), so the `>=90`
    length trust and the technical-signal gate both fired; class 29/40/51
    byline helpers key on an English `By ...` / `Published` / `Share` shape,
    so a German pair never matched.

    The discriminator is the welded PAIR of the portal's OWN labels, not the
    words: `In Kuerze:` alone and `Autor: <Name>` alone are ordinary German
    prose and both flag real prose. Measured: 1 buffer hit and it IS the leak
    -> 0 real-prose FPs on a 11-sentence German/English control corpus
    (incl. `Autor: Jane Doe published the benchmark in 2024.`,
    `Autorin: Maria Schmidt analysierte in Kurze den Datensatz.`),
    0 of the gate test file's asserted literals, 0/3,058
    `longterm_episodes`.
    """
    return bool(_DE_PORTAL_FACTBOX_RE.search(text or ""))

# class 65 markers (live 18.09.26) -- see _is_prompt_echo_fragment.
_PROMPT_ECHO_FRAGMENT_RE = _re.compile(
    r"^\s*(?:The\s+)?shared underlying pattern[^\n]{0,30}?\bone sentence\s*\.?\s*$",
    _re.IGNORECASE | _re.MULTILINE)


def _is_prompt_echo_fragment(text):
    """True when `text` is the learner's OWN task template echoed back.

    Live 18.09.26 (class 65): a `Structural connection between ...` cycle
    stored the whole answer as

        Shared underlying pattern one sentence.

    the instruction it had been given, not an answer. Only 41 chars, so the
    `>=90` length trust never applied -- and `_INSTRUCTION_OPENER_RE` is
    START-anchored on imperative verbs, while this is a bare noun-phrase
    fragment; `_is_prompt_echo_bullet_chain` (class 42) needs >=2 bullets.

    The discriminator is the ANCHORED, whole-segment fragment: real answers
    embed the phrase in a sentence (`The shared underlying pattern is a
    closed-loop feedback system ...`, `Both systems share an underlying
    pattern: a feedback loop.`) and stay learnable. Measured: 1 buffer hit
    and it IS the leak -> 0 FPs on 5 clean prose counter-cases, the gate
    test file's asserted literals, and 0/3,058 `longterm_episodes`.
    """
    return bool(_PROMPT_ECHO_FRAGMENT_RE.search(text or ""))

# class 66 markers (live 18.09.26) -- see _is_generated_plan_echo_fragment.
_PROMPT_PLAN_ECHO_RE = _re.compile(
    r"^\s*(?:KI-Performance-Optimierung|AI Performance Optimization"
    r"|Performance Optimization)\s*:[\s\S]{0,200}?\+[\s\S]{0,120}?[\r\n]+\s*\d{1,2}\.\s*$",
    _re.IGNORECASE | _re.MULTILINE)


def _is_generated_plan_echo_fragment(text):
    """True when `text` is a generated PLAN the learner fed back as an answer.

    Live 18.09.26 (class 66): the `Structural connection between energy
    efficiency and ...` cycles stored their own deliverable list FIVE times,
    as a single truncated fragment

        KI-Performance-Optimierung: Python-Skript fuer RAM/Disk/Cron-Monitoring
        + Optimierungsvorschlaege + Skill + Cron-Job alle 12h
        2.

    Title-with-colon + a `+`-joined feature list + a DANGLING list marker and
    an abrupt stop -- the model enumerated a plan and the extractor kept only
    the first item plus the marker. It is the agent's own prior output, not
    world knowledge: all five copies came from its own `Structural connection`
    questions. The dangling `2.` is what marks it as a truncated list; a
    complete plan (`The plan is: 1. collect metrics 2. aggregate 3. report.`)
    ends in prose and stays learnable.

    The discriminator is the PAIR (own-artifact title + `+`-list + dangling
    marker): the bare title alone hits 1 real `longterm_episodes` row and the
    bare dangling marker alone flags ordinary numbered prose (`Our toolchain:
    script + docs + tests + CI.\n2.`). Measured: 5 buffer hits, ALL the same
    leak family -> 0 real-prose FPs on a 7-sentence control corpus, 0 of the
    gate test file's asserted literals, 0/3,058 `longterm_episodes`.
    """
    return bool(_PROMPT_PLAN_ECHO_RE.search(text or ""))

# class 51 markers (live 18.09.26) -- see _is_news_byline_share_header.
_BYLINE_WEEKDAY_SHARE_RE = _re.compile(
    r"\bBy\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+\w+day,[\s\S]{0,40}?\bShare\b")


def _is_news_byline_share_header(text):
    """True when `text` is a broadcast-news article header run.

    Live 18.09.26 (class 51): `cycle_a_technews` stored

        ABCNews By Mason Leib Thursday, April 30, 2026 Share A software
        company founder went viral this week after sharing a post on social
        media describing how an AI agent threw his business into chaos for
        30 hours.

    A news site's own furniture: brand chip + TWO-word byline + full weekday
    dateline + the reader's `Share` control, glued to the article lede. It
    carries digits (`30`), so the `>=90` length trust and the
    technical-signal gate both fired and no existing marker matched --
    class 29 strips a LEADING byline and class 40 keys on `Published`, not
    on the weekday dateline + `Share` pair.

    The discriminator is the welded PAIR (byline + full weekday dateline
    within 40 chars of the reader's own `Share` control), never the bare
    words -- `By <First> <Last>` alone is ordinary prose and a weekday date
    alone is an ordinary date. Measured: 1 buffer hit and it IS the leak ->
    0 real-prose FPs on a 14-sentence control corpus, 0 of the gate test
    file's 511 asserted literals; 0/3,058 `longterm_episodes`. The
    `date + Share` pair alone was REJECTED (2 test-literal FPs).
    """
    return bool(_BYLINE_WEEKDAY_SHARE_RE.search(text or ""))


# class 38 markers (live 17.09.26) -- see _is_marketing_hero_cta_chrome.
_HERO_CTA_STAR_RE = _re.compile(
    r"\[\*\]\s+(?:With|Mit)\s+(?:over|\u00fcber)\s+[\d.,]+",
    _re.IGNORECASE)

# The SAME hero WITHOUT the `[*]` marker (live 18.09.26, class 54): the
# competitor page renders the adoption-brag bullet with a `->` instead, so the
# class-38 marker never fired:
#   "Any Editor Terminal interface, desktop app, and IDE extensions Read the
#    docs -> Open Source AI Coding Agent With over 160,000 GitHub Stars, 900
#    contributors, and over 13,000 commits, OpenCode is used and trusted by
#    over 7."
# Stored TWICE in one buffer (rows 14 and 297, byte-identical). The existing
# helper's guard was one variant too narrow -- the same pattern as root cause
# AO -- so the guard is relaxed rather than a fourth class added.
#
# The discriminator is the FULL brag triple in one sentence (stars AND
# contributors AND commits), which a landing-page hero writes as a list and
# real prose never does. Measured (18.09.26): 2 live buffer hits, BOTH are the
# leak; 0 of 3,058 longterm_episodes; 0 of 1,003 asserted gate-test literals;
# 0 prose controls (incl. "With over 195,000 GitHub stars and 950
# contributors, the project ships a desktop app.").
_HERO_ADOPTION_BRAG_RE = _re.compile(
    r"With\s+over\s+[\d.,]+[kKmM]?\s+GitHub\s+[Ss]tars,\s*"
    r"[\d.,]+[kKmM]?\s+contributors,\s*and\s+over\s+[\d.,]+[kKmM]?\s+commits",
    _re.IGNORECASE)


def _is_marketing_hero_cta_chrome(text):
    """True when `text` is a landing-page hero CTA chain with a [*] marker.

    Live 17.09.26 (class 38): `cycle_e_competitors` stored the German form
    `Terminal-Interface, Desktop-App und IDE-Extension Doku lesen Der
    Open-Source AI-Coding-Agent [*] Mit ueber 195,000 GitHub-Stars, 950
    Contributors und ueber 13,000 Commits wird OpenCode von ueber 16M
    Entwickler:innen jeden Monat genut` -- 247 chars. Rows 17 and 87 in the
    same buffer hold the SAME page hero in English (`Available as a terminal
    interface, desktop app, and IDE extension Read docs The open source AI
    coding agent [*] With over 195,000 GitHub stars, ...`), so this is ONE
    leak shape stored three times, not a one-off.

    An availability line + a nav CTA (`Read docs` / `Doku lesen`) + the
    product tagline + a `[*]` footnote marker + the adoption-brag counter
    sentence. The counters and the CTA verb made every existing gate pass;
    `_is_nav_list` wants >=6 TitleCase tokens with no comma.

    Marker = the `[*]` marker immediately followed by the brag opener
    `With over` / `Mit ueber`. Measured: 3 live buffer hits, ALL THREE are
    this leak -> 0 real-prose FPs on a 26-sentence hostile control corpus
    (incl. footnote-style `Required fields are marked with [*] in the form`,
    `Read docs to learn how the [*] wildcard expands`, and bare `With over
    5,000 examples the dataset is large enough`); 0/3,056 `longterm_episodes`.
    The looser `(?:Read docs|Doku lesen) ... [*]` form was REJECTED on
    measurement (3 control FPs).
    """
    if _HERO_CTA_STAR_RE.search(text or ""):
        return True
    # the same hero rendered with a `->` bullet instead of the `[*]` marker
    # (class 54, 18.09.26)
    return bool(_HERO_ADOPTION_BRAG_RE.search(text or ""))


# class 40 markers (live 17.09.26) -- see _is_byline_published_article_header.
_BYLINE_PUBLISHED_RE = _re.compile(
    r"\bBy\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+Published\s+\d{1,2}\s+"
    r"[A-Z][a-z]{2,9}\s+\d{2}\b")


def _is_byline_published_article_header(text):
    """True when `text` carries an article-header byline + `Published <dd Mon yy>`.

    Live 17.09.26 (class 40): two rows in the 300-row buffer had passed BOTH
    gates --
      `Pro Why CIOs are paying closer attention to physical security By Mark
       Coates Published 14 September 26 Connected physical security is
       reshaping how CIOs approach risk, data and resilience.`  (188 chars)
      `Pro Why every enterprise needs an AI model exit strategy By Ganesh
       Padmanabhan Published 15 September 26 Model flexibility helps
       enterprises protect workflows, ...`  (210 chars)
    -- an editorial chip + headline + two-word byline + abbreviated dateline,
    glued to the article's own lede. The `>=90` long-prose trust accepted them
    and the `14 September 26` / `15 September 26` digits fed the
    technical-signal gate, so no existing marker matched.

    NOT the same shape as `_strip_byline_prefix`, which only removes a LEADING
    byline; here the byline sits AFTER the headline, mid-text. Discriminator =
    the page's own furniture pair `By <First> <Last> Published <dd> <Mon> <yy>`
    (the byline is not separated from `Published`, unlike the
    `Written by ... \u00b7 Published ...` form of class 29).

    Measured: 2 live buffer hits and BOTH are the leak -> 0 real-prose FPs on a
    10-sentence hostile control corpus (incl. `By Mark Coates Published research
    shows that connected physical security is reshaping how CIOs approach
    risk.`, `The paper was published in September 2026 by the ACM ...`,
    `Ganesh Padmanabhan wrote about AI model exit strategies in a 2024
    enterprise report.`); 0/3,056 `longterm_episodes`.
    """
    return bool(_BYLINE_PUBLISHED_RE.search(text or ""))


# class 39 markers (live 17.09.26) -- see _is_platform_selector_listing_chrome.
_PLATFORM_SEL_SUBREDDIT_RE = _re.compile(
    r"(?:macOS|Windows|Linux)\s+(?:Apple\s+Silicon|Intel)\s*\([^)]*\)"
    r"[\s\S]{0,200}?\br/\w+\s+community\b")


def _is_platform_selector_listing_chrome(text):
    """True when `text` glues a platform selector to a subreddit feed row.

    Live 17.09.26 (class 39): `cycle_b_papers` stored
    `OS/iOS: macOS Apple Silicon (arm64) macOS Apple Silicon (arm64, KleidiAI
    enabled) DISABLED macOS Intel (x64)… 25 r/MachineLearning community 3h ago
    ICLR 2027 table font sizes [D] I am preparing an ICLR 2027 submission using
    the official LaTeX style.` -- a release page's OS/architecture selector
    (with a DISABLED entry, truncated at `…`) followed by a subreddit feed row
    (upvote count + `r/... community` + relative time) and a forum post title.

    The selector's counters and the `ICLR 2027` digits fed the technical-signal
    gate; the shape carries real-looking prose, so the length trust passed it.

    Marker = a `macOS Apple Silicon (arm64)`-style selector within 200 chars of
    `r/<name> community` -- the feed widget's own label. Measured: 1 live buffer
    hit and it IS the leak -> 0 real-prose FPs on a 21-sentence hostile control
    corpus (incl. `Supported targets: macOS Apple Silicon (arm64) and macOS Apple
    Silicon (arm64, KleidiAI enabled).`, `The r/MachineLearning community 3h ago
    posted macOS Intel (x64) benchmarks.`); 0/3,056 `longterm_episodes`.
    The arm64-paren+relative-time form was REJECTED: 3 control FPs.
    """
    return bool(_PLATFORM_SEL_SUBREDDIT_RE.search(text or ""))


# A deep-read PROMPT echoed back as the answer (live 17.09.26): the model
# parroted the learner's own task template as a bullet chain --
#   - Input is a list of daily paper submissions with titles, authors, ...
#   - I need to identify the single most valuable technical insight ...
#   - Output must be a sin
# It cleared the >=90 length trust and the technical-signal gate, and no
# marker matched: _INSTRUCTION_OPENER_RE is START-anchored (this text opens
# with a quote + newline) and _is_nav_list wants TitleCase tokens.
# The discriminator is the BULLET-CHAIN form of an instruction voice: a real
# fact never arrives as >=2 bullets each opening with a task-frame word.
_PROMPT_ECHO_BULLET_RE = _re.compile(
    r"(?:^|[\r\n])\s*[-*\u2022]\s+(?:Input\b|Output\b|I need to\b|"
    r"I must\b|I should\b|The task\b|Identify the\b|Steps?\b|"
    r"Constraints?\b|Format\b)",
    _re.IGNORECASE)


def _is_prompt_echo_bullet_chain(text):
    """True when the text is the learner's own prompt echoed as bullets."""
    try:
        return len(_PROMPT_ECHO_BULLET_RE.findall(text)) >= 2
    except TypeError:
        return False


# The distillation LLM's own VERDICT ABOUT THE PAGE returned as an "insight"
# (live 17.09.26, class 44). cycle_h_efficiency learned
#
#   "The provided text is a boilerplate webpage footer containing no technical
#    information, only navigation links and legal notices."
#
# This is not page chrome and not a prompt echo -- it is the 2B model's SOURCE
# ASSESSMENT ("the input has no technical signal") being stored as knowledge.
# 127 chars, and the word "technical" fed the technical-signal gate, so nothing
# matched. A verdict about the input can never be a learning: REJECT.
#
# The discriminator is the FURNITURE VOCABULARY welded to the source noun --
# `_SRC` ("provided/given/supplied/extracted text|document|page|content|
# snippet|input") within 100 chars of a copula/contain verb, within a further
# 60 chars of a page-furniture noun (boilerplate / webpage footer / navigation
# links / nav menu / legal notices / cookie banner / site furniture / page
# chrome). No single part is enough: "The provided text is a transcript ...",
# "Boilerplate license headers should be stripped ..." and even an agent's own
# "The agent's provided input had no technical signal ..." all stay learnable.
# Measured: 1 hit over the live buffer (= this leak), 0 over 5,582 junk-log
# rows, 3,056 longterm_episodes, 787 string literals extracted from the gate
# test file, and 15 of 16 hand-written hostile counter-cases (the one hit is a
# meta-sentence ABOUT this gate, i.e. correct behaviour).
_VERDICT_SRC_RE = _re.compile(
    r"\b(?:provided|given|supplied|extracted)\s+"
    r"(?:text|document|page|content|snippet|input)\b",
    _re.IGNORECASE)
_VERDICT_FURNITURE_RE = _re.compile(
    r"\b(?:boilerplate|webpage\s+(?:footer|header)|navigation\s+links?|"
    r"nav(?:igation)?\s+menus?|legal\s+notices?|cookie\s+(?:banner|notice)|"
    r"site\s+furniture|page\s+chrome)\b",
    _re.IGNORECASE)
_VERDICT_VERB_RE = _re.compile(
    r"\b(?:is|are|appears?\s+to\s+be|consists?\s+of|contains?\s+only|"
    r"contains?\s+no)\b",
    _re.IGNORECASE)


def _is_source_verdict_chrome(text):
    """True when the text is the LLM's verdict ABOUT the page, not knowledge.

    Live 17.09.26 (class 44): see the module comment above. The three parts
    must co-occur in order and close together -- a source noun, a copula/
    contain verb, then page-furniture vocabulary.
    """
    t = text or ""
    src = _VERDICT_SRC_RE.search(t)
    if not src:
        return False
    verb = _VERDICT_VERB_RE.search(t, src.end())
    if not verb or verb.start() - src.end() > 100:
        return False
    furn = _VERDICT_FURNITURE_RE.search(t, verb.end())
    if not furn or furn.start() - verb.end() > 60:
        return False
    return True


# class 45 markers (live 17.09.26) -- see _is_operator_spotlight_chain.
_OPERATOR_SPOTLIGHT_RE = _re.compile(r"Operator\s+Spotlight", _re.IGNORECASE)


def _is_operator_spotlight_chain(text):
    """True when an "Operator Spotlight" widget row was stored TWICE in one record.

    Live 17.09.26 (cycle_a_technews): `July 24, 2026 cahaseler 016 Operator
    Spotlight: Scripts Are Cheaper Than Tokens Operator Spotlight: Brocktree
    runs ~200 AI agents in SpaceMolt through one stationary hub bot, and trusts
    none of them to plan.` -- a slug + issue number + the widget's headline
    repeated as its own card title.  207 chars WITH digits, so the >=90
    long-prose trust and the technical-signal gate both fired and no existing
    marker matched.

    Discriminator is the REPETITION of the widget's own label (>= 2 hits), not
    the phrase: bare `Operator Spotlight` alone and the pair `Operator Spotlight
    ... hub bot` both hit real prose ("Our operator spotlight feature rotates
    weekly ...").  Measured: 1 buffer hit and it IS the leak; 0 of 3,058
    longterm_episodes; 0 of 816 literal controls.
    """
    t = text or ""
    return len(t) <= 400 and len(_OPERATOR_SPOTLIGHT_RE.findall(t)) >= 2


# class 46 markers (live 17.09.26) -- see _is_preprint_header_chain.
_PREPRINT_CHAIN_RE = _re.compile(
    r"([A-Z][A-Za-z0-9][\w\- ]{6,60}?)\s+(\d{1,2}/\d{1,2}/\d{4})\s+"
    r"([A-Z0-9][\w\-: ]{5,60})[.\s]*$")
_PREPRINT_TITLEWORD_RE = _re.compile(r"\b[A-Z][a-zA-Z0-9]{2,}\b")
_PREPRINT_LOWERWORD_RE = _re.compile(r"\b[a-z]{4,}\b")


def _is_preprint_header_chain(text):
    """True when a paper title + slash-date + project-title header chain landed.

    Live 17.09.26 (cycle_b_papers): `Activations for 1-bit LLMs 10/21/2024
    1-bit AI Infra: Part 1.` -- a GitHub README banner (paper title, date,
    project title), not knowledge.  Only 61 chars, so the length trust never
    applied; the date fed the technical-signal gate.

    The discriminator is the SHAPE: a TitleCase head of >= 2 words, a
    slash-date, a project title, and -- crucially -- NO lowercase word of 4+
    letters anywhere.  Prose about a date always carries one ("The paper was
    published on 10/21/2024 ..."), and `Attention Is All You Need 6/12/2017
    Attention Is All You Need` IS listing chrome, so flagging it is correct.
    Measured: 1 buffer hit and it IS the leak; 0 of 3,058 longterm_episodes;
    0 of 816 literal controls; 0 of 8 prose counter-cases.
    """
    t = text or ""
    if len(t) > 300:
        return False
    g = _PREPRINT_CHAIN_RE.search(t)
    if not g:
        return False
    if len(_PREPRINT_TITLEWORD_RE.findall(g.group(1))) < 2:
        return False
    return len(_PREPRINT_LOWERWORD_RE.findall(t)) == 0


# class 47 markers (live 17.09.26) -- see _is_personal_blog_nav_chain.
_BLOG_ABOUT_RE = _re.compile(r"\bAbout\b")


def _is_personal_blog_nav_chain(text):
    """True when a personal blog's header nav run landed ("About x Work Writing About").

    Live 17.09.26: `About \u2715 AAKASH SETHI Work Writing About June 26, 2026
    \u00b7 AI Engineering Haystack: ...` -- a Wordpress/Ghost header nav chain
    glued to the post headline and lede.  252 chars WITH digits.

    The dismiss glyph co-occurring with `About` twice is the tell: ordinary
    prose says "About" once.  Measured: 1 buffer hit and it IS the leak; 0 of
    3,058 longterm_episodes; 0 of 816 literal controls; 0 of 12 hostile controls
    (incl. `About 200 agents run in the simulation ...` and `About the operator
    spotlight: ...`).
    """
    t = text or ""
    return (len(t) <= 400 and "\u2715" in t
            and len(_BLOG_ABOUT_RE.findall(t)) >= 2)


# class 48 markers (live 17.09.26) -- see _is_pricing_hero_chrome.
_PRICING_HERO_RE = _re.compile(r"%\s*OFF\s+base pricing", _re.IGNORECASE)


def _is_pricing_hero_chrome(text):
    """True when a competitor landing-page pricing HERO was stored as insight.

    Live 17.09.26 (cycle_e_competitors): `Flash 75% OFF base pricing for a
    limited time Powered by IDEs Proven in Benchmarks IntelliJ IDEA Engine Top
    performer on SWE-Rebench 10+ models supported via BYOK Plan on a powerful
    model, implement on a fast one.` -- a promo banner, not intelligence.

    Discriminator is the whole promo phrase, not the parts: bare `% OFF`, `base
    pricing`, `for a limited time` and `Powered by` all appear in real prose and
    real docs.  Measured: 1 buffer hit and it IS the leak; 0 of 3,058
    longterm_episodes; 0 of 816 literal controls.
    """
    t = text or ""
    return len(t) <= 400 and bool(_PRICING_HERO_RE.search(t))

# A docs-site CTA welded onto a SERP run by `…;` (live 18.09.26, class 53): the
# learner stored
#   "Efficient Transformers Library - GitHub — This library provides ...
#    performant on …; Welcome to Efficient-Transformers Documentation! —
#    Install Efficient-Transformers. 1. Model download and Optimize ..."
# - two search-result titles each with its `Title — snippet` body, welded by
# `…;`, the second one carrying the docs site's own CTA.
#
# A generic `…;` / multi-snippet rule was TRIED and is WRONG: the class-24 test
# (`test_german_dictionary_serp_chrome_is_gated_on_both_paths`) records that it
# was rejected because real rows carry genuine technical prose
# ("Parallelism and Scaling - vLLM — ... experts …; Optimization and Tuning -
# vLLM — ..."). The discriminator is therefore the docs site's OWN navigation
# label, not the separator: a run of `…;` immediately followed by the
# documentation landing page intro `Welcome to <Product> Documentation`.
# Real prose mentions a welcome or a documentation install step inside a
# sentence, which never sits directly on the welded title boundary.
# Measured (18.09.26): 1 live buffer hit and it IS the leak; 2 buffer_junk
# rows of the same family; 0 of 3,058 longterm_episodes; 0 of 1,003 asserted
# gate-test literals; 0 prose controls.
_DOCS_CTA_AFTER_SERP_RE = _re.compile(
    r"\u2026\s*;\s*Welcome to\s",
    _re.IGNORECASE)


def _is_docs_cta_serp_run(text):
    """True when a SERP run ends on a docs site's `Welcome to …` page intro."""
    return bool(_DOCS_CTA_AFTER_SERP_RE.search(text or ""))


# class 55 markers (live 18.09.26) -- see _is_news_aggregator_listing_run.
# A press round-up: `| <Site> <Mon DD, YYYY> <Headline>` repeated.
_PIPE_SITE_DATE_HEAD_RE = _re.compile(
    r"\|\s*[A-Z][A-Za-z0-9]*\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
    r"\d{1,2},\s+\d{4}\s+[A-Z]")


def _is_news_aggregator_listing_run(text):
    """True when `text` is a run of press-roundup rows (class 55, 18.09.26).

    Each pipe segment is one syndication row: `| <Site> <Mon DD, YYYY>` followed
    by a Capitalised headline. The discriminator is REPETITION: one such segment
    is ordinary prose, a run of >=2 is a listing. Measured: 1 buffer hit and it
    IS the leak -> 0 real-prose FPs on a 14-sentence control corpus, 0 test
    literals, 0/3,058 `longterm_episodes`.
    """
    return len(_PIPE_SITE_DATE_HEAD_RE.findall(text or "")) >= 2


# class 56 markers (live 18.09.26) -- see _is_devto_card_tail.
_DEVTO_CARD_TAIL_RE = _re.compile(r"\b\d{1,4}\s+projects?\s*\|\s*dev\.?\s*$")


def _is_devto_card_tail(text):
    """True when `text` ends on a dev.to cross-post card counter bar (class 56).

    The anchor is the TAIL (`$`), because `2 projects | dev.to` mid-sentence is
    ordinary prose. Measured: 1 buffer hit and it IS the leak -> 0 FPs, 0 test
    literals, 0/3,058 episodes.
    """
    return bool(_DEVTO_CARD_TAIL_RE.search(text or ""))


# class 57 markers (live 18.09.26) -- see _is_services_menu_chain.
_SERVICE_MENU_AND_RE = _re.compile(r"\b[A-Z]{2,}\s*&\s*[A-Z]{2,}\b")
_SERVICE_LABEL_RE = _re.compile(
    r"\b(?:RPA\s+Development|Computer\s+Vision|AI\s+Integration"
    r"|AI\s+Product\s+Engineering)\b")


def _is_services_menu_chain(text):
    """True when `text` is an agency/services page's menu strip (class 57).

    An ALL-CAPS `X & Y` nav label ANDED with >=2 service titles. Measured: 1
    buffer hit and it IS the leak; 0 FPs on the control corpus, 0 test
    literals, 0/3,058 episodes. The bare ALL-CAPS-token count was REJECTED
    (>=4 gave 36 buffer hits, 384 episodes and a control FP).
    """
    t = text or ""
    if not _SERVICE_MENU_AND_RE.search(t):
        return False
    return len(_SERVICE_LABEL_RE.findall(t)) >= 2


# class 58 markers (live 18.09.26) -- see _is_pagination_newsletter_widget.
_PAGINATION_NEWSLETTER_RE = _re.compile(
    r"\bPrevious\s+Page\s+\d+\s+of\s+\d+\s+Next[\s\S]{0,200}?"
    r"\bNew articles by email\b", _re.IGNORECASE)


def _is_pagination_newsletter_widget(text):
    """True when `text` is a blog archive widget run (class 58, 18.09.26).

    Live 18.09.26: `cycle_h_efficiency` stored

        Herv\u00e9 Zwirn Sep 14, 2026 Afshin Khadangi Causal Liability Theory
        and the AI Consciousness Fallacy Afshin Khadangi Sep 14, 2026 Previous
        Page 1 of 63 Next The Consciousness AI New articles by email One a
        week, when there is something worth sending.

    The page's own pagination widget (`Previous Page N of M Next`) welded to
    its newsletter promo (`New articles by email`). 247 chars with dates, so
    the >=90 length trust and the technical-signal gate both fired. The
    discriminator is the WINDOW: the two widget labels sit within 200 chars of
    each other on one archive page. Measured: 1 buffer hit and it IS the leak;
    0 FPs on 12 control sentences (`New articles by email are sent weekly, and
    the archive lists Previous Page 4 of 9 Next in the footer.` is a whole-text
    FP for the unbounded AND, hence the window); 0/666 test literals;
    0/3,058 episodes.
    """
    return bool(_PAGINATION_NEWSLETTER_RE.search(text or ""))



# class 59 markers (live 18.09.26) -- see _is_fullscreen_toggle_chrome.
_FULLSCREEN_TOGGLE_RE = _re.compile(
    r"\bEnter fullscreen mode\s+Exit fullscreen mode\b", _re.IGNORECASE)


def _is_fullscreen_toggle_chrome(text):
    """True when `text` is a code-block FULLSCREEN toggle widget (class 59).

    Live 18.09.26: `cycle_b_papers` stored

        Hugging Face's Transformers: from transformers import pipeline llm =
        pipeline ( ' text-generation ' , model = ' gpt-3 ' ) Enter fullscreen
        mode Exit fullscreen mode Integrate Z3 : Initialize Z3 and define your
        logical constraints.

    A publishing platform's own code-block control pair (`Enter fullscreen
    mode` + `Exit fullscreen mode`, glued with a single space) embedded between
    a code excerpt and the article prose. 230 chars with an `import`, so the
    >=90 length trust and the technical-signal gate both fired. The
    discriminator is the WIDGET PAIR, not either label: a single `Enter
    fullscreen mode` is ordinary UI prose. Measured: 1 buffer hit and it IS the
    leak; 0 FPs on prose controls (`The editor lets you enter fullscreen mode
    and exit fullscreen mode with the same button.` stays learnable because the
    labels are not space-glued); 0/679 test literals; 0/3,058 episodes.
    """
    return bool(_FULLSCREEN_TOGGLE_RE.search(text or ""))



# class 60 markers (live 18.09.26) -- see _is_hashtag_run_after_headline.
_TAG_RUN_RE = _re.compile(
    r"(?:#\s*[A-Za-z][A-Za-z0-9_-]{1,}\s+){2,}#\s*[A-Za-z][A-Za-z0-9_-]{1,}")
_TITLE_HEADLINE_RE = _re.compile(r"(?:[A-Z][A-Za-z0-9'-]*\s+){4,}$")


def _is_hashtag_run_after_headline(text):
    """True when `text` is a post headline welded to its tag run (class 60).

    Live 18.09.26: `cycle_e_competitors` stored

        AI Coding Agents Must Reduce Maintenance Costs, Not Just Write Code
        # ai # webdev # tutorial # productivity A coding agent that drops 800
        lines into your repo in 90 seconds feels productive.

    A publishing platform's title + its tag strip, glued to the article lede.
    The discriminator is STRUCTURAL: >=3 whitespace-adjacent hashtags AND a
    TitleCase headline (>=4 capitalized words) immediately before them. The
    bare hashtag COUNT was REJECTED -- `>=3` gave 71 episodes and 2 control FPs,
    `>=4` still 42 episodes and 1 control FP; adjacency alone still flagged
    3 by-construction controls. Only count + headline measured 0 FPs on
    9 controls, 0/689 test literals, 0/3,058 episodes.
    """
    t = text or ""
    for m in _TAG_RUN_RE.finditer(t):
        if _TITLE_HEADLINE_RE.search(t[:m.start()]):
            return True
    return False



# class 61 markers (live 18.09.26) -- see _is_dated_tag_strip_chrome.
_DATED_TAG_STRIP_RE = _re.compile(r"\u00b7\s*#\s*")
_TAG_STRIP_TOKEN_RE = _re.compile(
    r"[A-Za-z0-9\u00c0-\u024f\u4e00-\u9fff][\w'\u00c0-\u024f\u4e00-\u9fff-]*")


def _is_dated_tag_strip_chrome(text):
    """True when `text` is a dated card headline + tag strip (class 61).

    Live 18.09.26: `cycle_d_docs` stored (twice, byte-identical rows)

        LLM Complete Guide -- From Parameters to Optimization, Everything About
        Local LLM Serving 2026-02-26 \u00b7 # AI \ud65c\uc6a9 vLLM LLM serving GPU optimization
        PagedAttention Qwen3 The first tool engineers encounter when trying to
        serve LLMs on local GPUs is vLLM.

    A blogging platform's card header: `<headline> <date> \u00b7 # <tag strip>` glued
    to the article lede. 248 chars with a date, so the >=90 length trust and
    the technical-signal gate both fired. The `\u00b7 #` separator alone is ordinary
    prose (`Published 2026-02-26 \u00b7 # ai is a tag used on the blog.`), so the
    discriminator is DENSITY: the tag strip itself is a run of >=5 tokens with
    >=3 mixed-case or digit-bearing tokens, which real prose after `\u00b7 #` never
    is. Measured: 2 buffer hits, BOTH are the leak; 0 control FPs; 0/689 test
    literals; 0/3,058 episodes. A pure token-count threshold was REJECTED (2
    control FPs at every threshold 5..7).
    """
    t = text or ""
    for m in _DATED_TAG_STRIP_RE.finditer(t):
        seg = t[m.end():m.end() + 120]
        toks = _TAG_STRIP_TOKEN_RE.findall(seg)
        if len(toks) < 5:
            continue
        dense = sum(1 for x in toks[:10]
                    if any(c.isupper() for c in x) or any(c.isdigit() for c in x))
        if dense >= 3:
            return True
    return False



# class 62 markers (live 18.09.26) -- see _is_model_listing_run_chrome.
_UPDATED_DATE_RE = _re.compile(r"\bUpdated\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b")
_SIZE_DOT_UPDATED_RE = _re.compile(
    r"\u00b7\s*\d+(?:\.\d+)?[BM]\s*\u00b7\s*Updated")


def _is_model_listing_run_chrome(text):
    """True when `text` is a HuggingFace model-listing row run (class 62).

    Live 18.09.26: `cycle_h_efficiency` stored

        13 ChenMnZ/Llama-3-8b-instruct-BlockAP-w2g64 Text Generation \u00b7 2B \u00b7
        Updated Jul 21, 2024 \u00b7 12 ChenMnZ/Llama-3-8b-instruct-BlockAP-w2g128
        Text Generation \u00b7 2B \u00b7 Updated Jul 21, 2024 \u00b7 15 View 4
        collections Papers 8 arxiv: 2505.

    A model hub's search-result rows: download count + `owner/model` + task
    label + size + `Updated <Mon DD, YYYY>`. 228 chars with a date, so the
    >=90 length trust and the technical-signal gate both fired. The repeated
    `Updated <date>` alone is ordinary prose (`Two releases: Updated Jul 21,
    2024 and Updated Aug 2, 2024 are listed in the notes.` is a control FP), so
    the discriminator is the PAIR: >=2 `Updated <Mon DD, YYYY>` AND a
    `size \u00b7 Updated` stat separator, which a prose sentence never carries.
    Measured: 1 buffer hit and it IS the leak; 0/8 control FPs; 0/707 test
    literals; 0/3,058 episodes.
    """
    t = text or ""
    if len(_UPDATED_DATE_RE.findall(t)) < 2:
        return False
    return bool(_SIZE_DOT_UPDATED_RE.search(t))



# class 63 markers (live 18.09.26) -- see _is_trending_repo_row_chrome.
_STAR_COUNTER_RE = _re.compile(r"\u2605\s*\d+(?:\.\d+)?k\s*\+\d+")
_LANG_STAT_RE = _re.compile(
    r"\b\d{1,3}\s+(?:Python|Go|TypeScript|JavaScript|Rust|C\+\+|Java|Jupyter|Shell)\b")
_REPO_SLUG_RE = _re.compile(r"\b[A-Za-z0-9][\w.-]*/\s*[A-Za-z0-9][\w.-]*")


def _is_trending_repo_row_chrome(text):
    """True when `text` is a GitHub trending row (class 63).

    Live 18.09.26: `cycle_c_github` stored

        AI agents and apps\U0001f44d \U0001f44e \u2605 66k +481 100 Python 28 infiniflow/
        ragflow RAGFlow is a leading open-source Retrieval-Augmented Generation
        (RAG) engine that fuses\u2026 \U0001f44d \U0001f44e \u2605 91k +439 100 Go 29
        langchain-ai/ langgraph Build resilient agents.

    (and an older row 9 of the same family). A trending page's row run: vote
    emojis + star counter `\u2605 <N>k +<M>` + language percentage + owner/slug.
    The star counter ALONE is ordinary prose (`We compare \u2605 66k +481 and
    \u2605 91k +439 in the table.` is a control FP), so the discriminator is the
    THREE-WAY PAIR: star counter AND an owner/slug AND a language-percentage
    stat. Measured: 2 buffer hits, BOTH are the leak family; 0/10 control FPs;
    0/717 test literals; 0/3,058 episodes.
    """
    t = text or ""
    if not _STAR_COUNTER_RE.search(t):
        return False
    if not _LANG_STAT_RE.search(t):
        return False
    return bool(_REPO_SLUG_RE.search(t))



# class 67 markers (live 18.09.26) -- see _is_journal_issue_index_chrome.
# A journal volume/issue index row: `Volume 15 (2025) WRN 15(12) - December
# 2025 : Art museums on Wikidata; ...` -- the issue tokens repeat.
_JOURNAL_ISSUE_INDEX_RE = _re.compile(
    r"[A-Za-z]{2,6}\s+\d+\(\d+\)\s*[-\u2013]\s*[A-Z][a-z]+\s+\d{4}\s*:")


def _is_journal_issue_index_chrome(text):
    """True when `text` is a journal volume/issue index run (class 67).

    Live 18.09.26: `cycle_b_papers` stored `Volume 15 (2025) WRN 15(12) -
    December 2025 : Art museums on Wikidata; comparing three comparisons of
    Grokipedia and Wikipedia WRN 15(11) - November 2025 : At least 80 million
    inconsistent facts on Wikipedia ...`. The discriminator is the ISSUE TOKEN
    shape `NAME NN(NN) - Month YYYY :` -- one issue label is an ordinary
    citation (`WRN 15(12) means the twelfth issue of the fifteenth volume`),
    the trailing colon welds it to a listing entry. Measured: 1 buffer hit and
    it IS the leak -> 0 real-prose FPs on 4 hostile controls, 0/3,058
    `longterm_episodes`, 0/686 test literals.
    """
    return bool(_JOURNAL_ISSUE_INDEX_RE.search(text or ""))


# class 68 markers (live 18.09.26) -- see _is_truncated_serp_tail.
# A SERP result title with a site suffix, an em-dash snippet and a SPACE-glued
# truncation ellipsis at the very end: `Introduction to Haystack - Haystack
# Documentation \u2014 Haystack is an open-source ... scalable \u2026`.
_TRUNCATED_SERP_TAIL_RE = _re.compile(
    r"[\w\)]\s-\s[A-Z][\w.&/]*(?:\s[A-Z][\w.&/]*)*\s\u2014[^\u2014\n]*"
    r"\s(?:\u2026|\.\.\.)\s*$")


def _is_truncated_serp_tail(text):
    """True when `text` is a site-suffixed SERP snippet cut mid-sentence (68).

    Live 18.09.26: `cycle_c_github` stored `Introduction to Haystack - Haystack
    Documentation \u2014 Haystack is an open-source AI framework ... scalable
    \u2026`. The existing `_SERP_TAIL` only fires when the ellipsis sits
    DIRECTLY after the em-dash; here a whole snippet body sits between them and
    the ellipsis is SPACE-glued (`scalable \u2026`), so the truncated body
    passed both gates. The anchor is the TAIL plus the site-suffix title shape
    (`<Title> - <Site> \u2014 <body>`): a sentence merely ending in an ellipsis
    (`The model paused\u2026`) has no site-suffix title. Measured: 1 buffer hit
    and it IS the leak -> 0 real-prose FPs on 12 hostile controls, 0/3,058
    episodes, 0/686 test literals.
    """
    return bool(_TRUNCATED_SERP_TAIL_RE.search(text or ""))


# class 69 markers (live 18.09.26) -- see _is_docs_feature_label_weld.
_DOCS_FEATURE_LABELS = (
    r"OpenAI-compatible\s+API\s+server|Anthropic\s+Messages\s+API"
    r"|multi-LoRA|reasoning\s+parsers|Streaming\s+outputs|tool\s+calling"
    r"|gRPC\s+support|TPU"
)
_DOCS_FEATURE_LABEL_WELD_RE = _re.compile(
    r"(?:" + _DOCS_FEATURE_LABELS + r")"
    r"[\s:]{1,4}"
    r"(?:" + _DOCS_FEATURE_LABELS + r")",
    _re.IGNORECASE)


def _is_docs_feature_label_weld(text):
    """True when `text` is a docs feature-list whose labels are welded (69).

    Live 18.09.26: `cycle_d_docs` stored `Tool calling and reasoning parsers
    OpenAI-compatible API server, plus Anthropic Messages API and gRPC support
    Efficient multi-LoRA support for dense and MoE layers Support for NVIDIA
    GPUs, ...` -- a feature-list with every line separator lost, so the next
    label is glued straight onto the previous one. A SINGLE label is ordinary
    prose (`Streaming outputs are produced by the model during decoding.`), so
    the discriminator is the WELD: two labels separated by whitespace/colon
    only, no punctuation and no verb between them. Measured: 5 buffer hits,
    ALL the same docs-listing family; 0/14 hostile prose controls; 0/3,058
    episodes; 0/686 test literals.
    """
    return bool(_DOCS_FEATURE_LABEL_WELD_RE.search(text or ""))


# class 70 markers (live 18.09.26) -- see _is_label_bullet_chain.
# A run of `<TitleCase Label> : <value>` bullets whose newlines were lost:
# `Datasets : ProntoQA, FOLIO ... Model : GPT-5 ... Config : max_attempts=3`.
_LABEL_BULLET_RE = _re.compile(r"[A-Z][A-Za-z]+(?: [A-Za-z]+){0,3} : ")


def _is_label_bullet_chain(text):
    """True when `text` is a run of colon-label bullets with lost newlines (70).

    Live 18.09.26: `cycle_b_papers` stored `Datasets : ProntoQA, FOLIO,
    ProofWriter, ConditionalQA, StrategyQA Model : GPT-5 (Azure deployment)
    Config : max_attempts=3 , verify_timeout=10000ms Backend Avg Accuracy
    Success Rate SMT2 86.` -- and `cycle_c_github` stored `API compatibility :
    ... Model diversity : Support for text generation, ... Sources: README.`
    One label bullet (`Metrics : precision, recall and F1 were reported.`) is
    ordinary prose, so the discriminator is REPETITION: >=2 such bullets in one
    record. Measured: 2 buffer hits, BOTH the leak family; 0/26 hostile prose
    controls; 0/3,058 episodes; 0/686 test literals.
    """
    return len(_LABEL_BULLET_RE.findall(text or "")) >= 2


# class 76 markers (live 19.09.26) -- see _is_tag_counter_run_chrome.
# A result page's tag-cloud / category counter strip whose separators were lost:
# `AI (2) jackson (2) LangGraph (2) learning (2) mcp (2) NeoCode (2)`.
_TAG_COUNTER_PAIR_RE = _re.compile(r"\b[\w.\-]{2,}\s*\(\s*[1-9]\s*\)")


def _is_tag_counter_run_chrome(text):
    """True when `text` is a run of `tag (n)` counter pairs (class 76).

    Live 19.09.26: `cycle_b_papers` stored a tag-cloud strip -- 15 `word (n)`
    pairs and nothing else -- as the answer for a BitNet query. 221 chars WITH
    digits, so the >=90 length trust AND the technical-signal gate both fired
    and no existing marker matched. Single-digit counts are the discriminator
    against real prose (a date or a score carries 4 digits, not 1).

    One or two such pairs are ordinary prose (`vLLM (2) and TensorRT-LLM (3)`),
    so the discriminator is DENSITY: >=8 single-digit pairs in one record.
    Measured: 1 buffer hit and it IS the leak; 0/6,312 buffer_junk rows;
    0/3,059 longterm_episodes; 0/764 gate-test literals; 0/7 prose controls.
    """
    t = text or ""
    if len(t) > 400:
        return False
    return len(_TAG_COUNTER_PAIR_RE.findall(t)) >= 8


# class 75 markers (live 19.09.26) -- see _is_bio_page_furniture_pair.
# A publisher's byline-card furniture welded together: `Read Full Bio <Name>
# Updated on: June 17, 2025 / 5:28 PM EDT / CBS News Add CBS News on Google`.
_BIO_CARD_DATELINE_RE = _re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\s*/\s*"
    r"\d{1,2}:\d{2}\s*(?:AM|PM)\b", _re.IGNORECASE)
_BIO_CARD_LABEL_RE = _re.compile(r"read\s+full\s+bio", _re.IGNORECASE)


def _is_bio_page_furniture_pair(text):
    """True when `text` carries a byline card's furniture PAIR (class 75).

    Live 19.09.26: `cycle_a_technews` stored

        Read Full Bio Mary Cunningham Updated on: June 17, 2025 / 5:28 PM EDT /
        CBS News Add CBS News on Google Amazon's CEO envisions an "agentic
        future" in which AI robots, or agents, replace humans working in the
        company's offices.

    A CBS-style byline card: the author bio link, the `Updated on:` stamp with a
    full date-TIME dateline, the publisher label and an add-on-Google link --
    all welded to the article's lede. 226 chars with digits, so the >=90 length
    trust and the technical-signal gate fired.

    Neither half is a marker on its own: `Read Full Bio` alone flagged 2 hostile
    controls and a bare dateline flagged 3. The discriminator is the PAIR of the
    page's OWN furniture (bio label + date-time dateline), which no prose
    carries. Measured: 1 buffer hit and it IS the leak; 0/11 hostile prose
    controls; 0/6,265 buffer_junk rows; 0/3,059 longterm_episodes; 0/1,175
    gate-test literals.
    """
    t = text or ""
    return bool(_BIO_CARD_LABEL_RE.search(t) and _BIO_CARD_DATELINE_RE.search(t))


# class 74 markers (live 19.09.26) -- see _is_decorative_alt_text_chrome.
# A landing page's logo alt-text welded to the next decoration's alt-text:
# `GitHub Logo <sparkles> Decorative dot pattern background` -- markup
# furniture, never an insight. The emoji is an optional separator (0-3 chars).
_DECORATIVE_ALT_TEXT_RE = _re.compile(
    r"github\s+logo\s*\S{0,3}\s*decorative\s+\w+\s+pattern\s+background",
    _re.IGNORECASE)


def _is_decorative_alt_text_chrome(text):
    """True when `text` is a page's welded decorative alt-text run (class 74).

    Live 19.09.26: `cycle_c_github` stored

        Agent Launch Week #2 Explore our product launch updates GitHub Logo
        \u2728 Decorative dot pattern background The end-to-end AI Agent
        Engineering Platform Build enterprise multi-agent systems -- development
        , observability , and deployment in one platform.

    A hero section whose image alt-texts were concatenated: the site logo's alt
    (`GitHub Logo`) is welded to the decorative background's alt (`Decorative
    dot pattern background`), with the page's own sparkles emoji between them.
    249 chars with digits, so the >=90 length trust and the technical-signal
    gate fired.

    The discriminator is the WELD: no verb, no punctuation between the two alt
    strings. Real prose that mentions both always separates them with a verb or
    a comma (`GitHub Logo and a decorative dot pattern background are both alt
    attributes in the hero markup.`). Measured: 1 buffer hit and it IS the leak;
    0/18 hostile prose controls; 0/3,059 longterm_episodes; 0/1,175 test
    literals; 0/6265 buffer_junk rows.
    """
    return bool(_DECORATIVE_ALT_TEXT_RE.search(text or ""))


# class 73 markers (live 19.09.26) -- see _is_table_header_value_run.
# A benchmark TABLE's column-label chain with its first value welded on:
# `Model Dataset Resolution Acc@1 ckpt MedViT_small ImageNet-1K 224 83.`
# A menu is a LABEL CHAIN; a sentence has grammar. No verb + almost no
# lowercase words = the page's table header row, not an insight.
_TABLE_COL_LABELS = (
    "Model", "Models", "Dataset", "Datasets", "Resolution", "Acc@1", "Acc@5", "Acc",
    "Accuracy", "ckpt", "F1", "Top-1", "Top-5", "mAP", "Params", "FLOPs", "Latency",
    "Throughput", "Precision", "Recall", "Tokens", "Steps", "Epochs", "Backend",
    "Avg", "Success Rate", "BLEU", "ROUGE", "Perplexity", "Speedup", "Runtime",
)
_TABLE_VERB_RE = _re.compile(
    r"\b(?:is|are|was|were|has|have|had|shows?|reached|measured|achieved|improves?|"
    r"gives?|uses?|makes?|allows?|enables?|trains?|runs?|keeps|compares?|lists?|"
    r"contains?|reports?|supports?|works?|means?|indicates?|found|became|remained|"
    r"needs?|does|do|did)\b", _re.IGNORECASE)
_TABLE_WORD_RE = _re.compile(r"[A-Za-z][A-Za-z'./@+-]*")


def _is_table_header_value_run(text):
    """True when `text` is a benchmark table's header row (class 73).

    Live 19.09.26: `cycle_f_multi_domain` stored

        Model Dataset Resolution Acc@1 ckpt MedViT_small ImageNet-1K 224 83.

    A paper's benchmark table header with the first result cell welded on. Only
    68 chars, so the >=90 length trust never applied (class-33 precedent) and
    no existing marker matched; `_is_metric_row_fragment` (class 43) needs a
    parenthesised ratio of counts, which this row has not.

    The discriminator is the class-43 rule generalised: >=3 metric column
    labels AND no finite verb AND almost no lowercase words (<=0.25). Real
    prose that names the same columns -- `Top-1 accuracy and F1 score were
    reported for each model, dataset and resolution setting.` -- always has a
    verb. Measured: 1 buffer hit and it IS the leak; 0/15 hostile prose
    controls; 0/3,059 longterm_episodes; 0/1,175 gate-test literals.
    """
    t = text or ""
    labels = sum(1 for c in _TABLE_COL_LABELS
                 if _re.search(r"(?<![A-Za-z0-9])" + _re.escape(c) + r"(?![A-Za-z0-9])", t))
    if labels < 3:
        return False
    if _TABLE_VERB_RE.search(t):
        return False
    words = _TABLE_WORD_RE.findall(t)
    if not words:
        return False
    return (sum(1 for w in words if w.islower()) / len(words)) <= 0.25


# class 72 markers (live 19.09.26) -- see _is_repo_stat_footer_run.
# A repo page's stat FOOTER welded onto the end of its description:
# `<N> stars <M> forks <Lang> <Licence>.` -- chrome, not an insight.
_REPO_STAT_FOOTER_RE = _re.compile(
    r"\b\d[\d,]*\s+stars?\s+\d[\d,]*\s+forks?\b\s+"
    r"(?:Python|Go|TypeScript|JavaScript|Rust|C\+\+|Java|Jupyter(?:\s+Notebook)?|Shell|C)\s+"
    r"(?:Apache|MIT|GPL|BSD|MPL|LGPL)[\w.\-]*\s*\.\s*$")
_EXAMPLE_CUE_RE = _re.compile(
    r"(?:e\.g\.|for example|such as|\blike\b|example:)\s*(?:[A-Za-z<>/|,.\-]+\s+){0,4}$",
    _re.IGNORECASE)


def _is_repo_stat_footer_run(text):
    """True when `text` ends in a repo page's stat footer (class 72).

    Live 19.09.26: `cycle_f_multi_domain` stored

        NeMo: a PyTorch framework for physics ML, from install to first
        surrogate Open-source deep-learning framework for building, training,
        and fine-tuning deep learning models using state-of-the-art Physics-ML
        methods 3,262 stars 784 forks Python Apache-2.

    251 chars with digits, so the >=90 length trust and the technical-signal
    gate both fired. The `stars`/`forks` counters alone are ordinary prose
    (`The repository now has 3,262 stars and 784 forks, making it popular.`),
    so the discriminator is the WELDED FOOTER: counter pair + language +
    licence, ending the record. Real prose that only QUOTES such a footer
    (e.g. `..., e.g. repo 12 stars 34 forks Python MIT.`) is exempted by the
    small example-cue lookbehind. Measured: 1 buffer hit and it IS the leak;
    0/23 hostile prose controls; 0/3,059 longterm_episodes; 0/1,159 test
    literals.
    """
    t = text or ""
    m = _REPO_STAT_FOOTER_RE.search(t)
    if not m:
        return False
    return not _EXAMPLE_CUE_RE.search(t[:m.start()])


# class 71 markers (live 18.09.26) -- see _is_repeat_badge_glyph_run.
# A changelog-style list where the page's own "new" badge glyph (U+1F195)
# annotates >= 2 entries in one record.
_REPEAT_BADGE_GLYPH_RE = _re.compile(r"\U0001f195")


def _is_repeat_badge_glyph_run(text):
    """True when `text` is a badge-annotated listing run (class 71).

    Live 18.09.26: `cycle_g_security` stored `ARTKIT, Meta LlamaFirewall/Llama
    Guard 4 \U0001f195 New Case Studies EchoLeak (CVE-2025-32711), DeepSeek R1
    vulnerabilities, first malicious MCP server \U0001f195 AI Regulations EU AI
    Act 2026 milestones, NIST AI RMF, ISO/IEC 42001 \U0001f504 Updated LLM Ec`
    -- a link/entry listing whose newlines were lost, with the page's own
    "new" badge welded onto entries. The badge glyph ALONE is not the marker
    (one \U0001f195 in a sentence is ordinary prose); the discriminator is
    REPETITION of the page's own badge in one record. Measured: 1 buffer hit
    and it IS the leak -> 0/3,058 `longterm_episodes`, 0/704 test literals,
    0 FPs across 12 hostile prose controls.
    """
    return len(_REPEAT_BADGE_GLYPH_RE.findall(text or "")) >= 2



# class 77/78/79/80 markers (live 19.09.26) -- see the helpers below.
# A security-advisory LISTING row: vendor/product run glued to a `-- <Mon DD, YYYY>`
# dateline and a bare CVE id, or a severity badge welded to the end of the text.
#   "Cisco Ios Xe Rockwellautomation Allen Bradley Stratix 5200 Firmware + 5 --
#    Oct 16, 2023 CVE-2025-20337 CRITICAL 10."
# 115 chars WITH digits -> the `>=90` length trust AND the technical-signal gate
# both fired. `CVE-<id>` alone is ordinary security prose; the discriminator is
# the advisory furniture (dateline->CVE weld, or a trailing `<SEVERITY> <score>.`).
_ADVISORY_ROW_RE = _re.compile(
    r"(?:\s--\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+CVE-\d{4}-\d{4,}\b"
    r"|CVE-\d{4}-\d{4,}\s+(?:CRITICAL|HIGH|MEDIUM|LOW)\s+\d{1,2}(?:\.\d)?\.?\s*$)",
    _re.IGNORECASE)

# A site-branded HEADLINE STUB stored as the answer: a short multi-TitleCase run,
# a colon, then `<year> Comparison of ...` and nothing else -- the SERP card's
# title line, never a sentence.
#   "Tech Frontline Low-Code AI Workflow Automation: 2026 Comparison of Zapier,
#    Make, and Tray."
# A bare `20xx Comparison of` is ordinary prose (3 control FPs); the brand run
# BEFORE the colon is the discriminator (0 FPs at 2-4 TitleCase tokens).
_SITE_HEADLINE_STUB_RE = _re.compile(
    r"^\s*(?:[A-Z][\w&.\-]*\s+){2,4}[^:\r\n]{0,50}:\s*20\d\d\s+Comparison of\b",
    _re.MULTILINE)

# An incident/vendor FACT BOX: the page's own label pair `Key Points` ...
# `Affected objects:` welded in one run.
#   "Key Points Event time: 2026-05-10, James Shore published an analysis article
#    -Affected objects: All developers and technical teams who use AI coding agents"
# 191 chars with digits -> both gates fired. `Affected objects` alone is ordinary
# prose (the vendor's own label is the anchor); the WELDED pair is the marker.
_FACT_BOX_LABEL_CHAIN_RE = _re.compile(
    r"\bKey Points\b[\s\S]{0,200}\bAffected objects\s*:",
    _re.IGNORECASE)


def _is_advisory_row(text):
    """True for a security-advisory LISTING row (class 77, live 19.09.26).

    A vendor/product run welded to an advisory dateline + CVE id, or a CVE id
    with a trailing severity badge and score. Measured: 1 buffer hit and it IS
    the leak -> 0 real-prose FPs on 9 hostile security-prose controls, 0 of
    1,408 asserted gate-test literals, 0/3,059 `longterm_episodes`.
    """
    return bool(_ADVISORY_ROW_RE.search(text or ""))


def _is_site_headline_stub(text):
    """True for a site-branded headline stub (class 78, live 19.09.26).

    A brand run, a colon, then `<year> Comparison of ...` and nothing further.
    Measured: 1 buffer hit (the leak) -> 0 FPs on 6 prose controls, 0 test
    literals, 0/3,059 episodes.
    """
    return bool(_SITE_HEADLINE_STUB_RE.search(text or ""))


def _is_fact_box_label_chain(text):
    """True for an incident/vendor FACT BOX label chain (class 79, live 19.09.26).

    `Key Points` welded within 200 chars of the vendor's own `Affected objects:`
    label. Measured: 1 buffer hit (the leak) -> 0 FPs on 6 prose controls, 0
    test literals, 0/3,059 episodes.
    """
    return bool(_FACT_BOX_LABEL_CHAIN_RE.search(text or ""))


# class 80 marker: the agent's OWN deliverable plan WITHOUT the dangling list
# marker that class 66 required. Live 19.09.26:
#   "Energy efficiency: AI performance optimization: Python script for RAM/Disk/
#    Cron monitoring + optimization suggestions + skill + cron job every 12h."
# Same own-artifact family as class 66 (the German form is `KI-Performance-
# Optimierung: ...`), but it ends in prose instead of a dangling `2.`, so
# `_PROMPT_PLAN_ECHO_RE` never fired. The discriminator is the own-artifact
# title AND a 3-way `+`-joined deliverable run (bare `RAM/Disk/Cron` alone hits
# 5 episodes; bare `skill + cron` hits 3 episodes + 1 control FP).
_OWN_PLAN_PLUS_RUN_RE = _re.compile(
    r"^\s*(?:Energy efficiency|KI-Performance-Optimierung|AI performance optimization"
    r"|Performance optimization|Efficiency)[^:\r\n]{0,40}:"
    r"[^\r\n]{0,200}\+[^\r\n]{0,120}\+[^\r\n]{0,120}\+",
    _re.IGNORECASE | _re.MULTILINE)


def _is_own_plan_plus_run(text):
    """True for the agent's own deliverable plan stored as knowledge (class 80).

    Measured: 1 buffer hit (the leak) -> 0 FPs on 6 prose controls, 0 test
    literals; the single `longterm_episodes` hit is the SAME own-artifact string
    in German, i.e. the same leak, not world knowledge.
    """
    return bool(_OWN_PLAN_PLUS_RUN_RE.search(text or ""))


def _is_nav_chrome(text):
    """True when text is page chrome (entities, marketing, UI, template leaks)."""
    if _ENTITY.search(text):
        return True
    # a SERP run welded to a docs site's CTA (class 53, 18.09.26)
    if _is_docs_cta_serp_run(text):
        return True
    # a press-roundup listing run (class 55, 18.09.26)
    if _is_news_aggregator_listing_run(text):
        return True
    # a syndicated dev.to card tail (class 56, 18.09.26)
    if _is_devto_card_tail(text):
        return True
    # an agency services menu strip (class 57, 18.09.26)
    if _is_services_menu_chain(text):
        return True
    # a blog archive pagination widget + newsletter promo (class 58, 18.09.26)
    if _is_pagination_newsletter_widget(text):
        return True
    # a code-block FULLSCREEN toggle widget pair (class 59, 18.09.26)
    if _is_fullscreen_toggle_chrome(text):
        return True
    # a post headline welded to its hashtag run (class 60, 18.09.26)
    if _is_hashtag_run_after_headline(text):
        return True
    # a dated card headline + tag strip (class 61, 18.09.26)
    if _is_dated_tag_strip_chrome(text):
        return True
    # a model-hub listing row run (class 62, 18.09.26)
    if _is_model_listing_run_chrome(text):
        return True
    # a GitHub trending row (class 63, 18.09.26)
    if _is_trending_repo_row_chrome(text):
        return True
    # a journal volume/issue index run (class 67, 18.09.26)
    if _is_journal_issue_index_chrome(text):
        return True
    # a truncated site-suffixed SERP snippet (class 68, 18.09.26)
    if _is_truncated_serp_tail(text):
        return True
    # a docs feature-list with welded labels (class 69, 18.09.26)
    if _is_docs_feature_label_weld(text):
        return True
    # a colon-label bullet chain with lost newlines (class 70, 18.09.26)
    if _is_label_bullet_chain(text):
        return True
    # a repeated page badge glyph on list entries (class 71, 18.09.26)
    if _is_repeat_badge_glyph_run(text):
        return True
    # a repo page's stat footer welded onto its description (class 72, 19.09.26)
    if _is_repo_stat_footer_run(text):
        return True
    # a repo page's stat footer welded onto its description (class 72, 19.09.26)
    if _is_repo_stat_footer_run(text):
        return True
    # a benchmark table's header row (class 73, 19.09.26)
    if _is_table_header_value_run(text):
        return True
    # a page's welded decorative alt-text run (class 74, 19.09.26)
    if _is_decorative_alt_text_chrome(text):
        return True
    # a page's welded decorative alt-text run (class 75, 19.09.26)
    if _is_bio_page_furniture_pair(text):
        return True
    # a result page's tag-counter run (class 76, 19.09.26)
    if _is_tag_counter_run_chrome(text):
        return True
    low = text.lower()
    if any(c in low for c in _NAV_CHROME):
        return True
    # a deep-read prompt echoed back as a bullet chain (17.09.26)
    if _is_prompt_echo_bullet_chain(text):
        return True
    if _is_de_portal_fact_box_chrome(text):
        return True
    if _is_prompt_echo_fragment(text):
        return True
    if _is_generated_plan_echo_fragment(text):
        return True
    if _is_generated_plan_echo_fragment(text):
        return True
    # a security-advisory listing row / headline stub / fact box / own plan
    # (classes 77-80, 19.09.26)
    if _is_advisory_row(text):
        return True
    if _is_site_headline_stub(text):
        return True
    if _is_fact_box_label_chain(text):
        return True
    if _is_own_plan_plus_run(text):
        return True
    if _is_sidebar_listing_chrome(text):
        return True
    # the page's own META blurb (same rule as internet_learner._is_page_meta_blurb)
    if _is_page_meta_blurb(text):
        return True
    # a GitHub repo-listing row (same rule as internet_learner._is_gh_listing_row)
    if _is_gh_listing_row(text):
        return True
    if _is_byline_counter_chrome(text):
        return True
    # a news-card stub / relative-time nav chain (class 33/34, 17.09.26)
    if _is_news_card_stub(text):
        return True
    if _is_relative_time_nav_chain(text):
        return True
    # a repeated aggregator feed listing (class 37, 17.09.26)
    if _is_hn_feed_listing_chrome(text):
        return True
    # a single aggregator item row with its feed tail (class 49, 18.09.26)
    if _is_hn_item_chrome(text):
        return True
    # a run of a document-hosting page's nav widgets (class 50, 18.09.26)
    if _is_nav_widget_run_chrome(text):
        return True
    # a broadcast-news byline + weekday dateline + Share header (class 51, 18.09.26)
    if _is_news_byline_share_header(text):
        return True
    # a landing-page hero CTA chain (class 38, 17.09.26)
    if _is_marketing_hero_cta_chrome(text):
        return True
    # a platform selector glued to a subreddit feed row (class 39, 17.09.26)
    if _is_platform_selector_listing_chrome(text):
        return True
    # an "Operator Spotlight" widget row stored twice (class 45, 17.09.26)
    if _is_operator_spotlight_chain(text):
        return True
    # a paper-title + slash-date + project-title header chain (class 46, 17.09.26)
    if _is_preprint_header_chain(text):
        return True
    # a personal-blog header nav run (class 47, 17.09.26)
    if _is_personal_blog_nav_chain(text):
        return True
    # a competitor pricing hero (class 48, 17.09.26)
    if _is_pricing_hero_chrome(text):
        return True
    # an article-header byline + `Published <dd Mon yy>` (class 40, 17.09.26)
    if _is_byline_published_article_header(text):
        return True
    # a date-stamped headline listing (class 35, 17.09.26)
    if _is_date_heading_listing(text):
        return True
    # a repo-page tab bar + language/size stat bar (class 36, 17.09.26)
    if _is_repo_tab_statbar_chrome(text):
        return True
    # the LLM's verdict ABOUT the page returned as an insight (class 44, 17.09.26)
    if _is_source_verdict_chrome(text):
        return True
    # a counter truncated at its own digits ("K followers ...") = mid-widget
    if _DETACHED_COUNT_RE.match(text):
        return True
    # a sports-fixture list from a results page (same narrow rule as
    # internet_learner._is_fixture_list)
    if _FIXTURE_LIST_RE.search(text):
        return True
    # an arXiv abstract-page label chain (same rule as
    # internet_learner._is_arxiv_abstract_chrome)
    if _is_arxiv_abstract_chrome(text):
        return True
    # a Chinese Q&A/answer-portal label chain (same rule as
    # internet_learner._is_qa_portal_chrome)
    if _is_qa_portal_chrome(text):
        return True
    # a German pricing/checkout label chain (same rule as
    # internet_learner._is_de_pricing_chrome)
    if _is_de_pricing_chrome(text):
        return True
    # an ad-blocker-off / subscribe notice (same rule as
    # internet_learner._is_adwall_notice)
    if _is_adwall_notice(text):
        return True
    # a legal-imprint / contact block (same rule as is_contact_block)
    if is_contact_block(text):
        return True
    # a LEADING MediaWiki section-edit control (same narrow rule as
    # internet_learner._strip_wiki_section_prefix)
    if _WIKI_EDIT_WORD_RE.match(text.strip()):
        return True
    # diagram DSL source, not prose (same rule as
    # internet_learner._is_diagram_markup)
    # a package-index / file-listing label chain (same rule as
    # internet_learner._is_package_index_chrome)
    # a course/certification landing-page CTA (same rule as
    # internet_learner._is_course_cta_chrome)
    if _is_course_cta_chrome(text):
        return True
    # the extractor's own plan echoed back (same rule as
    # internet_learner._is_plan_scaffold_echo)
    if _is_plan_scaffold_echo(text):
        return True
    # a GitHub issue page, not an insight (same rule as
    # internet_learner._is_github_issue_chrome)
    if _is_github_issue_chrome(text):
        return True
    # a blog archive listing, not an article (same rule as
    # internet_learner._is_archive_listing)
    if _is_archive_listing(text):
        return True
    # a company/Wikipedia infobox financial label chain (same rule as
    # internet_learner._is_junk)
    if is_financial_infobox(text):
        return True
    # a service-status / maintenance banner (same predicate as
    # internet_learner._is_maintenance_banner)
    if _is_maintenance_banner(text):
        return True
    # a benchmark/metric TABLE row: column labels + counts, no
    # sentence (class 43, 17.09.26 -- same rule as internet_learner)
    if _is_metric_row_fragment(text):
        return True
    # a rendered release-note / changelog bullet chain
    if _is_changelog_chain(text):
        return True
    if _is_package_index_chrome(text):
        return True
    if _is_diagram_markup(text):
        return True
    # a news-ticker loop (same rule as internet_learner._is_ticker_loop): the
    # writer gate must refuse it too, or any other writer path lands it in the
    # buffer. Kept here as a mirror because buffer_store must not import the
    # learner (circular).
    if _TIME_CODE_RE.search(text):
        words = text.split()
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                ph = " ".join(words[i:j])
                if len(ph) >= 15 and text.count(ph) >= 2:
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
    if is_prompt_echo(s):
        return True
    if is_ordinal_stub(s):
        return True
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
