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


def _is_arxiv_abstract_chrome(text):
    """True when `text` is an arXiv-style abstract page's label chain."""
    low = (text or "").lower()
    if not low:
        return False
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


def _is_nav_chrome(text):
    """True when text is page chrome (entities, marketing, UI, template leaks)."""
    if _ENTITY.search(text):
        return True
    low = text.lower()
    if any(c in low for c in _NAV_CHROME):
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
    # a blog archive listing, not an article (same rule as
    # internet_learner._is_archive_listing)
    if _is_archive_listing(text):
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
