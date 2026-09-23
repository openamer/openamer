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
    # a vLLM server LOG LINE (class 155, 23.09.26). Substring form --
    # buffer_store._JUNK_MARKERS has no regex. Kept in sync with
    # internet_learner._JUNK_RE. Measured: hits only the leaking row.
    "apiserver pid=",
    "[scheduler.",
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
    # a landing-page marketing-slogan clause at the tail of a 50+/15+ promo
    # claim (class 139, 22.09.26 -- stored 15.09 and again 22.09)
    "no mental load",

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
    # A GitHub releases-page ROW: "Released <name> (GitHub Releases) *
    # <relative time>" -- page meta welded to the release title, then a
    # hashtag tail. Live 21.09.26: the knowledge-to-action competitor cycle
    # analysed
    #   "Released Stride (GitHub Releases) * 1 day, 18 hours ago How to get
    #    sound effects for your game #gamedev #sounddesign #elevenlabs #ad"
    # The relative-time digits fed the technical-signal gate and the length
    # cleared the >=25 floor, so BOTH gates passed it and it trained.
    # Keyed on the pair (a release label followed by the literal site label
    # "(GitHub Releases)"), never on the bare words: prose that merely DISCUSSES
    # releases ("GitHub Releases are built automatically from tags ...") is
    # untouched -- measured as a counter-case.
    # A slide-deck NAVIGATION trio welded to a widget date: "Show original
    # Previous slide Next slide <relative date>". Live 21.09.26: the same kta
    # cycle analysed
    #   "ES Show original Previous slide Next slide 1 year ago in Stocks, AI
    #    Modeling, Business, AI GOOGL Alphabet Shares ..."
    # A search widget / slideshow strip, zero prose. Keyed on the ADJACENCY of
    # the controls, never on a single control: ordinary prose that merely says
    # "the previous slide showed the latency curve" carries the words but never
    # the welded trio -- measured as a counter-case. Measured: 1 buffer hit and
    # that hit IS the leaking row -> 0 prose FPs over 3,059 longterm_episodes +
    # 7,442 buffer_junk rows + 4 hand-written counter-cases.
    "show original previous slide",
    "previous slide next slide",
    "add free huggingface demo",
    # Doc-site product nav welded to a vendor SDK label (live 22.09.26:
    # cycle_d_docs stored "API, Infinite Possibilities Reference Qualcomm
    # Cloud AI home Qualcomm Cloud AI SDK download Qualcomm Cloud AI API
    # reference User Guide OCP Microscaling Formats (MX) Specification
    # efficient-transformers Welcome to Efficient-Transformers
    # Documentation!" -- 250 chars of pure sidebar/product nav, zero prose.
    # Same markers as internet_learner._JUNK_RE; keep both files in sync.
    # Measured over the live 245-row buffer: 1 hit each and that hit IS the
    # leaking row -> 0 real-prose FPs. The bare forms "api reference" and
    # "infinite possibilities" were MEASURED-AND-REJECTED (1 hostile control
    # each), so both markers are two-token WELDS. "sdk download" was likewise
    # rejected (hostile control: "Qualcomm Cloud AI SDK download is documented
    # on the vendor portal ...").
    "cloud ai api reference",
    "infinite possibilities reference",
    "efficient-transformers welcome to efficient-transformers",
)

# A GitHub releases-page ROW shape: a release LABEL followed by the literal
# site label, then a relative-time stamp -- e.g. "Released Stride (GitHub
# Releases) • 1 day, 18 hours ago How to get sound effects ..." (live
# 21.09.26, knowledge-to-action competitor cycle). The relative-time digits
# satisfied the technical-signal gate. DELIBERATELY a welded regex pair, not
# a bare "(github releases)" substring: the bare form was measured and
# REJECTED because it also flags genuine prose that mentions the feature
# ("The pipeline pushes (GitHub Releases) metadata into our registry so
# downstream consumers can pin versions."). Requiring the release label
# BEFORE it and a relative stamp AFTER it keeps that sentence learnable.
# Measured: 1 buffer hit and that hit IS the leaking row -> 0 prose FPs.
_GH_RELEASES_ROW_RES = (
    _re.compile(r"\(github releases\)", _re.IGNORECASE),
    _re.compile(r"\b\d+\s+day[s]?,\s*\d+\s+hour[s]?\s+ago\b",
                _re.IGNORECASE),
)
# BOTH parts must be present. A bare "(GitHub Releases)" alone was measured
# and REJECTED: genuine prose mentions the feature ("The release pipeline
# pushes (GitHub Releases) metadata into our registry ..."). The releases-
# page ROW always welds the label to a relative-time stamp, and real prose
# never carries both.
_GH_RELEASES_ROW_MIN_MARKERS = 2


def _is_gh_releases_row(text):
    """True when `text` is a GitHub releases-page listing row."""
    t = text or ""
    return (sum(1 for r in _GH_RELEASES_ROW_RES if r.search(t))
            >= _GH_RELEASES_ROW_MIN_MARKERS)


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
# class 137 (22.09.26) widened this from FULL month names to the
# abbreviated form too: the live leak `Sep 24, 2025 ... Sep 18, 2025 ...`
# was invisible to class 35, which then read 0 hits on it. Measured: the
# widened form fires on that row and stays 0/3,059 longterm_episodes and
# 0/12 hostile prose counter-cases. Single call site, 2 dates minimum.
_FULL_DATE_RE = _re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|"
    r"Nov|Dec)\.?\s+\d{1,2},\s+\d{4}\b")
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


def _is_hn_show_run_chrome(text):
    """True for an HN item row whose headline carries a `Show HN:` tag (105)."""
    return bool(_HN_SHOW_RUN_RE.search(text or ""))




# a HN item row: feed unit + points + the site's own `Show HN:` tag
# (class 105, 19.09.26).
_HN_SHOW_RUN_RE = _re.compile(
    r"\b\w+\s+\d{1,2}\s+(?:minutes?|hours?|days?)\s+ago\s*\|\s*"
    r"\d{1,5}\s*comments?\b\s+\d{1,4}\s+\bShow\s+HN\s*:", _re.IGNORECASE)


def _is_blog_nav_feature_run_chrome(text):
    """True for a personal/blog nav-label chain carrying the `Featured #` marker.

    Live 19.09.26 (class 106): `cycle_f_multi_domain` stored

        Software People Events Resources Cheatsheets Videos Blog About About
        Posit Our AI Work Our Python Work Our R Work Community Support Blog
        Featured # Sep 9, 2026 Positron September Release Highlights Highlights
        from the 2026.

    A whole-site nav bar (>=8 consecutive label tokens, welded) run straight
    into the page's own markdown heading marker `Featured #`. 223 chars WITH
    digits, so the >=90 length trust and the technical-signal gate both fired;
    `_is_nav_list` wants >=6 TitleCase tokens with no comma and this run has
    ordinary TitleCase labels welded to lowercase prose.

    The discriminator is the CONJUNCTION: >=8 nav-vocabulary label tokens AND
    the page's own `Featured #` heading marker. The nav count alone measured
    clean on the buffer but is one threshold away from ordinary prose that
    LISTS those sections; the `Featured #` weld is what no human sentence has.
    Measured: 1 buffer hit and it IS the leak -> 0 FPs on 10 hostile controls
    that list nav vocabulary freely, 0 of 3,059 `longterm_episodes`, 0 gate-test
    literals. (The duplicate-TitleCase-word form was REJECTED: 4 real
    `longterm_episodes` hits.)
    """
    return bool(_BLOG_NAV_FEATURE_RE.search(text or ""))




# a site nav-label run welded to the page's own `Featured #` heading marker
# (class 106, 19.09.26).
_BLOG_NAV_FEATURE_RE = _re.compile(
    r"(?:(?:Software|People|Events|Resources|Cheatsheets|Videos|Blog|About|"
    r"Community|Support|Docs|Pricing|Careers|Contact|Login|Home)\b[\s,]*){8,}"
    r"[\s\S]{0,160}?\bFeatured\s+#", _re.IGNORECASE)

# class 107 markers (live 20.09.26) -- see _is_de_double_optin_newsletter_chrome.
_DE_DOUBLE_OPTIN_MARKERS = (
    "fast geschafft",
    "urlaubstr",
    "bestätigen sie ihre anmeldung",
    "klick auf den link in der",
    "soeben geschickt haben",
)
_DE_DOUBLE_OPTIN_MIN_MARKERS = 2


def _is_de_double_optin_newsletter_chrome(text):
    """True when `text` is a German newsletter double-opt-in confirmation page.

    Live 20.09.26 (class 107): `cycle_e_competitors` stored

        Fast geschafft - mehr als 3000 Urlaubsträume warten auf Sie Bitte
        bestätigen Sie Ihre Anmeldung durch einen Klick auf den Link in der
        E-Mail, die wir Ihnen soeben geschickt haben.

    A whole-page consent chain: promo hook plus signup confirmation. 160 chars,
    so the >=90 length trust fired; the digits in `3000` fed the
    technical-signal gate. Structural, not topical: TWO independent markers, so
    German prose that merely mentions a confirmation still passes. Measured: 1
    buffer hit and it IS the leak -> 0 FPs on real-prose controls (`Fast
    geschafft: der Benchmark lief in 42 Sekunden durch`, `Bitte bestätigen Sie
    Ihre Anmeldung, sobald Sie das Formular ... ausgefüllt haben`), 0 of 3,059
    `longterm_episodes`, 0 gate-test literals.
    """
    low = (text or "").lower()
    if not low:
        return False
    return sum(1 for m in _DE_DOUBLE_OPTIN_MARKERS if m in low) >= _DE_DOUBLE_OPTIN_MIN_MARKERS


# class 108 markers (live 20.09.26) -- see _is_jobboard_ad_run_chrome.
_JOBBOARD_SLOGAN = "without the hassle"
_JOBBOARD_BRAND = "haystack"
_JOBBOARD_MIN_BRAND = 2


# class 113/114 markers (live 20.09.26) -- see _is_dated_listing_run and
# _is_readtime_card_widget.
_MONTH_NAME = (r"(?:Jan|Feb|M(?:ar|\u00e4r|rz)|Apr|May|Jun|Jul|Aug|Sep|Sept|"
               r"Oct|Okt|Nov|Dec|Dez)")
# an aggregator row's own date: "12th September 2026" / "12. September 2026"
_LISTING_DATE = (r"\d{1,2}\.?(?:st|nd|rd|th)?\s+" + _MONTH_NAME + r"[a-z]*\.?\s+\d{4}")
# the row's OWN dash separator, not a hyphen inside a word
_ROW_DASH = r"\s[-\u2013\u2014]\s"
_DATED_LISTING_RE = _re.compile(
    _ROW_DASH + r"\b" + _LISTING_DATE + r"\b.{0,140}?" + _ROW_DASH
    + r"\b" + _LISTING_DATE + r"\b", _re.I | _re.S)
_READTIME_CARD_RE = _re.compile(
    r"\b" + _MONTH_NAME + r"\b\s*\d{1,2},\s*\d{4}.{0,60}?"
    r"\b\d+\s+min\s+min\s+read\b", _re.I | _re.S)


def _is_dated_listing_run(text):
    """True when `text` is an aggregator LISTING run of dated headlines (class 113).

    Live 20.09.26: `cycle_e_competitors` (and an earlier `cycle_a_technews`)
    stored the same blog index feed:

        ChatGPT Work - 12th September 2026 OpenAI agents attacked RubyGems
        back in May - 12th September 2026 Some thoughts on the Navier-Stokes
        Millennium Prize Problem - 8th September 2026 This is a link post by
        Simon Willison, posted on 27th February 2026 .

    Several unrelated headlines welded together by their own `- <date>` tails:
    a blog INDEX page, not an article. 251 chars carrying digits, so both the
    >=90 length trust and the technical-signal gate fired, and no existing
    detector matched.

    The discriminator had to be TIGHTENED during measurement: a first form
    requiring only two date stamps within 120 chars measured 1
    `longterm_episodes` hit -- a Markdown metrics TABLE (`| Erstellt | 16.
    August 2026 | ... | Letzter Push | 28. August 2026 |`), which is real
    knowledge and must stay learnable. Requiring the row DASH (` - `) to weld
    each date to a headline removes it: prose that merely mentions two dates
    (`released on 12 September 2026 and benchmarked on 8 September 2026`) has
    no such dash in BOTH slots. Measured: 2 buffer hits and BOTH are the leak
    -> 0 FPs on 10 prose controls, 0 of 3,059 `longterm_episodes`, 0 gate-test
    literals.
    """
    return bool(_DATED_LISTING_RE.search(text or ""))


def _is_readtime_card_widget(text):
    """True when `text` is a review card's date + glued read-time badge (class 114).

    Live 20.09.26: `cycle_f_multi_domain` stored

        Claw Mar 23, 2026 Comparison 15 min min read OpenClaw vs Other AI
        Agent Frameworks - Comprehensive Comparison 2026 In-depth comparison
        of OpenClaw with LangChain, AutoGPT, CrewAI, and other popular AI
        agent frameworks.

    A CMS review card: date, category, and a read-time badge. The badge is the
    discriminator -- the renderer emits the doubled unit `min min read`, which
    ordinary prose never does (`a 15 min read`, `the 15-minute read` stay
    learnable). Requiring the date + badge TOGETHER keeps a bare badge and a
    bare date out of scope. Measured: 1 buffer hit and it IS the leak -> 0 FPs
    on 10 prose controls (including two that mention `min read`), 0 of 3,059
    `longterm_episodes`, 0 gate-test literals.
    """
    return bool(_READTIME_CARD_RE.search(text or ""))


# class 118 marker (live 20.09.26) -- see _is_infobox_factrow_tail.
# MediaWiki relative-age template followed by the infobox's license field. The
# template renders as a date, a `;`, the relative age and the ISO date in
# parentheses; the extractor then welded the NEXT infobox field onto it.
_RELAGO_TEMPLATE = r"\b\d+\s+years?\s+ago\s*\([\s\S]{0,40}?\)"
_INFOBOX_LICENSE_LABEL = r"\bContent license\b"
_INFOBOX_FACTROW_TAIL_RE = _re.compile(
    _RELAGO_TEMPLATE + r"[\s\S]{0,60}?" + _INFOBOX_LICENSE_LABEL, _re.I)


def _is_infobox_factrow_tail(text):
    """True when `text` is a wiki infobox fact-row tail (class 118).

    Live 20.09.26: `cycle_h_efficiency` stored

        September 2026) Launched 15 January 2001 ; 25 years ago ( 2001-01-15 )
        Content license Creative Commons Attribution/ Share-Alike 4.

    Two infobox fields ("Launched", "Content license") with the rendered
    relative-age template between them -- a page's field table, not an article.
    The text OPENS mid-parenthesis, so the extractor cut a field row out of the
    box. 131 chars carrying digits, so the >=90 length trust and the
    technical-signal gate both fired, and no existing detector matched
    (`which_rule_matches.py` -> INDIVIDUAL RULES MATCHED: none).

    The discriminator is the JUXTAPOSITION, not either half. The relative-age
    template alone (5 candidate forms measured) hits 13 of 12-25 hand-written
    hostile prose controls -- a real sentence may legitimately say "PyTorch 1.0
    shipped 7 December 2018; 7 years ago (2018-12-07) the ecosystem was much
    smaller". The license label alone hits 6 controls ("the paper's content
    license is Creative Commons Attribution 4.0"). "Content license" + a CC
    name within 60 chars still hits "The model card lists: Created by Meta,
    Content license CC BY-NC 4.0, and Type of site research" -- real knowledge.
    Requiring the template THEN the label inside 60 chars removes every one of
    them: prose that names both puts a sentence boundary between them, and the
    template only ever precedes the field table.

    Measured: 1 buffer hit and it IS the leak (the writer gate accepted it,
    `_is_junk` False) -> 0 of 3,059 `longterm_episodes`, 0 of 642 gate-test
    literals, 0 FPs on 25 prose controls, 0 on a 12-strong hostile set that
    quotes the template and the license label separately.
    """
    return bool(_INFOBOX_FACTROW_TAIL_RE.search(text or ""))


def _is_jobboard_ad_run_chrome(text):
    """True when `text` is a job-board's repeated ad/slogan run.

    Live 20.09.26 (class 108): `cycle_c_github` stored

        Haystack - Tech hiring without the hassle - Explore the tech scene on
        your terms. Haystack connects world-class tech talent with employers
        that match their interests and values.; Haystack - Get hired without
        the hassle - Haystack is where the best in tech go to stay ahead ...

    The recruiter brand repeated >=2x welded to its own slogan is a SERP ad run,
    not knowledge. The discriminator is the CONJUNCTION: the slogan alone is one
    marketing phrase away from real prose (`The recruiter said the role was tech
    hiring without the hassle`), so the repeated brand is required. Measured: 1
    buffer hit and it IS the leak; the other buffer row carrying the brand twice
    (`pip install haystack-ai Get Started with Haystack`) does NOT carry the
    slogan and is left alone; 0 of 3,059 `longterm_episodes`, 0 gate-test
    literals.
    """
    low = (text or "").lower()
    return _JOBBOARD_SLOGAN in low and low.count(_JOBBOARD_BRAND) >= _JOBBOARD_MIN_BRAND

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
    r"^\s*(?:The\s+)?shared underlying pattern"
    r"(?:[^\n]{0,30}?\bone sentence)?\s*\.?\s*$",
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

# class 148 markers (live 22.09.26) -- see _is_need_plan_echo.
# A BARE imperative plan voice: the model answers its own question with what
# it intends to WRITE ("Need maybe structure: ..."), not world knowledge.
# START-anchored so the same words inline in real prose stay learnable
# ("We need to reduce peak memory ...", "The plan needs three properties ...").
_NEED_PLAN_ECHO_RE = _re.compile(r"^\s*\**\s*need\b", _re.IGNORECASE)
_NEED_PLAN_ECHO_MAX = 300


def _is_need_plan_echo(text):
    """True when `text` is the learner's own generation PLAN, not an answer.

    Live 22.09.26 (class 148): the reasoning-loop cycles stored 12 completions
    that open with a dangling plan verb --

        Need maybe structure: intro: memory consolidation is offline ...
        Need address inner alignment, outer alignment, deceptive alignment ...
        Need likely comprehensive.

    `internet_learner._INSTRUCTION_OPENER_RE` already refuses these at
    extraction time (same anchored `need\b` shape), which is why `--once`
    reports "shallow + deep read both gated" -- but the WRITER gate had no
    counterpart, so they were STORED. The asymmetry, not the shape, is the
    bug: a row the extractor refuses must never reach the buffer.

    The discriminator is the ANCHORED opener plus the length cap. Real prose
    embeds the verb ("We need to reduce peak memory", "The plan needs three
    properties") and never STARTS with it; the echoes are all <= 300 chars.
    Measured: 12/300 buffer hits and all 12 ARE the leak -> 0 collateral,
    0/3,064 `longterm_episodes`, 0/1,278 asserted-clean gate-test literals.
    """
    if text is None:
        return False
    s = text.strip()
    if not s or len(s) > _NEED_PLAN_ECHO_MAX:
        return False
    return bool(_NEED_PLAN_ECHO_RE.search(s))

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


# class 81 markers (live 19.09.26) -- see _is_institution_abstract_tail_chrome.
# An affiliation line welded to a TRUNCATED abstract number at the very end of
# a record: `... on a reasoning task Waseda University Abstract 9.`
_INSTITUTION_ABSTRACT_TAIL_RE = _re.compile(
    r"\b(?:University|Universit\u00e4t|Institute|Institut|College|Laboratory|Lab|School)"
    r"\s+Abstract\s+\d{1,3}\s*\.\s*$")


def _is_institution_abstract_tail_chrome(text):
    """True when `text` ends in an affiliation + truncated `Abstract <n>.` tail.

    Live 19.09.26: `cycle_h_efficiency` stored
      "Language-model groups overstate consensus when replaying human
       deliberation on a reasoning task Waseda University Abstract 9."
    -- a paper-listing card whose text was cut off mid-tail: affiliation, then
    the abstract's ORDINAL (`Abstract 9.`), nothing after it. 125 chars WITH
    digits, so the >=90 length trust AND the technical-signal gate both fired
    and no existing marker matched (`_is_arxiv_abstract_chrome` needs the
    viewer labels `View PDF` / `HTML (experimental)`; `_is_nav_list` needs >=6
    TitleCase tokens with no comma; the byline helpers are English-keyed on
    `By <Name>` / `Published` / `Share`).

    The discriminator is the PAIR: an institution label AND a bare abstract
    ordinal glued at the TAIL. `Read Abstract 9 for the training details.` and
    `The Laboratory Abstract 5 was rejected by the reviewers.` are ordinary
    prose and carry no institution-label + tail weld. Measured: 1 buffer hit
    and it IS the leak; 0/6,302 buffer_junk rows; 0/3,059 longterm_episodes;
    0/824 gate-test literals; 0/29 hostile prose controls.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_INSTITUTION_ABSTRACT_TAIL_RE.search(t))


# class 82 markers (live 19.09.26) -- see _is_trending_card_header_pair.
# A GitHub trending card whose two header labels were welded into the text:
# `This Week Last Update: 2 days ago See Project 2 OpenManus Open-source AI ...`
_TRENDING_CARD_HEADER_RE = _re.compile(
    r"this\s+week\s+last\s+update\s*:\s*\d{1,3}\s+days?\s+ago\s+see\s+project\s+\d{1,3}",
    _re.IGNORECASE)


def _is_trending_card_header_pair(text):
    """True when `text` carries a trending card's welded header PAIR (class 82).

    Live 19.09.26: a post-fix `cycle_c_github` stored
      "This Week Last Update: 2 days ago See Project 2 OpenManus Open-source
       AI agent framework OpenManus is an open-source AI agent framework
       designed to autonomously execute complex, multi-step tasks by
       combining reasoning, planning, and tool use."
    -- the trending page's two card labels (`This Week Last Update: ...` and
    `See Project N`) welded onto the repo description. 242 chars WITH digits,
    so the >=90 length trust AND the technical-signal gate both fired; the
    existing repo-listing helpers (`_is_trending_repo_row_chrome` wants the
    star counter `\u2605 <N>k +<M>` plus a language stat,
    `_is_repo_stat_footer_run` wants a commits/branches/tags footer,
    `_is_gh_listing_row` wants `Updated <Mon DD, YYYY>` + `Public Forked`)
    all returned False.

    The discriminator is the PAIR in its exact welded form: the `This Week
    Last Update: <n> days ago` label immediately followed by `See Project
    <n>` with a single space between them. Natural prose that talks about a
    weekly update or a project number carries punctuation between the halves.
    Measured: 1 buffer hit and it IS the leak; 0/6,313 buffer_junk rows;
    0/3,059 longterm_episodes; 0/845 gate-test literals; 0/20 natural prose
    controls.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_TRENDING_CARD_HEADER_RE.search(t))


# class 83 markers (live 19.09.26) -- see _is_aggregator_row_year_tail.
# A Hacker-News-style feed row that ends in an arXiv parenthesis-year tail:
# `CameronBanga 5 hours ago | 10 comments 58 Cache-to-Cache: Direct Semantic
#  Communication Between LLMs (2025) (arxiv.`
_AGGREGATOR_ROW_RE = _re.compile(
    r"\b\d{1,2}\s+(?:minutes?|hours?|days?)\s+ago\s*\|\s*\d{1,5}\s*comments?\b"
    r"[\s\S]{0,80}?\(\s*(?:19|20)\d\d\s*\)", _re.IGNORECASE)


def _is_aggregator_row_year_tail(text):
    """True for an aggregator feed row welded to an arXiv-year tail (class 83).

    Live 19.09.26: `cycle_b_papers` stored
      "CameronBanga 5 hours ago | 10 comments 58 Cache-to-Cache: Direct
       Semantic Communication Between LLMs (2025) (arxiv."
    -- a feed row (`<user> <relative-time> | <n> comments <points> <headline>`)
    welded onto the paper's `(2025) (arxiv` tail. 115 chars WITH digits, so
    the technical-signal gate fired; `_is_hn_item_chrome` and
    `_is_hn_feed_listing_chrome` (class 37/49) both returned False, because
    they require the `<relative-time> | N comments` unit to REPEAT (>=2).

    A single occurrence is deliberately NOT gated: class 37's own test asserts
    the single-unit control `The review took 2 days ago | 4 comments per
    reviewer were recorded.` must stay learnable, and a bare single-unit
    marker measured 4-9 control FPs here. The AU rule applies -- sweep the
    threshold, and when it cannot be lowered without FPs, the PATTERN is
    wrong: add a second structural co-occurrence. The co-occurrence that
    works is the page's own arXiv `(yyyy)` tail within 80 chars of the feed
    unit, which real prose about a relative time and a comment count does not
    carry.

    Measured: 1 buffer hit and it IS the leak; 0/6,313 buffer_junk rows;
    0/3,059 longterm_episodes; 0/845 gate-test literals (incl. the class-37
    leak and its clean single-unit control); 0/20 natural prose controls.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_AGGREGATOR_ROW_RE.search(t))


# class 143 markers (live 22.09.26) -- see _is_feed_handle_unit_row.
# A SINGLE (non-repeated) Hacker-News-style feed row, welded onto its own tail:
#   "DeepLogin 5 hours ago | 20 comments 193 Kev: Tiny Jev-like family of
#    decision models built on top of Qwen3."
# = submitter handle + relative time + `| N comments` + points + a SECOND
# handle + a headline. class 37 (_is_hn_feed_listing_chrome) needs that
# `<relative-time> | N comments` unit REPEATED (>=2), so a one-item feed row
# passes it; class 83 (_is_aggregator_row_year_tail) requires an arXiv
# `(yyyy)` tail; `_is_hn_item_chrome` (49) requires the aggregator's own name
# or the `New ask Hacker News story` label -- none of them matches.
#
# Discriminator (the class-83 precedent: a bare single-unit marker measured
# 4-9 control FPs, so add a SECOND structural co-occurrence instead of
# loosening the threshold): the feed row carries TWO handles -- the trailing
# `<points> <handle>:` is the points/handle pair the renderer emits for the
# item itself, which the relative-time+comments unit alone does not imply.
# Measured 22.09.26 over 12,322 rows (online_buffer, buffer_junk,
# longterm_episodes, world_model): 3 hits -- the live buffer row 149 (the
# leak) plus its two audit echoes, all the same string -> 0 real-prose FPs on
# an 11-case hostile battery (prose citing a relative time, a comment count,
# a points-like number, a named handle, a colon-attributed quote).
_FEED_HANDLE_TOKEN_RE = r"[A-Za-z][\w.\-]{2,20}"
#
# The trailing handle is matched CASE-SENSITIVELY via the scoped inline flag
# `(?-i:...)`: the page emits handles capitalized, while the surrounding row
# is matched case-insensitively. Without the scope, `[A-Z]` under
# IGNORECASE re-admits lowercase prose (`... and then 193 runs:`).
_FEED_HANDLE_TAIL_RE = r"(?-i:[A-Z])[\w.\-]{1,20}"
_FEED_HANDLE_UNIT_RE = _re.compile(
    r"\b" + _FEED_HANDLE_TOKEN_RE + r"\s+\d{1,3}\s+"
    r"(?:minutes?|hours?|days?|weeks?)\s+ago\s*\|\s*\d{1,5}\s*comments?\b"
    r"[\s\S]{0,80}?\b\d{1,5}\s+" + _FEED_HANDLE_TAIL_RE + r"\s*:",
    _re.IGNORECASE)


def _is_feed_handle_unit_row(text):
    """True when `text` is a single feed row: handle + time + comments + points + handle (143).

    Live 22.09.26 (class 143): `cycle_e_competitors`/`cycle_b_papers` stored

        DeepLogin 5 hours ago | 20 comments 193 Kev: Tiny Jev-like family of
        decision models built on top of Qwen3.

    -- the top item of a Hacker-News-style feed, cut off right after the
    headline's first line. 97 chars WITH digits, so the `>=90` length trust
    and the technical-signal gate both fired; no existing marker matched,
    because every sibling rule wants MORE structure than a one-item feed row
    carries (37: the unit repeated; 49: the aggregator's own name or its item
    label; 83: an arXiv year tail).

    Deliberately NOT loosening class 37's repetition threshold: its own test
    pins the single-unit control `The review took 2 days ago | 4 comments per
    reviewer were recorded.` as learnable. The second co-occurrence used here
    is the trailing points/handle pair, which is feed chrome and does not
    appear in prose that merely counts comments.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_FEED_HANDLE_UNIT_RE.search(t))


# class 144 markers (live 22.09.26) -- see _is_de_consultation_contact_chrome.
# A German shop page's nav lockup + consultation block welded together:
#   "Produkten PRODUKTBERATUNG Wir beraten Sie persönlich unter 0681
#    5866-4466 (Mo-Do 9-18 Uhr, Fr 9-17 Uhr)."
# A hotline number and opening hours are the shop's own furniture, not
# knowledge. 104 chars WITH digits, so the `>=90` length trust and the
# technical-signal gate both fired; the `_is_de_*` family covers pricing,
# double-opt-in newsletters, portal fact boxes and nav-weld headlines -- none
# of them a consultation/contact block.
#
# Discriminator: the CONJUNCTION of a consultation vocabulary term and a
# contact marker (a German phone form, `Uhr`, `Hotline`, `Telefon`) within 90
# chars on ONE line. Neither half is unique on its own -- `Uhr` is an ordinary
# German word and a phone form is ordinary prose -- which is why the pair is
# required (the AS/AU rule: when a single part cannot be made unique, add the
# second structural co-occurrence).
#
# Measured 22.09.26 over 12,336 rows (online_buffer, buffer_junk,
# longterm_episodes, world_model): 1 hit and it IS the leaking buffer row -> 0
# hits in 8,980 buffer_junk rows, 0/3,064 longterm_episodes, 0/1,647 gate-test
# literals; 0 FPs on 6 hostile prose controls (a bare `Die Beratung erfolgt
# telefonisch.`, a hotline mention without a number, and English prose carrying
# `9-18 hours` plus a 4-digit number) and 0/1,730 SKILL.md files.
_DE_CONSULT_PHRASE_RE = _re.compile(
    r"\b(?:beraten|Beratung|Bestellung|Kaufberatung|Angebot|Hotline|Telefon)\b",
    _re.IGNORECASE)
_DE_CONTACT_MARK_RE = _re.compile(
    r"\b0\d{2,5}[\s/-]\d{3,8}\b"
    r"|\b\+49\b"
    r"|\bUhr\b"
    r"|\bHotline\b"
    r"|\bTelefon\b",
    _re.IGNORECASE)


def _is_de_consultation_contact_chrome(text):
    """True when `text` is German consultation/contact chrome (class 144).

    Live 22.09.26: `cycle_f_multi_domain` stored

        Produkten PRODUKTBERATUNG Wir beraten Sie persönlich unter 0681
        5866-4466 (Mo-Do 9-18 Uhr, Fr 9-17 Uhr).

    -- a German shop's nav lockup welded to its consultation block. Real prose
    about a consultation or a phone line does not place a phone form or `Uhr`
    within 90 chars of the vocabulary term on an otherwise content-free line,
    which is what the conjunction tests.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    for m in _DE_CONSULT_PHRASE_RE.finditer(t):
        tail = t[m.end():m.end() + 90]
        if "\n" in tail:
            tail = tail.split("\n", 1)[0]
        if _DE_CONTACT_MARK_RE.search(tail):
            return True
    return False


# class 84 markers (live 19.09.26) -- see _is_pipe_byline_shares_header.
# A portal article header whose byline was welded to a pipe dateline and the
# site's own `Shares` affordance:
# `... HPC Cluster by Ali Azhar | July 15, 2026 Shares As investment in ...`
_PIPE_BYLINE_SHARES_RE = _re.compile(
    r"\bby\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s*\|\s*"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\s+Shares\b")


def _is_pipe_byline_shares_header(text):
    """True for a pipe-dateline byline welded to the site's `Shares` (class 84).

    Live 19.09.26: `cycle_f_multi_domain` stored
      "Wire How HPC and Simulation Are Powering the Next Wave of Physical AI
       HPC Cluster by Ali Azhar | July 15, 2026 Shares As investment in
       Physical AI accelerates, simulation is taking on a much larger role
       than simply generating synthetic training data."
    -- a portal article header: section chip, headline, byline, PIPED dateline,
    then the site's own `Shares` affordance glued to the lede. 157 chars WITH
    digits, so both the >=90 length trust and the technical-signal gate fired.

    **The existing helper covers the vocabulary but not the SHAPE** (the
    class-40/51 rule, third occurrence). `_is_news_byline_share_header`
    (class 51) already keys on `By <First> <Last>` + a dateline + `Share`, and
    still returned False: it requires a full WEEKDAY dateline, while this page
    ships a PIPE dateline with no weekday. `_strip_byline_prefix` (class 29)
    only strips a LEADING byline, and here the byline sits after a brand chip.

    The discriminator is the three-part weld: byline AND pipe dateline AND the
    bare `Shares` token immediately after the date. Prose that merely credits
    an author or reports share counts carries no such weld. Measured: 1 buffer
    hit and it IS the leak; 0/6,313 buffer_junk rows; 0/3,059
    longterm_episodes; 0/845 gate-test literals; 0/20 natural prose controls.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_PIPE_BYLINE_SHARES_RE.search(t))


# class 85 markers (live 19.09.26) -- see _is_portal_counter_bar_comparison.
# A news portal's counter bar welded to a comparison headline:
# `Instant 23-Aug-2026 0 207 Technology OpenAI Workspace Agents vs Google
#  Gemini Enterprise: Complete Comparison 2026 OpenAI Workspace Agents vs ...`
_PORTAL_COUNTER_BAR_RE = _re.compile(
    r"\b\d{1,2}-[A-Z][a-z]{2}-\d{4}\s+\d{1,4}\s+\d{1,4}\s+[A-Z][a-z]+\b"
    r"[\s\S]{0,120}?Complete\s+Comparison")


def _is_portal_counter_bar_comparison(text):
    """True for a portal counter bar welded to a comparison headline (class 85).

    Live 19.09.26: `cycle_g_security` stored
      "Instant 23-Aug-2026 0 207 Technology OpenAI Workspace Agents vs Google
       Gemini Enterprise: Complete Comparison 2026 OpenAI Workspace Agents vs
       Google Gemini Enterprise is a comparison of two enterprise agent
       platforms introduced on April 22, 2026."
    -- the listing page's own counter bar (`Instant <dd-Mon-yyyy> <n> <n>
    <Category>`) welded onto the headline and its lede. 246 chars WITH digits,
    so both the >=90 length trust and the technical-signal gate fired.

    The discriminator is a CONJUNCTION, not a phrase (the AU rule). Two
    narrower forms were measured and REJECTED: the bare date + two counters +
    category label scored 4 hostile recombinants (`The log line 23-Aug-2026 0
    207 Technology was parsed by the tool.`), and adding the leading `Instant`
    token still left 2 (`Instant 23-Aug-2026 0 207 Technology is the scraped
    badge text.`). Adding the site's own headline label `Complete Comparison`
    within 120 chars of the counter bar reached 0 on every corpus.

    Measured: 1 buffer hit and it IS the leak; 0/6,313 buffer_junk rows;
    0/3,059 longterm_episodes; 0/845 gate-test literals; 0/24 natural prose
    controls.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_PORTAL_COUNTER_BAR_RE.search(t))

# class 86 markers (live 19.09.26) -- see _is_release_notes_pr_bullet.
_CHANGELOG_PR_RE = _re.compile(
    r"\(\s*#\d{3,}\s*\)\s*(?:Allow|Add|Fix|Support|Enable|Improve|Update|Remove|Bump|Refactor)\b")


_RELEASE_NOTE_EMOJI_RE = _re.compile(
    r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\bv?\d+\.\d+(?:\.\d+){1,2}\b"
    r"|\[\s*\d{1,2}/\d{4}\s*\])"
    r"[^\n]{0,40}?"
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF]{1,3}\s*"
    r"(?:Released|Add(?:ed)?|Update[ds]?|Fixed|Removed|Improved|Launched"
    r"|Introduced|Deprecated|Enabled)\b",
    _re.I,
)

def _is_release_note_emoji_bullet(text):
    """True for a release-notes changelog bullet anchored by a date + emoji (125).

    Live 21.09.26: `cycle_b_papers` stored a model card's changelog tail
      "F16 on BitNet-embedding-270M prefill (8 threads) Supports I2_S conversion
       with optimized kernels on x86 CPUs Lossless inference with 2 bits per
       weight 07/16/2026: <megaphone> Released BitNet Embeddings 0."
    -- a version stamp, then an emoji-led changelog bullet, welded to the card's
    feature list. 185 chars WITH digits, so the >=90 length trust AND the
    technical-signal gate both fired. The existing changelog helpers all miss it:
    `_is_release_notes_pr_bullet` needs a `( #N )` PR number and
    `_is_changelog_chain` needs >=3 bracketed links.

    The discriminator is the CONJUNCTION: a date/version STAMP within 40 chars
    of an emoji-led changelog VERB. The emoji+verb alone was measured and
    REJECTED -- 4 real `longterm_episodes` rows and 1 hostile control
    ("openamer auf ... update" + a warning sign) matched; the stamp anchor
    takes both corpora to 0.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_RELEASE_NOTE_EMOJI_RE.search(t))


def _is_release_notes_pr_bullet(text):
    """True for a release-notes changelog bullet welded to its PR number (86).

    Live 19.09.26: `cycle_b_papers` stored
      "HMX flash-attention head_dim padding (support DK=DV=72) ( #26539 )
       Allow HMX flash-attention to run with head_dim not a multiple of 64 (e."
    -- a GitHub release-notes line: the change title, its parenthesised PR
    number and the `Allow <X> to ...` bullet body. 138 chars WITH digits, so
    the >=90 length trust and the technical-signal gate both fired.

    The discriminator is the WELD: a parenthesised PR number whose parenthesis
    is immediately followed by a changelog imperative verb. The bare
    `( #N )` form was measured and REJECTED (1 control FP `The patch ( #1234 )
    was reverted after the regression report.` + 3 episodes); the verb-anchored
    form measured 0 on every corpus.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_CHANGELOG_PR_RE.search(t))


# class 87 markers (live 19.09.26) -- see _is_midtext_byline_counter_run.
_MIDTEXT_BYLINE_RE = _re.compile(
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,}\s+[A-Z][a-z]+\s+(?:[A-Z][a-z]+\s+)?"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}"
    r"\s+\d{1,4}\s+\d{1,4}\s+\d{1,4}\s+Share\b")


def _is_midtext_byline_counter_run(text):
    """True for a headline run welded to a mid-text byline counter bar (87).

    Live 19.09.26: `cycle_d_docs` stored
      "Demystifying the Compression of Large Language Models Maarten
       Grootendorst Jul 22, 2024 544 26 47 Share Translations - Korean -
       Chinese - French As their name suggests, Large Language Models (LLMs)
       are often too large to run on consumer hardware."
    -- a blog article header: the TitleCase headline run, the author byline,
    the dateline, the bare counter bar and the site's own `Share` affordance.

    **The existing helper covers the vocabulary but not the POSITION** (the
    class-29/40/51/84 rule): `_strip_byline_stack` (class 15) keys on exactly
    this `<Name> <date> <counters> Share` order but uses `.match()`, i.e. it
    only fires when the byline LEADS the text. Here a headline run precedes it.
    The discriminator is the headline RUN + the byline counter bar. Without the
    headline run the loose form measured 2 control FPs
    (`Authors: Smith Feb 3, 2026 12 4 9 Share the findings in the appendix.`);
    with it, 0 on every corpus.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_MIDTEXT_BYLINE_RE.search(t))


# class 88 markers (live 19.09.26) -- see _is_relative_time_counter_row.
_RELTIME_COUNTER_ROW_RE = _re.compile(
    r"\b\d{1,4}\s+(?:minutes?|hours?|days?)\s+ago\s+\d{1,4}\s+\d{1,4}\s+[A-Z][a-z]")


def _is_relative_time_counter_row(text):
    """True for a feed row: relative time + bare counters + a headline (88).

    Live 19.09.26: `cycle_f_multi_domain` / `cycle_a_technews` stored
      "General Physics 52 minutes ago 0 0 Circular Rydberg atoms set three
       records, staying stable for 11 milliseconds Rydberg atoms are ..."
    -- a physics-feed listing row: the section label, the relative time, two
    bare counters and the headline. Passed both gates on its digits.

    The discriminator is the CONJUNCTION (the AU rule): the relative time must
    be followed by TWO bare counters AND a Capitalized headline word. The bare
    relative time alone matches ordinary prose (`It ran 3 hours ago with 12 4
    retries recorded in the log.`) and was REJECTED. Measured: 2 buffer hits,
    both the leak family; 0/24 hostile controls; 0/3,059 longterm_episodes;
    0/857 gate-test literals.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_RELTIME_COUNTER_ROW_RE.search(t))


# class 89 markers (live 19.09.26) -- see _is_project_count_news_tail.
_PROJECT_COUNT_NEWS_TAIL_RE = _re.compile(
    r"\d+\s+projects?\s*\|\s*news\.\s*$")


def _is_project_count_news_tail(text):
    """True when `text` ends on a newsroom cross-post counter bar (89).

    Live 19.09.26: `cycle_e_competitors` stored
      "PowerContext, Context for work that humans and agents hand off and
       continue 1 project | news."
    -- a newsroom card tail (`<n> project | news.`). Only 93 chars, so the
    >=90 length trust never applied.

    The anchor is the TAIL (`$`), exactly like class 56's `dev.` sibling:
    `2 projects | news.` mid-sentence is ordinary prose. Measured: 1 buffer
    hit and it IS the leak; 0/24 hostile controls; 0/3,059
    longterm_episodes; 0/857 gate-test literals.
    """
    return bool(_PROJECT_COUNT_NEWS_TAIL_RE.search(text or ""))


# class 90 markers (live 19.09.26) -- see _is_course_cta_opener.
_COURSE_CTA_OPENER_RE = _re.compile(
    r"^Start this course\s*(?:\u2192|->)", _re.MULTILINE)


def _is_course_cta_opener(text):
    """True for a course landing-page CTA opener (90).

    Live 19.09.26: `cycle_g_security` stored
      "Start this course \u2192 Building AI Agents How agents work, how they
       fail, and how to design ones worth deploying."
    -- the landing page's own arrow CTA welded to the course-bundle headline.

    `_is_course_cta_chrome` (class 10 era) keys on a promo voice AND a bundle
    phrase and does NOT match this shape. The discriminator is the
    START-anchored arrow CTA: the bare `Start this course` measured 1 control
    FP (`Start this course to learn how agents work and how they fail in
    production.`), the arrow-anchored form 0. Measured: 1 buffer hit and it IS
    the leak; 0/24 hostile controls; 0/3,059 longterm_episodes; 0/857
    gate-test literals.
    """
    return bool(_COURSE_CTA_OPENER_RE.search(text or ""))


# class 92 markers (live 19.09.26) -- see _is_code_linenum_run.
_CODE_LINENUM_RE = _re.compile(r"\b\d(?:\s+\d){5,}\s+#\s+[A-Z][a-z]")


def _is_code_linenum_run(text):
    """True for a code block whose line-number gutter was welded in (92).

    Live 19.09.26: `cycle_d_docs` stored (twice, two near-identical rows)
      "The Challenge: Full Fine-Tuning Limitations Resource Requirements Full
       fine-tuning requires updating all model parameters, leading to
       substantial computational overhead: 1 2 3 4 5 6 # Full fine-tuning a 7B
       parameter model model = AutoModelForCausalLM ."
    -- a docs section whose code block lost its newlines, so the line-number
    gutter (`1 2 3 4 5 6`) runs into the `#` comment and the code.

    The discriminator is the digit RUN welded directly to a code comment. The
    bare `1 2 3 4 5 6` form matches the docs' pagination chrome (a known leak)
    and ordinary prose (`The code \`1 2 3 4 5 6 # setup\` appears in the
    notebook listing.`) and was REJECTED; requiring the `#` + a Capitalized
    comment word measured 0 on every corpus. Measured: 2 buffer hits, BOTH the
    leak family; 0 hostile-control FPs; 0/3,059 longterm_episodes; 0/857
    gate-test literals.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_CODE_LINENUM_RE.search(t))


# class 93 markers (live 19.09.26) -- see _is_share_exec_summary_header.
_SHARE_EXEC_SUMMARY_RE = _re.compile(r"\bShare\s+Executive\s+Summary\b")


def _is_share_exec_summary_header(text):
    """True for an article header's `Share Executive Summary` affordance (93).

    Live 19.09.26: `cycle_g_security` stored
      "LLM Prompt injection Share Executive Summary Palo Alto Networks has
       released \u201c Securing GenAI: A Comprehensive Report on Prompt
       Attacks: Taxonomy, Risks, and Solutions ,\u201d which surveys emerging
       prompt-based attacks on AI applications and AI agents."
    -- a report page's tag chip, its `Share` control and its `Executive
    Summary` tab, welded to the report's own abstract.

    The discriminator is the space-glued PAIR of the page's OWN two affordances.
    `Share` alone and `Executive Summary` alone are both ordinary English
    (`Readers can Share an Executive Summary with their team.`), so only the
    welded pair is safe. Measured: 1 buffer hit and it IS the leak; 0/24
    hostile controls; 0/3,059 longterm_episodes; 0/857 gate-test literals.
    """
    return bool(_SHARE_EXEC_SUMMARY_RE.search(text or ""))


# class 95 markers (live 19.09.26) -- see _is_relative_stamp_news_run.
# A dated newsroom feed run: the composite relative stamp `N days, N hours ago`
# repeated, each stamp followed by a capitalised headline word:
# `OpenAI is buying failed biotech trade secrets to train medical models
#  3 days, 11 hours ago Salesforce built Koa to stop paying Anthropic and
#  OpenAI millions 3 days, 12 hours ago Anthropic and OpenAI want an AI freeze.`
_RELATIVE_STAMP_NEWS_RUN_RE = _re.compile(
    r"(?:\d{1,2}\s+days?,\s*\d{1,2}\s+hours?\s+ago\s+[A-Z][a-z])"
    r"[\s\S]{0,80}?"
    r"(?:\d{1,2}\s+days?,\s*\d{1,2}\s+hours?\s+ago\s+[A-Z][a-z])")


def _is_relative_stamp_news_run(text):
    """True for a newsroom feed run: repeated relative stamps + headlines (95).

    Live 19.09.26: `cycle_f_multi_domain` stored
      "OpenAI is buying failed biotech trade secrets to train medical models
       3 days, 11 hours ago Salesforce built Koa to stop paying Anthropic and
       OpenAI millions 3 days, 12 hours ago Anthropic and OpenAI want an AI
       freeze."
    -- a dated news-card feed: three headlines, each welded to the site's own
    composite relative stamp (`<n> days, <n> hours ago`). 217 chars WITH
    digits, so the >=90 length trust and the technical-signal gate both fired.
    `_is_relative_time_nav_chain` (class 34) needs the `For You/Latest/
    Trending` labels this page does not ship; `_is_hn_feed_listing_chrome`
    (37) / `_is_hn_item_chrome` (49) / `_is_aggregator_row_year_tail` (83)
    all key on a `| N comments` unit; `_is_relative_time_counter_row` (88)
    on TWO bare counters; the class-94 archive entry measured the bare
    relative stamp (`\d+ (min|hour)s? ago`) and REJECTED it as ordinary
    prose (`It ran 3 hours ago with 12 4 retries recorded in the log.`) --
    which is why the COMPOSITE `days, hours` form plus REPETITION is the
    discriminator here.

    Measured (case-sensitive, so `[A-Z][a-z]` is a real anchor):
    buffer 1 hit and it IS the leak; 0/6,242 `buffer_junk` rows; 0/3,059
    `longterm_episodes`; 0/947 gate-test string literals; 0/14 hostile
    controls (incl. the class-83 `CameronBanga 5 hours ago | ...` and the
    class-37 single-unit control, which carry no composite stamp, and the
    declarative `We compared 3 days, 11 hours ago against 2 weeks, 5 hours
    ago in the benchmark.`, which carries no capitalised word after the
    stamp). The bare composite stamp WITHOUT the capitalised word was
    REJECTED: it matches all four declarative prose controls, and the
    `>=2` count form additionally matched one real `buffer_junk` row.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_RELATIVE_STAMP_NEWS_RUN_RE.search(t))


# class 94 markers (live 19.09.26) -- see _is_citation_counter_run.
_CITATION_COUNTER_RUN_RE = _re.compile(
    r"\b\d{1,3}\s+\d{1,3}\s+\d{1,3}\s+\d{1,3}\s+[A-Z][a-z]")


def _is_citation_counter_run(text):
    """True for a reference-counter run repeated inside prose (94).

    Live 19.09.26: `cycle_f_multi_domain` stored
      "AI systems without human supervision for worker surveillance and
       quality inspection in industrial sectors 4 4 5 5 However, the bill does
       allow authorities to use real-time biometric surveillance in public
       spaces for national security reasons 1 1 2 2 ."
    -- an academic-paper page whose citation-marker runs (`4 4 5 5`) were
    welded into the prose.

    The discriminator is the four-number run welded to a Capitalized word; a
    bare digit run matches ordinary tabular prose and was measured as a topic
    trap. Measured: 1 buffer hit and it IS the leak; 0/24 hostile controls;
    0/3,059 longterm_episodes; and the one gate-test literal it matches
    (`Onboarding Code Comprehension ... 1 2 3 4 5 6 7 8 9 10 11 Next ...`) is
    a KNOWN leak already asserted as junk, i.e. a true positive.
    """
    t = text or ""
    if len(t) > 1200:
        return False
    return bool(_CITATION_COUNTER_RUN_RE.search(t))








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
# class 81 (live 20.09.26): same own-artifact family, third TITLE --
#   "Continuous Learning Loop: Error-Capture + Categorization + Memory
#    + Auto-Skill-Generation + Trend."
# Measured: 1 buffer hit (the leak) / 0 control FPs on 11 prose
# controls / 0 test literals; the 4 episode hits are the SAME
# own-artifact strings (English + German), not world knowledge.

# class 82 markers (live 20.09.26) -- see _is_de_nav_weld_headline_chrome.
# A German site's nav-label WELD stored as the answer: >=2 nav labels joined
# by whitespace ONLY, followed by a TitleCase colon headline. Live leak:
#   "Blogs Karriere Über uns U Vertrieb kontaktieren LLM Agent Sandboxing:
#    Wie MCP, Tool Permissions und DSGVO zusammenpassen"
# The weld is the discriminator: every comma/conjunction-joined control stays
# clean (`Impressum Datenschutz AGB sind rechtliche Pflichtangaben.` is ordinary
# German prose naming the same labels), and so does `Impressum Datenschutz AGB:
# rechtliche Pflichtangaben.` Measured: 1 buffer hit (the leak) -> 0 FPs on 17
# hostile controls, 0 of 6,118 longterm_episodes, 0 test literals.
_DE_NAV_WELD_LABELS = (r"(?:Blogs?|Karriere|Über uns|Ueber uns|Vertrieb kontaktieren"
                       r"|Impressum|Datenschutz|AGB|Kontakt|Unternehmen|Leistungen"
                       r"|Referenzen|Team|Standort|News|Presse|Preise|Produkte)")
_DE_NAV_WELD_HEADLINE_RE = _re.compile(
    r"(?i)\b" + _DE_NAV_WELD_LABELS + r"(?:\s+" + _DE_NAV_WELD_LABELS + r"){1,}"
    r"[\s\S]{0,80}?[A-ZÄÖÜ][^:\r\n]{8,80}:\s*\S")


def _is_de_nav_weld_headline_chrome(text):
    """True for a German nav-label weld stored as the answer (class 82).

    The page's menu lost its separators, so its own labels are welded together
    and run into the article headline. A `,`/`und`-joined list of the SAME
    labels is ordinary German prose and stays learnable.
    """
    return bool(_DE_NAV_WELD_HEADLINE_RE.search(text or ""))
_OWN_PLAN_PLUS_RUN_RE = _re.compile(
    r"^\s*(?:Energy efficiency|KI-Performance-Optimierung|AI performance optimization"
    r"|Performance optimization|Efficiency|Continuous Learning Loop"
    r"|Kontinuierliche Lernschleife)[^:\r\n]{0,40}:"
    r"[^\r\n]{0,200}\+[^\r\n]{0,120}\+[^\r\n]{0,120}\+",
    _re.IGNORECASE | _re.MULTILINE)


def _is_own_plan_plus_run(text):
    """True for the agent's own deliverable plan stored as knowledge (class 80).

    Measured: 1 buffer hit (the leak) -> 0 FPs on 6 prose controls, 0 test
    literals; the single `longterm_episodes` hit is the SAME own-artifact string
    in German, i.e. the same leak, not world knowledge.
    """
    return bool(_OWN_PLAN_PLUS_RUN_RE.search(text or ""))



# class 96 markers (live 19.09.26) -- see _is_bare_markdown_heading_fragment.
# A stored "answer" that is nothing but ONE markdown heading line: the extractor
# kept the section title and dropped the body. Live leak (42 chars, so the >=90
# length trust never applied):
#   "## Ollama Model Analysis for Your Hardware"
# Measured: 1 buffer hit (the leak) -> 0 FPs on 10 prose controls (incl. a real
# heading WITH a body, and a hashtag run), 0 of 3,059 longterm_episodes, 0 test
# literals. The word cap and the "no terminal punctuation" guard are what keep
# ordinary one-line prose sentences out.
_BARE_HEADING_FRAGMENT_RE = _re.compile(
    r"^#{1,4}[ \t]+(?![^\r\n]*[#])(?![^\r\n]*[.!?:;])[^\r\n]*(?:[ \t]+[^\r\n]*){0,8}$")


def _is_bare_markdown_heading_fragment(text):
    """True when the whole stored text is a single markdown heading line."""
    return bool(_BARE_HEADING_FRAGMENT_RE.match((text or "").strip()))


# class 97 markers (live 19.09.26) -- see _is_german_glossary_echo.
# The agent's OWN German glossary line stored as knowledge (80 chars; the
# documented short-fragment family that passes both gates because no marker
# matched). Live leak:
#   "German: Fehler-Capture = error capture, Kategorisierung = categorization, Memory"
# Two `=` pairs AND no terminal punctuation is the discriminator: real glossary
# prose carries a closing period (or is a single pair). Measured: 1 buffer hit
# (the leak) -> 0 FPs on 6 prose controls, 0 episodes, 0 test literals.
_GERMAN_GLOSSARY_ECHO_RE = _re.compile(
    r"^German:[^\r\n]*=[^\r\n]*=[^\r\n]*[^.!?\r\n]$")


def _is_german_glossary_echo(text):
    """True for the agent's own two-pair German glossary line echoed back."""
    return bool(_GERMAN_GLOSSARY_ECHO_RE.match((text or "").strip()))





# class 99 markers (live 19.09.26) -- see _is_related_subjects_sidebar.
# A publisher's "related content" sidebar stored as the answer (240 chars, so the
# >=90 length trust applied; the digit-bearing `© 2024` fed the technical
# signal). Live leak:
#   "Techno-Critics’ Article 30 June 2025 Considerations About the Regulatory
#    Framework of Cryptocurrency Chapter © 2024 Explore related subjects Discover
#    the latest articles, books and news in related subjects, suggested using
#    machine learning."
# The discriminator is the sidebar's OWN welded label run, not the topic:
# `discover the latest articles, books` alone is ordinary prose
# ("Discover the latest articles in our library and read them." is fine).
_RELATED_SUBJECTS_SIDEBAR_RE = _re.compile(
    r"explore related subjects[\s\S]{0,40}discover the latest",
    _re.IGNORECASE)


def _is_related_subjects_sidebar(text):
    """True for a publisher's welded 'related content' sidebar label run."""
    return bool(_RELATED_SUBJECTS_SIDEBAR_RE.search(text or ""))


# class 102/103 markers (live 19.09.26) -- see the two helpers below. Mirrors
# internet_learner._is_aggregator_affordance_min_run / _is_startup_portal_nav_run
# (the AH both-files rule).
# (a) class 102: a model-aggregator landing page (affordance label welded to the
# site's own read-time label `\u00b7 N min`).
_AGGREGATOR_AFFORDANCE_MIN_RE = _re.compile(
    r"(?:read\s+full\s+article|try\s+on\s+[A-Z][A-Za-z0-9]{2,})"
    r"[\s\S]{0,60}?\u00b7\s*\d{1,3}\s*min",
    _re.IGNORECASE)


def _is_aggregator_affordance_min_run(text):
    """True for an aggregator's affordance label welded to its read time."""
    return bool(_AGGREGATOR_AFFORDANCE_MIN_RE.search(text or ""))


# (b) class 103: a startup portal's welded nav label run.
_STARTUP_PORTAL_NAV_RE = _re.compile(
    r"featured\s+startup\s+spotlight[\s\S]{0,40}?tech\s+startup\s+news"
    r"[\s\S]{0,20}?tech\s+startups",
    _re.IGNORECASE)


# class 126 (live 21.09.26): a video/news platform's OWN client-SDK package
# family named as the SUBJECT, welded to an "open-source SDKs (e.g. `...`)"
# opener -- "YouTube's open-source SDKs (e.g., `youtubei1`, `youtubei2`,
# `youtubei3`) are the only reliable way to programmatically control the API,
# bypass rate limits, and access private endpoints". It reached the training
# buffer 3x (19.09 00:24, 21.09 10:14, 21.09 16:04) -- the third time as a
# duplicate of the first, i.e. the SAME page was deep-read twice and the
# exact-`_is_duplicate` gate could not see it because the sentence drifted
# (`youtubei-python`/`youtubei-webapp` -> `youtubei1`/`youtubei2`/
# `youtubei3`). It is platform plumbing for that site's own API, not knowledge
# an agent can act on, so it is chrome. Discriminator: the backticked SDK
# family welded to the "open-source SDKs (e.g." opener. The opener ALONE is not
# enough (generic prose about open-source SDKs is learnable); the package
# family is the anchor. Measured: 10 hits over online_buffer + buffer_junk +
# both junk archives + kta_log + internet_learn_log + world_model (7.9 MB) +
# longterm_episodes (50 MB) -- ALL 10 are this leak, 0 false positives.
# A generic same-`u` similarity gate (token-set Jaccard) was MEASURED AND
# REJECTED: the three leak rows score 0.241/0.308/0.327 while legitimate
# distinct rows for one `u` score up to 0.400 -- no separation, so a threshold
# would only delete real learnings.
_SDK_FAMILY_WELD_RE = _re.compile(
    r"open[- ]source\s+SDKs?\s*\(?\s*e\.g\.?[\s\S]{0,80}?youtubei",
    _re.IGNORECASE)


def _is_platform_sdk_family_weld(text):
    """True for a platform's own client-SDK family welded to an SDKs opener."""
    return bool(_SDK_FAMILY_WELD_RE.search(text or ""))


def _is_startup_portal_nav_run(text):
    """True for a startup portal's welded nav label run."""
    return bool(_STARTUP_PORTAL_NAV_RE.search(text or ""))


# class 128 (live 21.09.26): an AI-agent INDEX landing page stored as the
# answer -- same shape as internet_learner._is_agent_index_nav_run; keep both
# files in sync. This is one of the TWO rows that made the KTA competitor-gap
# experiment report `signal NOT mappable`: the consumer reads the LAST
# lexicon-matching buffer row, so a nav row appended late poisons every
# subsequent run.
#
# REJECT, not strip: the prose behind the run is a generic lede with no
# capability token. TWO independent conjuncts in order (a single token like
# `compare alternatives` is ordinary English). Measured: 1 buffer hit
# (= this leak), 0 prose FPs, 0 longterm_episodes FPs, 0 test-literal FPs.
_AGENT_INDEX_NAV_RE = _re.compile(
    r"compare\s+alternatives[\s\S]{0,80}?advertise\s+api",
    _re.IGNORECASE)


def _is_agent_index_nav_run(text):
    """True for an AI-agent index landing page's welded affordance nav run."""
    return bool(_AGENT_INDEX_NAV_RE.search(text or ""))


# class 129 (live 21.09.26): a blog badge ribbon stored as the answer --
#   "Arab World #3 Featured Blog 85% 3 Machine Learning RAG Systems in
#    Production: Architecture, Tradeoffs, and Failure Modes
#    Retrieval-augmented generation (RAG) is the dominant application"
# The site's own card ribbon (rank badge + `Featured Blog` label + a percent
# counter + a bare index) is welded to the headline stack and its lede.
# 239 chars WITH digits, so the >=90 length trust AND the technical-signal
# gate both fired; `_is_blog_nav_feature_run_chrome` (class 106) needs a
# >=8-token nav vocabulary run and this ribbon has none.
#
# REJECT, not strip: the prose behind the ribbon is a generic RAG lede with
# no capability token (same call as class 128). THREE conjuncts in order --
# numbered badge, the site's own `Featured Blog` label, a percent ribbon --
# so no single ordinary-English token can fire it. A BARE `Featured Blog`
# marker was measured and REJECTED as too broad (it fired on all 3 natural
# prose counter-cases).
# Measured: 1 buffer hit and it IS the leak -> 0/7,984 buffer_junk rows,
# 0/3,059 longterm_episodes, 0/3 prose counter-cases.
_BADGE_RIBBON_RE = _re.compile(
    r"^[\s\S]{0,40}?#\s*\d{1,3}\b[\s\S]{0,60}?\bFeatured\s+Blog\b"
    r"[\s\S]{0,60}?\d{1,3}\s*%", _re.IGNORECASE)


def _is_badge_ribbon_chrome(text):
    """True for a blog card ribbon (rank badge + Featured Blog + percent)."""
    return bool(_BADGE_RIBBON_RE.search(text or ""))


# class 130 (live 22.09.26) -- a "source tally" CTA stored as knowledge.
# Exact leaked bytes (cycle_b_papers -> online_buffer.jsonl):
#     Curated from 71 sources: Anthropic, OpenAI, HN, arXiv, GitHub and more.
# It is the search widget's own footer, not a finding: the digit `71` fed
# `_TECH_HINT_RE` and `OpenAI` satisfied `_has_alpha_signal`, so the
# technical-signal gate and the 20-char floor both passed. Same family as the
# earlier marketing-slogan rules, but ANCHORED and requiring the trailing
# `and more`, which keeps real prose that happens to mention a count
# ("The survey was curated from 71 sources across three labs.") learnable.
# Measured FP replay: 1 hit over the live buffer and that hit IS the leak
# -> 0/8,064 buffer_junk rows, 0/3,058 longterm_episodes, 0 cross_domain rows.
_SOURCE_TALLY_CTA_RE = _re.compile(
    r"^\W*(?:curated|compiled|aggregated|sourced|collected|gathered)\s+"
    r"from\s+\d{1,4}\+?\s+sources?\b[^.]{0,160}?\band\s+more\.?\s*$",
    _re.IGNORECASE)


def _is_source_tally_cta(text):
    """True when `text` is a widget's "Curated from N sources ... and more" CTA."""
    return bool(_SOURCE_TALLY_CTA_RE.search(text or ""))


# class 138 (live 22.09.26): an ALL-CAPS nav lockup welded to a Title-Case word.
# The lookahead requires the weld (`SOLACE AGENT MESH Take ...`); the rule body
# then requires the SAME name in Title Case elsewhere in the string.
_CAPS_LOCKUP_ANCHOR_RE = _re.compile(
    r"\b[A-Z][A-Z0-9]{2,}(?:\s+[A-Z][A-Z0-9]{2,})+(?=\s+[A-Z][a-z])")


def _is_caps_nav_lockup_weld(text):
    """True for an ALL-CAPS nav lockup welded to prose AND repeated in Title Case (class 138).

    Live 22.09.26 (competitor + github cycles): a vendor's "Platform Demo"
    banner was stored twice in `online_buffer.jsonl` as
        "Platform Demo SOLACE AGENT MESH Take AI agents from idea to
         production, and keep making them better Solace Agent Mesh is an
         agent development and runtime platform that lets you build, test,
         deploy, observe and improve every agent through one lifecycle."
    252 chars with no digits and a heavy technical-noun load, so BOTH the
    >=90 "long prose" trust and the technical-signal gate passed it.

    Discriminator = a CASE SHIFT inside one extracted string: the nav lockup
    is ALL CAPS ("SOLACE AGENT MESH") while the sentence repeats the same
    product name in Title Case ("Solace Agent Mesh"). A real sentence picks
    one casing. Requires the lockup to be WELDED (followed by a Title-Case
    word = the lost-newline nav shape).

    Measured over 239 buffer prose rows, 3,059 `longterm_episodes`, 8,541
    `buffer_junk` answers, 1,813 gate-test string literals, 502 world_model
    effects and 18 hostile controls: **0 FPs**, and the leaking row is caught.
    Each conjunct ALONE was measured and REJECTED: the bare weld fires 26x on
    ordinary prose ("Alles erledigt. Hier die Zusammenfassung:"), the bare
    case-shift 2x (one real prose row). Both bare forms of the vendor name
    ("solace agent mesh", "platform demo") were likewise REJECTED on control
    FPs -- so this rule carries NO vendor literal and generalises.
    """
    t = text or ""
    if len(t) > 600:
        return False
    for m in _CAPS_LOCKUP_ANCHOR_RE.finditer(t):
        run = m.group(0)
        title = run.title()
        if title == run:
            continue
        if title in t:
            return True
    return False

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
    # an affiliation welded to a truncated abstract ordinal (class 81, 19.09.26)
    if _is_institution_abstract_tail_chrome(text):
        return True
    # a trending card's welded header pair (class 82, 19.09.26)
    if _is_trending_card_header_pair(text):
        return True
    # an aggregator row welded to an arXiv year tail (class 83, 19.09.26)
    if _is_aggregator_row_year_tail(text):
        return True
    # a single feed row: handle + relative time + comments + points + handle (class 143, 22.09.26)
    if _is_feed_handle_unit_row(text):
        return True
    # German consultation/contact chrome (class 144, 22.09.26)
    if _is_de_consultation_contact_chrome(text):
        return True
    # a pipe-dateline byline welded to the site's Shares (class 84, 19.09.26)
    if _is_pipe_byline_shares_header(text):
        return True
    # a portal counter bar welded to a comparison headline (class 85, 19.09.26)
    if _is_portal_counter_bar_comparison(text):
        return True
    # a release-notes changelog bullet welded to its PR number (class 86, 19.09.26)
    if _is_release_notes_pr_bullet(text):
        return True
    if _is_release_note_emoji_bullet(text):
        return True
    # a headline run welded to a mid-text byline counter bar (class 87, 19.09.26)
    if _is_midtext_byline_counter_run(text):
        return True
    # a feed row: relative time + bare counters + headline (class 88, 19.09.26)
    if _is_relative_time_counter_row(text):
        return True
    # a newsroom cross-post counter bar at the tail (class 89, 19.09.26)
    if _is_project_count_news_tail(text):
        return True
    # a course landing-page arrow CTA opener (class 90, 19.09.26)
    if _is_course_cta_opener(text):
        return True
    # a code block whose line-number gutter was welded in (class 92, 19.09.26)
    if _is_code_linenum_run(text):
        return True
    # an article header's Share Executive Summary affordance (class 93, 19.09.26)
    if _is_share_exec_summary_header(text):
        return True
    # a reference-counter run repeated inside prose (class 94, 19.09.26)
    if _is_citation_counter_run(text):
        return True
    # a dated newsroom feed run: repeated relative stamps (class 95, 19.09.26)
    if _is_relative_stamp_news_run(text):
        return True
    # a publisher's welded related-content sidebar label run (class 99, 19.09.26)
    if _is_related_subjects_sidebar(text):
        return True
    # an aggregator's affordance label welded to its read time (class 102, 19.09.26)
    if _is_aggregator_affordance_min_run(text):
        return True
    # a startup portal's welded nav label run (class 103, 19.09.26)
    if _is_startup_portal_nav_run(text):
        return True
    # an AI-agent index landing page's affordance nav run (class 128, 21.09.26)
    if _is_agent_index_nav_run(text):
        return True
    # a blog badge ribbon welded to a headline stack (class 129, 21.09.26)
    if _is_badge_ribbon_chrome(text):
        return True
    # a widget's "Curated from N sources ... and more" CTA (class 130, 22.09.26)
    if _is_source_tally_cta(text):
        return True
    # a bare date-stamped listing strip (class 131, 22.09.26)
    if _is_date_stamp_listing_strip(text):
        return True
    # a news photo-credit strip + byline + dateline (class 132, 22.09.26)
    if _is_credit_byline_run(text):
        return True
# a paper/arXiv listing row's submitter weld (class 135, 22.09.26)
    if _is_arxiv_submitter_run(text):
        return True
# an aggregator card header welded to the article title (class 136, 22.09.26)
    if _is_aggregator_card_header_weld(text):
        return True
# an aggregator card's affordance rail welded to the card (class 141, 22.09.26)
    if _is_aggregator_card_affordance_rail(text):
        return True
    # a breadcrumb run welded to a repeated title prefix (class 137, 22.09.26)
    if _is_breadcrumb_title_repeat(text):
        return True
    # a platform's own client-SDK family named as the subject (class 126, 21.09.26)
    if _is_platform_sdk_family_weld(text):
        return True
    # a bare markdown heading stored as the whole answer (class 96, 19.09.26)
    if _is_bare_markdown_heading_fragment(text):
        return True
    # the agent's own German glossary line (class 97, 19.09.26)
    if _is_german_glossary_echo(text):
        return True
    # an ALL-CAPS nav lockup welded to prose + repeated in Title Case
    # (class 138, 22.09.26)
    if _is_caps_nav_lockup_weld(text):
        return True
    # a paper/arXiv author list with affiliation superscripts (class 140, 22.09.26)
    if _is_affiliation_author_list(text):
        return True
    # a year-welded SERP title restated by its own snippet (class 141, 22.09.26)
    if _is_serp_title_snippet_repeat(text):
        return True
    # a nav-menu weld run into a card title restated twice (class 149, 23.09.26)
    if _is_nav_weld_repeat_chrome(text):
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
    # the learner's own bare "Need ..." generation PLAN (class 148, 22.09.26)
    if _is_need_plan_echo(text):
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
    # a German nav-label weld run into the article headline (class 82, 20.09.26)
    if _is_de_nav_weld_headline_chrome(text):

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
    # a HN item row with the site's own `Show HN:` tag (class 105, 19.09.26)
    if _is_hn_show_run_chrome(text):
        return True
    # a site nav-label run welded to `Featured #` (class 106, 19.09.26)
    if _is_blog_nav_feature_run_chrome(text):
        return True
    # a German newsletter double-opt-in confirmation page (class 107, 20.09.26)
    if _is_de_double_optin_newsletter_chrome(text):
        return True
    # a job-board's repeated brand + slogan ad run (class 108, 20.09.26)
    if _is_jobboard_ad_run_chrome(text):
        return True
    # a dated aggregator listing run: headline welded to its date, twice (class 113, 20.09.26)
    if _is_dated_listing_run(text):
        return True
    # a review card's date + glued read-time badge (class 114, 20.09.26)
    if _is_readtime_card_widget(text):
        return True
    # a wiki infobox fact-row tail: relative-age template + license field (class 118, 20.09.26)
    if _is_infobox_factrow_tail(text):
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


# A bare date-stamped LISTING STRIP (class 131, 22.09.26).
# Live: the efficiency cycle stored, verbatim from online_buffer.jsonl,
#   "Olaewg 2007-09-25 sylvu 2008-02-16 Ave 2008-02-17 Autor: tajger Data:
#    2006-07-03 12:20:25 Na poczatku tabelka 1-BIALKA, ..."
# - a foreign-language forum/post listing whose every entry carries its own
# bare ISO date glued to the entry's author label. Both gates passed it: the
# date digits fed the technical-signal gate and the length cleared the >=90
# "long prose" trust.
#
# Keyed on the STRUCTURE, never the language or the topic: the row must carry
# AT LEAST THREE `<word> <ISO date>` pairs inside the first 220 chars, with NO
# sentence period in that window (a listing concatenates labels and never ends
# a sentence) and the dates must span at least three DISTINCT YEARS (a
# listing strip mixes archived years; a changelog or a release cadence uses
# one or two). Measured 22.09.26 over 20,831 rows (online_buffer 236,
# buffer_junk 8,062, kta_log 712, internet_learn_log 2,438, longterm_episodes
# 3,059, world_model 496) + 1,121 asserted gate-test literals:
# 1 hit, and that hit IS the leaking row -> 0 real-prose FPs on a 15-case
# hostile battery (release notes, changelogs, migration tables, dated prose,
# multi-year prose). The bare `>=3 dates` form was REJECTED on measurement
# (5/15 control FPs); adding the no-period condition alone still left 2/15;
# only the distinct-year condition removed them.
_DATE_STRIP_STOPWORDS = frozenset((
    "the", "and", "then", "or", "for", "with", "from", "vs", "at", "in",
    "of", "to", "a", "an", "on", "by", "is", "was", "were", "be", "as",
    "but", "so", "that", "this", "these", "those", "der", "die", "das",
    "und", "oder", "von", "mit", "im", "am", "den", "dem", "ein", "eine",
    "auf", "zu", "des", "le", "la", "el", "y", "et", "e",
))
_DATE_STRIP_PAIR_RE = _re.compile(
    r"\b([A-Za-z]{2,})\s+((?:19|20)\d\d-\d\d-\d\d)")
_DATE_STRIP_ISO_RE = _re.compile(
    r"(?:19|20)\d\d-\d\d-\d\d")


def _is_date_stamp_listing_strip(text):
    """True when `text` is a bare date-stamped listing strip (class 131)."""
    window = (text or "")[:220]
    if not window or "." in window:
        return False
    words = [m.group(1).lower() for m in _DATE_STRIP_PAIR_RE.finditer(window)]
    content = [w for w in words if w not in _DATE_STRIP_STOPWORDS]
    if len(content) < 3:
        return False
    return len({d[:4] for d in _DATE_STRIP_ISO_RE.findall(window)}) >= 3





# A news PHOTO-CREDIT strip welded to the byline + dateline (class 132,
# 22.09.26). Live: the technews cycle STORED, verbatim from
# online_buffer.jsonl,
#   "D3sign/STOCK PHOTO/Getty Images By Mason Leib April 29, 2026,
#    5:39 PM A software company founder wen..."
# - an article's image-credit run + byline + dateline + clock, 82 chars, so
# the >=90 "long prose" trust did NOT apply; the digits and the clock fed
# the technical-signal gate and no existing helper matched.
#
# Keyed on THREE independent parts that only a credit strip co-locates: an
# image-credit marker ("stock photo", "getty images", "ap photo", ...),
# a `By First [Last]` byline, a `<Month D, YYYY>` dateline AND a clock.
# Measured 22.09.26 over 20,845 rows (online_buffer, buffer_junk, kta_log,
# longterm_episodes, world_model): 1 hit and that hit IS the leaking row
# -> 0 real-prose FPs on a 7-case hostile battery (prose citing a credit,
# a caption, a named author, a wire credit with a clock, a byline with a
# date). Requiring the credit marker is what keeps `By Jane Doe September
# 3, 2026, 8:00 AM` learnable -- a byline alone is ordinary prose.
_CREDIT_BYLINE_MARKERS = (
    "stock photo", "getty images", "ap photo", "afp/getty", "reuters/",
    "photo by", "photograph by", "/afp", "/epa", "zuma press",
    "associated press",
)
_CREDIT_BYLINE_RE = _re.compile(
    r"\bBy\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2}")
_CREDIT_DATELINE_RE = _re.compile(
    r"\b[A-Z][a-z]{2,8}\s+\d{1,2},\s+(?:19|20)\d\d\b")
_CREDIT_CLOCK_RE = _re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", _re.IGNORECASE)


def _is_credit_byline_run(text):
    """True when `text` is a photo-credit strip + byline + dateline (132)."""
    low = (text or "").lower()
    if not low:
        return False
    if not any(m in low for m in _CREDIT_BYLINE_MARKERS):
        return False
    t = text or ""
    return bool(_CREDIT_BYLINE_RE.search(t)
                and _CREDIT_DATELINE_RE.search(t)
                and _CREDIT_CLOCK_RE.search(t))


# A paper/arXiv LISTING submitter run (class 135, 22.09.26). Live: the security
# cycle STORED, verbatim from online_buffer.jsonl,
#   "VLMs to Robotic Control . 9 authors 1 Submitted by Williams07 9 One to
#    More, More to One: Category-Aware Iterative Expert Training for Software
#    Engineering Agents Logics-MLLM 2 Submitted by paulsmith0217 4 Why Do Video
#    Diffusion Models Violate Physics?"
# - an arXiv new-listing page: each row is a title, an author count, a submitter
# ordinal and a submitter HANDLE. Not knowledge, and the page itself is an index.
#
# The discriminator is the WELD `<N> authors <N> Submitted by`, which is what the
# extractor produces when the listing's row separators are lost. Prose never
# emits it: a real sentence says "9 authors and was submitted by ..." (the word
# `authors` is NOT immediately followed by a bare digit) or "Authors 9 submitted
# by reviewers ..." (no `authors <N>` weld). Measured 22.09.26 over 14,515
# pair-rows (online_buffer, buffer_junk, kta_log, longterm_episodes, world_model,
# improvements, sft_openamer, archives): 2 hits and BOTH are the leaking row
# -> 0 FPs on a 5-case hostile battery, 0 gate-test literals.
_ARXIV_SUBMITTER_WELD_RE = _re.compile(
    r"\b\d+\s+authors?\s+\d+\s*submitted\s+by\b", _re.I)


def _is_arxiv_submitter_run(text):
    """True when `text` is an arXiv listing row's submitter weld (class 135)."""
    return bool(_ARXIV_SUBMITTER_WELD_RE.search(text or ""))


# An aggregator card's date + read-time badge welded to the article TITLE
# (class 136, 22.09.26). Live: the technews cycle STORED
#   "Sep 13, 2026 Read AI Agents 9 min OpenAI Agents API: Managed Infrastructure
#    for AI Agents OpenAI launched the Agents API in public beta, ..."
# - a blog aggregator's card header (date stamp, category label, read-time badge)
# welded onto the article's own title and lede. 184 chars, so the >=90 "long
# prose" trust applied; the digits fed the technical-signal gate and no existing
# helper matched (`_is_readtime_card_widget` keys on the DOUBLED unit
# `min min read`, which this renderer does not emit).
#
# Two independent parts are required: a `<Month D, YYYY> Read <TitleCase label>
# <N> min` badge run AND a TitleCase word immediately after it (the article
# title). The continuation test is the discriminator -- it is the same
# structural idea class 52 uses, and it is what keeps a sentence that merely
# QUOTES such a badge learnable ("... Read AI Agents 9 min is the card badge").
# Measured 22.09.26 over 14,515 pair-rows: 16 hits, ALL the leaking row (2 in
# the buffer, 13 audit echoes, 1 kta echo) -> 0 FPs on a 4-case hostile battery,
# 0 gate-test literals.
_AGG_MONTH_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
_AGG_LABEL_RE = r"[A-Z][A-Za-z&/]*(?:\s+[A-Z][A-Za-z&/]*){0,3}"
_AGGREGATOR_CARD_HEADER_RE = _re.compile(
    r"\b" + _AGG_MONTH_RE + r"\s+\d{1,2},\s*\d{4}\s+Read\s+"
    + _AGG_LABEL_RE + r"\s+\d{1,3}\s*min\s+(?=[A-Z])")


def _is_aggregator_card_header_weld(text):
    """True when an aggregator card header is welded onto the article (136)."""
    return bool(_AGGREGATOR_CARD_HEADER_RE.search(text or ""))

# class 141 (live 22.09.26): an aggregator CARD AFFORDANCE RAIL welded to the
# card's own title and lede:
#   "GAIA - Open-source framework ... Apr 13, 2026 - galaxyLogic - View Original
#    [star] Save TL;DR Highlight AMD has released GAIA, ..."
# The rail is the source's own UI furniture (open-original link, bookmark
# toggle, TL;DR/Highlight affordances), not knowledge. 246 chars WITH digits ->
# the >=90 "long prose" trust AND the technical-signal gate both fired, and no
# existing marker matched: `_AGGREGATOR_AFFORDANCE_MIN_RE` keys on
# "read full article" / "try on X" + a "[dot] N min" read-time, which this
# renderer does not emit; `_AGGREGATOR_CARD_HEADER_RE` (136) needs a
# "Read <label> N min" badge.
#
# Discriminator: the affordance rail itself -- "View Original" ... a bookmark
# star ... "Save" ... "TL;DR" in ONE run. "View Original" ALONE and the star
# ALONE are ordinary UI words, so the CONJUNCTION is required (the AS rule:
# when a single part cannot be made unique, add the second structural
# co-occurrence). Measured 22.09.26 over online_buffer + buffer_junk + both junk
# archives + longterm_episodes + world_model + kta_log + internet_learn_log
# (22,073 texts): 1 hit and it IS the leak -> 0 FPs on a 9-case hostile battery.
_AGG_CARD_AFFORDANCE_RE = _re.compile(
    r"View\s+Original[\s\S]{0,40}?(?:\u2606|\u2b50|\u2605|\u22c6)\s*Save"
    r"[\s\S]{0,60}?TL;DR",
    _re.IGNORECASE)


def _is_aggregator_card_affordance_rail(text):
    """True for an aggregator card's affordance rail welded to the card (141)."""
    return bool(_AGG_CARD_AFFORDANCE_RE.search(text or ""))


# class 137 (live 22.09.26): a docs site's breadcrumb run welded to a
# REPEATED category+title prefix, stored as the answer:
#   "Home / AI Guides / 12 Best Open-Source AI Agent Frameworks (2026) 📖 Guide
#    12 Best Open-Source AI Agent Frameworks (2026) Compare 12 open-source AI
#    agent frameworks for production workflows, multi-agent systems, ..."
# The crumb run `Home / <section> / ` is followed by the card's own title
# prefix TWICE (once bare, once again after the card's label badge) -- a real
# sentence never restates its own opening four words. 252 chars WITH digits,
# so the >=90 "long prose" trust AND the technical-signal gate both fired and
# no existing helper matched.
# The breadcrumb ALONE was measured and REJECTED (4 hostile-control FPs: prose
# can legitimately start "Home / Docs / Getting started ..."), and a bare
# repeated-prefix test was rejected too. Only the weld of crumb run + repeated
# prefix is clean.
# Measured 22.09.26: 1 buffer hit and it IS the leak -> 0/8,275 buffer_junk,
# 0/3,059 longterm_episodes, 0/10 hostile prose counter-cases.
_BREADCRUMB_RE = _re.compile(
    r"^\s*Home\s*(?:/|\u203a|\u00bb|>)\s*[^\n]{1,80}?(?:/|\u203a|\u00bb|>)\s*([^\n]+)$")


def _is_breadcrumb_title_repeat(text):
    """True for a breadcrumb run welded to a repeated title prefix (137)."""
    t = text or ""
    if len(t) > 500:
        return False
    m = _BREADCRUMB_RE.match(t)
    if not m:
        return False
    seg = m.group(1).strip()
    words = seg.split()
    if len(words) < 6:
        return False
    prefix = " ".join(words[:4])
    return len(prefix) >= 15 and seg.count(prefix) >= 2




# --- a paper/arXiv AUTHOR LIST with affiliation superscripts (class 140, 22.09.26) ---
# Live: `cycle_g_security` STORED
#   "Sahar Abdelnabi* 1 , Benjamin Pannell* 1 , ..., and Javier Rando 3
#    (*: Core contributors)."
# twice in `online_buffer.jsonl`, and `buffer_junk` carries a second paper of the
# same shape ("Bochao Wu 1 , Bei Feng 1 , ..."). It is the author block of a paper
# landing page: pure page furniture, zero knowledge. It passed BOTH gates -- 251
# chars cleared the "long prose" trust and the affiliation digits fed the
# technical-signal gate. The existing arXiv helpers key on DIFFERENT halves:
# `_is_arxiv_abstract_chrome` needs page labels from `_ARXIV_CHROME_MARKERS`, and
# class 135 `_is_arxiv_submitter_run` needs the `<N> authors <N> Submitted by`
# submitter WELD -- a clean author block emits neither.
#
# Discriminator = the affiliation-superscript SEGMENT repeated. A comma-separated
# segment that is a person name (1-3 capitalised words, optional `*`, optional
# `and`) followed by an affiliation digit, repeated >= 5 times. A real sentence
# about papers does not list five such entries in a row (measured, see below),
# and the leading-word STRUCT guard keeps a run of structural units learnable:
# "Section 3, Figure 2, Table 1, Appendix 4, Note 5" must SURVIVE.
# Measured 22.09.26 over online_buffer + longterm_episodes + world_model + kta_log
# + outcome_analyses + structures + buffer_junk (11,738 rows): 2 distinct hit
# strings, BOTH the leak; 0 FPs on 15 human/structural controls; 0 gate-test
# literals.
_AUTHOR_AFFIL_SEG_RE = _re.compile(
    r"^\s*(?:and\s+)?(?:[A-Z][A-Za-z'\-]+\s+){0,3}[A-Z][A-Za-z'\-]+\*?\s+\d{1,2}\s*$"
)
_AUTHOR_AFFIL_STRUCT_WORDS = frozenset({
    "section", "figure", "fig", "table", "appendix", "reference", "ref", "note",
    "step", "part", "chapter", "listing", "rule", "line", "page", "item", "version",
    "phase", "class", "type", "model", "stage", "level", "task", "epoch", "layer",
    "block", "unit", "test", "example", "case", "option", "method", "mode", "group",
    "batch", "fold", "seed", "run", "index", "row", "column", "file", "path", "port",
    "host", "node", "core", "thread", "process", "point", "topic", "question",
    "article", "paper", "authors", "variant", "day", "week", "month", "quarter",
    "goal", "objective", "claim", "assumption", "risk", "finding", "conclusion",
    "requirement", "feature", "metric", "result", "experiment", "dataset", "benchmark",
})
_AUTHOR_AFFIL_MIN_SEGMENTS = 5


def _is_affiliation_author_list(text):
    """True when `text` is a paper AUTHOR LIST with affiliation superscripts (class 140).

    Requires BOTH: >= `_AUTHOR_AFFIL_MIN_SEGMENTS` name+digit segments AND no
    segment whose leading word is a structural label (`Section`, `Figure`,
    `Version`, ...). The struct guard is what keeps a run of structural units --
    real content -- learnable.
    """
    t = (text or "").strip()
    if not t or len(t) > 2000:
        return False
    hit = 0
    for seg in t.split(","):
        words = [w.strip("*").lower() for w in seg.strip().split()]
        if len(words) <= 2 and words and words[0] in _AUTHOR_AFFIL_STRUCT_WORDS:
            return False
        if _AUTHOR_AFFIL_SEG_RE.match(seg):
            hit += 1
    return hit >= _AUTHOR_AFFIL_MIN_SEGMENTS


# class 141 (live 22.09.26): a SERP title welded to its own snippet, where a
# NUMERAL phrase or a >=4-token run from the title recurs in the snippet.
#
# Three rows of the SAME family in the 260-row buffer tail (the cron's own
# rejection was on cycle_b_papers, so this was found the cheap way -- reading
# the buffer tail, not the printed line):
#   "Grok Pricing 2026: $10 Lite, $30 SuperGrok, $300 Heavy Grok now spans free
#    access, $10 Lite, $30 SuperGrok, $300 Heavy, and $30/user Business plans."
#   "Claude Opus 5 Review 2026: $5/$25, 61 Score, Real API Catch Claude Opus 5
#    launched at $5/$25 per million tokens with 1M context and 128K output."
#   "AI-Agent Tokens Surge 5% as Market Interest Returns May 3, 2026: Virtuals
#    Protocol surged 5% as AI-agent tokens roared back, ..."
#   "Retrieval and Language Systems NER Guide 2026: GLiNER, spaCy, Transformers,
#    and LLMs NER in 2026 means choosing between GLiNER, spaCy, Transformers,
#    and LLM extraction for latency, accuracy, and schema control."
# Each is a search-result title, a year stamp, then the snippet restating the
# title -- pure furniture, zero knowledge. All four cleared the >=90 "long
# prose" trust and the technical-signal gate (the year, the prices, the counts).
#
# The WELD is the year-colon inside the first 80 chars; it is the extractor's
# lost-newline SERP boundary. The DISCRIMINATOR is the RESTATEMENT. Neither half
# separates on its own (the AJ/AQ/AR law): the weld alone hits 6 prose controls
# ("In 2026: the API price is $5 ...", "vLLM 0.9 shipped in 2026: ..."), and a
# bare repeat hits 201 longterm_episodes + a real article body.
#
# THE CONTROL THAT DECIDES THE RULE is the China-chip row -- a real article the
# gate test asserts must survive byte-identical. It repeats a bare `417%` across
# DIFFERENT verbs, so it is NOT a pct-pair, and its repeated runs are 2-3 tokens,
# so no 4-token window repeats: it survives by construction, not by a word list.
#
# MEASURED 22.09.26 (read-only): 4 buffer hits and all 4 ARE the leak;
# 0 of 3,063 longterm_episodes; 0 of 1,274 gate-test string literals; 0 of 24
# packaged prose controls; 0 of 12 topic-matched hostile controls; and 18
# buffer_junk rows AGREE (already-rejected rows of the same family, incl. the
# `AutoGPT Review 2026:` / `AI Agent News Today — September 11, 2026 — ...`
# restatements -- a repeat-detector cannot see those, but the existing classes
# already gate them, so 18/18 agreement and 0 disagreement is the right reading).
_SERP_YEAR_WELD_RE = _re.compile(r"^[^\n]{0,80}?(?:19|20)\d\d:\s")
_SERP_PRICE_REPEAT_RE = _re.compile(
    r"(\$\s?[1-9][\d,]*(?:\.\d+)?(?:/\$?\s?\d[\d,]*)?)[^\n]{0,160}?\1")
_SERP_PCT_PAIR_RE = _re.compile(
    r"\b([A-Za-z]{4,})(?:s|d|ed|ing)?\s+(\d{1,3})\s*%[^\n]{0,160}?"
    r"\b\1(?:s|d|ed|ing)?\s+\2\s*%", _re.IGNORECASE)
_SERP_TOKEN_RE = _re.compile(r"[A-Za-z0-9$%./-]+")
_SERP_REPEAT_WINDOW = 4
_SERP_MAX_LEN = 500


def _serp_norm_token(tok):
    """Lowercase + naive plural stem so `LLMs` matches `LLM` (a backreference
    cannot: the NER row repeats the list with `LLMs` -> `LLM` drift)."""
    t = tok.lower().strip(".,;:")
    if len(t) > 4 and t.endswith("s"):
        t = t[:-1]
    return t


def _serp_repeated_run(text):
    """True when a run of `_SERP_REPEAT_WINDOW` normalised tokens repeats."""
    toks = [_serp_norm_token(w) for w in _SERP_TOKEN_RE.findall(text)]
    if len(toks) < 2 * _SERP_REPEAT_WINDOW:
        return False
    seen = {}
    for i in range(len(toks) - _SERP_REPEAT_WINDOW + 1):
        win = tuple(toks[i:i + _SERP_REPEAT_WINDOW])
        if win in seen and i - seen[win] >= _SERP_REPEAT_WINDOW:
            return True
        seen.setdefault(win, i)
    return False


def _is_serp_title_snippet_repeat(text):
    """True for a year-welded SERP title restated by its own snippet (class 141).

    Requires BOTH: a year-colon weld in the first 80 chars AND a restatement --
    an identical price token, an identical `<verb> <n> %` pair, or an identical
    run of `_SERP_REPEAT_WINDOW` normalised tokens.
    """
    t = (text or "").strip()
    if not t or len(t) > _SERP_MAX_LEN:
        return False
    if not _SERP_YEAR_WELD_RE.match(t):
        return False
    if _SERP_PRICE_REPEAT_RE.search(t):
        return True
    if _SERP_PCT_PAIR_RE.search(t):
        return True
    return _serp_repeated_run(t)

_ARTICLE_BYLINE_AFFORDANCE_RE = _re.compile(
    r"(?:\bKey Takeaways\b)"
    r"|(?:\bWritten by\s+[A-Z])"
    r"|(?:\bReply to this comment\b)"
    r"|(?:\bPosted by\s+[A-Z][\w.\-]*\s*\|)"
    r"|(?:\b\d{1,3} min read\b)"
    # class 145 (22.09.26): the publisher spells the read time out and welds it
    # to a following header label.  ANCHORED on that label, because the bare
    # weld is a topic-word trap -- "Reading time: 5 min per 1,000 tokens is the
    # budget we target, measured on May 3, 2026" is REAL prose and would be
    # truncated.  The lookahead is the TitleCase-continuation test of 135/136.
    r"|(?i:\breading\s+time\s*:?\s*\d{1,3}\s*min(?:ute)?s?)"
    r"[\s,:\u00b7|\u2013-]*"
    r"(?=Share\b|Last\s+updated\b|Updated\b|Published\b|Date\b|min\s+read\b|$)"
)
_ARTICLE_DATELINE_RE = _re.compile(
    r"(?:\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"\d{1,2},?\s+20\d\d\b)"
    r"|(?:\b20\d\d-\d{2}-\d{2}\b)"
    r"|(?:\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+20\d\d\b)"
    # class 145: an ORDINAL day suffix ("March 6th, 2025").  Live 22.09.26 the
    # byline predicate had no ordinal form, so an article header carrying
    # "Last updated on March 6th, 2025" was invisible to BOTH gates.
    r"|(?:\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th),?\s+20\d\d\b)"
)


def _is_article_byline_chrome(text):
    """True for an article's own byline/dateline header welded to its lede
    (class 142, 22.09.26).  Same predicate as
    `internet_learner._is_article_byline_chrome` -- both gates must refuse
    this class or the cycle spends itself on a write the writer drops.

    An article affordance (case-SENSITIVE: these are rendered page labels)
    AND a full dateline, both inside the first 200 chars.  The
    case-sensitive form is required: the case-insensitive variant fired on
    prose such as "published on April 29, 2026 and updated later that day".
    """
    head = (text or "")[:200]
    return (bool(_ARTICLE_BYLINE_AFFORDANCE_RE.search(head))
            and bool(_ARTICLE_DATELINE_RE.search(head)))


# class 149 (23.09.26) -- a site's nav-menu WELD run into a card title that is
# then repeated.  See _is_nav_weld_repeat_chrome.
_NAV_WELD_TOKENS = (
    "suche", "suchen", "rechner", "vergleichen", "vergleich", "blog", "home",
    "preise", "kategorien", "kontakt", "magazin", "ratgeber", "startseite",
    "anmelden", "registrieren", "mehr erfahren", "jetzt kaufen", "zum shop",
    "warenkorb", "impressum", "datenschutz", "nachrichten",
    "product categories", "get started", "sign in", "sign up", "log in", "login",
    "resources", "docs", "pricing", "careers", "about us", "privacy policy",
    "cookie policy", "terms of service", "newsletter", "book a demo",
)
_NAV_WELD_REPEAT_MIN = 40
_NAV_WELD_WINDOW = 60
_NAV_WELD_MIN_TOKENS = 3


def _nav_weld_run(text, window=_NAV_WELD_WINDOW):
    """Largest number of DISTINCT nav tokens inside one `window`-char slice."""
    low = (text or "").lower()
    pos = []
    for tok in _NAV_WELD_TOKENS:
        start = 0
        while True:
            i = low.find(tok, start)
            if i == -1:
                break
            pos.append((i, tok))
            start = i + 1
    pos.sort()
    best = 0
    for a in range(len(pos)):
        seen = set()
        for b in range(a, len(pos)):
            if pos[b][0] - pos[a][0] > window:
                break
            seen.add(pos[b][1])
        best = max(best, len(seen))
    return best


def _has_adjacent_exact_repeat(text, minlen=_NAV_WELD_REPEAT_MIN):
    """True when a >=`minlen` substring occurs TWICE overlapping (gap <= length).

    An exact repeat whose instances are far apart is normal (a session
    transcript restates a line; prose echoes a phrase) -- those measure 6
    `longterm_episodes` hits.  A repeat whose second instance STARTS inside the
    first is a widget drawing the same label twice at nearly the same offset,
    which no human-written text does.
    """
    t = text or ""
    if len(t) < minlen * 2:
        return False
    seen = {}
    for i in range(len(t) - minlen + 1):
        chunk = t[i:i + minlen]
        j = seen.get(chunk)
        if j is None:
            seen[chunk] = i
            continue
        k = minlen
        while i + k < len(t) and t[j + k] == t[i + k]:
            k += 1
        if i - j <= k:
            return True
    return False


def _is_nav_weld_repeat_chrome(text):
    """True for a nav-menu WELD run into a card title restated twice (class 149).

    Live 23.09.26: `cycle_c_github` stored

        Start Suche VPS-Rechner Vergleichen Blog Suchen EN DE Home Blog
        Haystack: The Open-Source AI Orchestration Framework for
        Production-Ready RAG Haystack: The Open-Source AI Orchestration
        Framework for Production-Ready RAG Jun 27, 2026 What Is Haystack?

    A German VPS-comparison site's menu strip (Suche / VPS-Rechner /
    Vergleichen / Blog / Suchen), the language switch, a "Home Blog" trail and
    then the card's own title drawn twice -- 252 chars WITH digits, so the
    `>=90` length trust and the technical-signal gate both fired and no
    existing marker matched.  class 82 (`_is_de_nav_weld_headline_chrome`) is
    the same FAMILY but misses this shape: its labels are welded to each other
    already, and it requires a TitleCase colon headline (this row's headline
    has a comma instead).

    The discriminator is the CONJUNCTION, and neither half survives alone:

      * nav tokens alone are one comma away from ordinary prose -- a German
        sentence listing `Suche, Blog, Preise, Kontakt, Impressum und
        Datenschutz` scores a run of 6, and 18 hostile controls scored 3-6
        (13 of them).
      * an exact repeat alone scores 88 of 3,064 `longterm_episodes` and 0
        gate-test literals; the ADJACENCY is what removes them (adjacent
        repeat alone: 6 episodes, all transcripts/tool dumps).

    Measured 23.09.26: 1 buffer hit and it IS the leak -> 0 FPs on 21 hostile
    prose controls (EN + DE, several LISTING the same labels), 0 of 3,064
    `longterm_episodes`, 0 gate-test literals, and 0 hits over 11,959 real
    prose chunks in 495 repo `.md`/`.txt` files.
    """
    if not text:
        return False
    return (_nav_weld_run(text) >= _NAV_WELD_MIN_TOKENS
            and _has_adjacent_exact_repeat(text))


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
    if _is_article_byline_chrome(s):
        return True
    if _is_gh_releases_row(s):
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
