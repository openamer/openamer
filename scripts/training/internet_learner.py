#!/usr/bin/env python3
"""Internet Learner — 24/7 active learning from the ENTIRE internet.

Rotates through 5 source types, every cycle:
  A. Tech news (HN, Reddit ML, dev.to)
  B. Papers (arxiv cs.AI/CL/LG new listings)
  C. GitHub trending (AI-agent space)
  D. Docs (vLLM, transformers, peft best practices)
  E. Competitors (Devin, OpenHands, AutoGPT changelogs)

Each cycle: collect -> filter relevance -> extract insight ->
train (mini-step) -> record (buffer + world model + log).

Runs as a daemon: python internet_learner.py --loop
Single run:       python internet_learner.py --once
"""
import os
import json, os, sys, time, random, datetime, urllib.request, urllib.parse, re
from pathlib import Path

def _training_dir():
    """Resolve the live training dir, tolerating a wrong/stale OPENAMER_HOME.

    The desktop/cron env can point OPENAMER_HOME at a throwaway test dir
    (e.g. %TEMP%/repo-ac-test2/home), which made every cycle crash with
    FileNotFoundError on .il_rotation. Prefer a *valid* env override, then
    the real install dir, then this file's own directory.
    """
    cands = []
    _env = os.environ.get("OPENAMER_HOME")
    if _env:
        cands.append(os.path.join(_env, "scripts", "training"))
    _home = Path.home()
    cands.append(str(_home / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training"))
    cands.append(str(Path(__file__).resolve().parent))
    for _c in cands:
        if os.path.isdir(_c):
            return _c
    return os.path.join(str(_home), "AppData", "Local", "openamer", "scripts", "training")


T = _training_dir()
BUFFER = os.path.join(T, "online_buffer.jsonl")
LOG = os.path.join(T, "internet_learn_log.jsonl")
ROT = os.path.join(T, ".il_rotation")
LIVE = "http://localhost:8081"
REPO = os.path.join(str(Path.home()), "openamer-repo")

def _rotate(queries):
    """Append a rotating qualifier so cycles don't saturate into duplicates.

    Learned 2026-09-14: of the last 200 store() attempts, 126 were rejected with
    reason 'duplicate'. Each cycle carries only 2-3 static queries, so every seed
    is fully learned within a day and the learner then idles forever, reporting
    'rejected, not trained' while burning cycles. The qualifier now advances PER
    INVOCATION via the .il_rotation counter (8 angles x day rotation), so each
    run probes a genuinely new angle; the exact-duplicate gate in buffer_store
    still guards repeats.
    """
    angles = [
        "",                        # plain seed (1 in 8 invocations)
        "limitations and failure modes",
        "benchmark comparison",
        "production case study",
        "best practices 2026",
        "common pitfalls",
        "alternative approaches",
        "lessons learned postmortem",
    ]
    try:
        day = datetime.date.today().timetuple().tm_yday
        # Advance the angle PER INVOCATION, not per day. A day-static angle made
        # every same-day repeat of a source issue an identical query, so after
        # the first success each later cycle hit the exact (u, a) duplicate gate
        # and idled (live 14.09.26: 18 'both gated' + ~30 duplicate rejects in
        # one day). The .il_rotation counter advances once per run, so
        # (day + n) % 8 probes a new angle each invocation.
        n = 0
        if os.path.exists(ROT):
            n = int(open(ROT, encoding="utf-8").read().strip() or 0)
        a = angles[(day + n) % len(angles)]
    except Exception:
        a = ""
    if not a:
        return list(queries)
    return [q if a in q else f"{q} {a}" for q in queries]


_SEEN_Q = os.path.join(T, ".il_seen_queries")


def _recent_queries(n=60):
    """Last N queries this learner already issued (novelty ledger)."""
    try:
        lines = [l.strip() for l in open(_SEEN_Q, encoding="utf-8") if l.strip()]
        return lines[-n:]
    except FileNotFoundError:
        return []


def _remember_query(q):
    """Append one query to the novelty ledger, trimmed to the last 800."""
    try:
        lines = [l.strip() for l in open(_SEEN_Q, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        lines = []
    lines.append(q.replace("\n", " ").strip())
    try:
        with open(_SEEN_Q, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-800:]) + "\n")
    except Exception:
        pass


def _fresh_headline(domain_kw, avoid):
    """One REAL, current HN headline matching the domain (Algolia, free, no key).

    Root cause fixed 2026-09-14: every cycle drew from a static seed list, so
    once all (seed x rotation-angle) pairs were learned the exact-duplicate gate
    rejected EVERY later cycle forever ("rejected, not trained (shallow + deep
    read both gated)" on all 5 sources for hours, buffer stuck at its 300 cap).
    A live headline is novel by construction, so the learner keeps learning.
    Widened 2026-09-15: only the top 12 points>10 hits were ever read, so once
    every one of them sat in the novelty ledger this path returned "" and the
    learner fell back to the (then-degenerate) LLM query -> saturated seeds ->
    4 consecutive live rejects. Now 4 pages x 2 thresholds = top ~96 hits.
    """
    q = urllib.parse.quote(domain_kw)
    avoidset = {a.lower() for a in avoid}
    _SELF = ("show hn:", "launch hn:", "ask hn:", "tell hn:")
    start = random.randint(0, 3)
    pages = (start, (start + 1) % 4, (start + 2) % 4, (start + 3) % 4)
    for filt in ("points%3E10", "points%3E3"):
        for page in pages:
            url = (f"https://hn.algolia.com/api/v1/search?query={q}&tags=story"
                   f"&numericFilters={filt}&hitsPerPage=12&page={page}")
            try:
                raw = urllib.request.urlopen(url, timeout=15).read()
            except Exception:
                continue
            # Prefer real articles/repos over Show/Launch/Ask HN posts: those
            # usually point at a product landing page whose copy is marketing
            # chrome, not knowledge (live 14.09.26: the security cycle pulled a
            # "Show HN: Pingu Unchained" product page and learned nothing but
            # ad copy - correctly junk-gated, but a wasted cycle).
            for h in json.loads(raw).get("hits", []):
                t = (h.get("title") or "").strip()
                if len(t) < 20 or t.lower() in avoidset or _is_junk(t):
                    continue
                if t.lower().startswith(_SELF):
                    continue
                return t
    # No article-grade headline on any page (only Show/Ask HN product pages,
    # which carry marketing chrome instead of knowledge - live 15.09.26: the
    # github cycle pulled "Show HN: A murder mystery game built on an
    # open-source gen-AI agent framework" and deep-read ad copy, so the cycle
    # was gated and wasted). Return "" so _novel_query falls through to the
    # LLM-synthesised query, which yields a narrow technical term instead.
    return ""


def _collapse_repeats(t):
    """Cut a degenerate phrase loop emitted by the local 2B model.

    Live 15.09.26: `mini-openamer` answered the synth prompt with
    "vLLM v2.12.0 kv_cache_prefill_prefetch" repeated ~20x -> 300+ chars, so
    the `8 <= len(q) <= 120` guard rejected it and _llm_novel_query returned ""
    on EVERY call -> the learner always fell back to saturated static seeds
    (4 consecutive "rejected, not trained" cycles). It also emits one glued
    token ("python:openai:chat-history-search-history-search-...", 79 chars) -
    short enough to pass the guard, and it lands on a stdlib-docs TOC.
    Only a phrase repeated >=3 times counts, so normal prose is never touched.
    """
    w = t.split()
    cut = len(w)
    for size in range(1, min(6, len(w) // 2) + 1):
        for i in range(len(w) - 2 * size + 1):
            if w[i:i + size] == w[i + size:i + 2 * size]:
                cut = min(cut, i + size)
    t = " ".join(w[:cut])
    if len(t.split()) <= 3:
        # Glued shape: look for a >=6-char period repeated 3 times at any
        # offset, and require 3 repetitions so "vLLM"/"arxiv" double letters
        # are never collapsed.
        done = False
        for size in range(6, len(t) // 3 + 1):
            if done:
                break
            for i in range(0, len(t) - 3 * size + 1):
                p1 = t[i:i + size]
                if p1 == t[i + size:i + 2 * size] == t[i + 2 * size:i + 3 * size]:
                    t = t[:i + size]
                    done = True
                    break
    return t.rstrip(" -_.,:")


def _llm_novel_query(domain_kw, avoid):
    """Ask the free local/cloud route for ONE narrow, fresh query."""
    prompt = (
        f"Propose ONE specific, narrow, technical SEARCH QUERY an autonomous AI agent "
        f"should study about: {domain_kw}. Prefer a concrete tool, library, version or "
        f"technique. Output ONLY the query (max 12 words, no quotes, no numbering)."
    )
    try:
        req = urllib.request.Request(LIVE + "/v1/chat/completions",
            data=json.dumps({"model": "mini-openamer", "max_tokens": 60,
                             "use_tools": False,
                             "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=120))
        q = r["choices"][0]["message"]["content"].strip().split("\n")[0]
        q = re.sub(r"^[\-\*\d\.\)\s\"'`]+", "", q).strip().strip("\"'`")
        q = _collapse_repeats(q)
        # Root cause F: a `module:attr` / `pkg:func` shape lands on a stdlib
        # docs table of contents where every candidate sentence is nav junk,
        # so the cycle is wasted. Return "" and let the widened HN pass win.
        if q.count(":") >= 2 or re.search(r"[\w.]+:[\w.]+:", q):
            return ""
        if 8 <= len(q) <= 120 and q.lower() not in {a.lower() for a in avoid}:
            return q
    except Exception:
        pass
    return ""


def _novel_query(domain_kw, seeds):
    """A genuinely fresh query per invocation — kills the duplicate wall.

    Order: real live headline -> LLM-synthesised -> rotating static seed. The
    exact-duplicate gate in buffer_store still guards true repeats.
    """
    avoid = _recent_queries()
    q = ""
    # domain_kw may be a list of keyword fallbacks: a narrow term can have ZERO
    # article-grade HN hits (live 15.09.2026: "quantization LLM inference
    # efficiency" -> 2 Algolia hits, both Show HN -> _fresh_headline "" on every
    # page, so cycle_h_efficiency fell through to the LLM/static-seed path and
    # was gated every cycle: 0/3 on 15.09.). Try each keyword before giving up.
    kws = domain_kw if isinstance(domain_kw, (list, tuple)) else [domain_kw]
    for _kw in kws:
        try:
            q = _fresh_headline(_kw, avoid)
        except Exception:
            q = ""
        if q:
            break
    if not q:
        q = _llm_novel_query(kws[0], avoid)
    if not q:
        q = random.choice(_rotate(seeds))
    _remember_query(q)
    return q


def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def store(user_text, insight, buffer=None):
    """Quality-gated write to the training buffer. True only on a real append.

    Two gates, in order:
      1. page chrome / boilerplate (`_is_junk`) — nav text, ads, login walls,
         marketing slogans.
      2. no technical signal (`_looks_like_content`) — a candidate with neither
         a number nor a technical noun/verb is page furniture, not knowledge.
         Live 13.09.26: the competitor cycle "learned" Polish classified-ad
         chrome ("Pomysły na rodzinne spotkania Dania na grilla ... Przepisy").
    Rejections are audited to buffer_junk.jsonl so the gate stays observable.
    """
    if not insight:
        return False
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import buffer_store
    buf = buffer or BUFFER
    # Normalise percent-escapes first: a search-result "title" that is really a
    # URL ("Which%20Programming%20Language%20used%20behind%20Microsoft%20Edge")
    # must be judged on its decoded words — the bare digits of %20 otherwise
    # satisfy the technical-signal gate and let the fragment through (live
    # 13.09.26, efficiency cycle).
    cleaned = _clean_insight(insight, 300)
    reason = ""
    if _is_junk(insight):
        reason = "junk"
    elif not cleaned:
        reason = "no-tech-signal"
    if reason:
        try:
            buffer_store._audit(user_text, insight, reason)
        except Exception:
            pass
        return False
    # 2026-09-22: ask the WRITER before writing. Measured on 600 audited junk
    # rows: 368 (61%) were SILENT DROPS — this module judged the text learnable,
    # buffer_store.is_junk() then refused it, and the cycle reported only the
    # generic "rejected, not trained". Auditing under its own reason makes the
    # disagreement visible (it was invisible for 8 days) and keeps the two
    # gates separable when one of them is over-strict.
    if _writer_gate_refuses(cleaned):
        try:
            buffer_store._audit(user_text, cleaned, "writer-gate")
        except Exception:
            pass
        return False
    rec = {"u": (user_text or "")[:3000], "a": (cleaned or "")[:4000]}
    try:
        if buffer_store._is_duplicate(rec, buf):
            buffer_store._audit(user_text, cleaned, "duplicate")
            return False
        buffer_store.append(user_text, cleaned, buffer=buf)
    except Exception as e:
        print(f"[internet-learn] buffer write failed: {e}", flush=True)
        return False
    # Success = the record is NOW present. Do NOT compare line counts: once the
    # buffer is at its cap, enforce_cap trims it back to MAX_BUF, so a real
    # append leaves the count unchanged (before == after) and the old
    # `after > before` test reported "rejected, not trained" on every cycle
    # while the buffer was actually rotating. Live 14.09.26: buffer pinned at
    # exactly 300 rows with all cycles logged as rejected.
    return buffer_store._is_duplicate(rec, buf)


def store_or_deep(user_text, query, insight):
    """Store a shallow (title-level) insight; if a gate rejects it, READ the
    page and store the substantive prose instead.

    Root cause fixed 2026-09-14: extract_insight() returns search-result titles,
    so repeating the same seed+angle inside one day produced an identical title
    and tripped the 'duplicate' gate — the learner idled at ~50% rejection
    (31 of the last 60 cycles) while burning ~7s each. deep_learn() fetches the
    page, whose prose differs cycle-to-cycle and clears both gates.
    Returns the stored text, or "" if both attempts were gated.
    """
    if store(user_text, insight):
        return insight
    deep = deep_learn(query) if query else ""
    if deep and deep != insight and store(user_text, deep):
        return deep
    # Second chance, wider net: the first deep pass reads k=2 pages, and a page
    # with no verb/tech-hint sentence leaves both gates unsatisfied, so the
    # whole cycle is wasted (live 15.09.26: cycle_e/cycle_g logged "rejected,
    # not trained" ~1 cycle in 3). k=6 fetches more candidates for the same
    # query before giving up.
    deep2 = deep_learn(query, k=6) if query else ""
    if deep2 and deep2 not in (insight, deep) and store(user_text, deep2):
        return deep2
    return ""


def add_to_buffer(user_text, assistant_text):
    """Back-compat alias for `store` (older call sites)."""
    return store(user_text, assistant_text)

def observe_world(cause, effect):
    """Write through the central world model (single source of truth)."""
    import world_model
    return world_model.observe(cause, effect)

# Boilerplate / nav text that is NOT knowledge (newsletter footers, cookie
# banners, paywall CTAs). Learned 2026-09-13: a technews cycle once "learned"
# the literal string "No spam, ever — we'll never share your email address".
# 2026-09-13 (second time): the GitHub cycle "learned" GitHub's anti-bot page
# — "You switched accounts on another tab or window." — because no pattern
# covered login walls. Every entry here must be a CONCRETE page-chrome phrase,
# never a bare word like "login"/"forbidden" (real content would die with it).
_JUNK_RE = re.compile(
    r"(unsubscribe|no spam|opt out|opt-out|cookie|privacy policy|terms of service|"
    r"sign up for|subscribe to our|all rights reserved|we'?ll never share|"
    r"click here|read more|accept all|newsletter|advertisement|"
    r"enable javascript|skip to content|manage your preferences|"
    # login walls / anti-bot / error pages (serve no learning signal)
    r"switched accounts on another tab|another tab or window|view all docs|"
    # GitHub releases-page chrome (live 15.09.26: cycle_f_multi_domain
    # stored "No results found View all tags openai-sdks released this"
    # — reject at extraction so the cycle retries instead of wasting it)
    r"view all tags|released this \d|"
    r"sign in to continue|log in to continue|you need to log in|"
    r"are you a robot|verify you are human|prove you'?re human|"
    r"captcha|access denied|403 forbidden|404 not found|page not found|"
    r"please enable cookies|too many requests|rate limit exceeded|"
    # nav chrome of wiki-style sites (live 13.09.26: the docs cycle returned the
    # German Wikipedia donation banner "Jetzt spenden Benutzerkonto erstellen
    # Anmelden Meine Werkzeuge" — the English-only patterns missed it).
    r"jetzt spenden|benutzerkonto erstellen|meine werkzeuge|meine beitr|"
    r"letzte ?nderungen|zuf?llige seite|community-portal|"
    r"\ber wikipedia|datenschutz|impressum|"
    # bare marketing slogans carry no learning signal
    r"developers, agents, and code come together|build software better, together|"
    # German ad/classified chrome (live 13.09.26: a competitor cycle "learned"
    # "Unsere Werbepartner Einkaufen Ferienwohnungen Freizeit und Reise …")
    r"werbepartner|ferienwohnungen|kleinanzeigen|anzeigenmarkt|"
    # a landing-page marketing-slogan clause (class 139, 22.09.26: the
    # multi-domain cycle stored "Operator prepping for month-end Pull 50+
    # invoices from 15+ portals in under 5 minutes \u2014 no mental load." --
    # the digits fed the technical-signal gate and the row is a product
    # CLAIM, not knowledge. Measured over the live corpora + 30 hostile
    # controls, incl. "Reconciliation happens in under 5 minutes -- no
    # mental gymnastics required.": 0 real-prose rows carry it.)
    r"no mental load|"
    # German bank referral/promo chrome (live 16.09.26: cycle_c_github
    # stored "Auch die neue Kundin oder der neue Kunde erhält eine Prämie
    # von 300 €, was eine Gesamtprämie von 600 € ergibt!" — a referral BONUS
    # offer, zero technical prose; the euro amounts fed the technical-signal
    # gate and the 100 chars cleared the >=25 floor. Concrete promo phrases
    # only: measured over the live 5080-row corpus, 1 hit (the leaking row),
    # 0 real-prose rows.)
    r"pr\u00e4mie von|gesamtpr\u00e4mie|erh\u00e4lt eine pr\u00e4mie|"
    r"neukundenpr\u00e4mie|kunden-werben|empfehlungspr\u00e4mie|"    r"przepisy|kuchnia|inspiracje|porady|dania na grilla|"
    # HuggingFace docs sidebar nav (live 14.09.26: the docs cycle stored the
    # verbatim product-label list "Inference Providers Kernels LeRobot
    # Leaderboards … Tokenizers Trackio Transformers". At 200 chars it cleared
    # the >=90 length trust, so it needs its own narrow signature.)
    r"inference providers kernels|lerobot leaderboards|reachy mini|"
    r"openenv optimum|tokenizers trackio|"
    # Doc-site product nav welded to a vendor SDK label (live 22.09.26:
    # cycle_d_docs stored "API, Infinite Possibilities Reference Qualcomm
    # Cloud AI home Qualcomm Cloud AI SDK download Qualcomm Cloud AI API
    # reference User Guide OCP Microscaling Formats (MX) Specification
    # efficient-transformers Welcome to Efficient-Transformers
    # Documentation!" — 250 chars of pure sidebar/product nav, zero prose,
    # and BOTH gates passed it. Two WELDED markers, measured over the live
    # 245-row buffer: 1 hit each and that hit IS the leaking row -> 0
    # real-prose rows carry them. Both bare forms were MEASURED-AND-REJECTED:
    # "api reference" and "infinite possibilities" each hit 1 hostile control
    # ("The API reference for the agent runtime lists every tool and its
    # parameters.", "Infinite possibilities in agent design come from
    # composing narrow tools.") -- hence the two-token weld.)
    r"cloud ai api reference|infinite possibilities reference|"
    r"efficient-transformers welcome to efficient-transformers"
    # Leaked LLM meta/instruction text (live 14.09.26: the multi-domain cycle
    # stored the model's OWN extraction template verbatim — "Identify the Core
    # Task: Extract ONE technical insight ... No preamble before the insight.
    # Target audience: autonomous AI agent." — 200+ chars of prompt scaffolding
    # that cleared the >=90 "long prose" trust. Each phrase below is a concrete
    # template fragment, never a bare word.)
    r"identify the core task|extract one technical insight|"
    r"no preamble before|target audience: autonomous|"
    r"format it as a single sentence|self-critique: reply with|"
    # Second prompt-echo shape (live 15.09.26: cycle_d_docs distilled
    # `" exactly). - Must be a single technical insight extracted from the
    # given text. - **Text Source:** The provided text is a lengthy table of
    # con…` from a docs page — the model echoed its own template.)
    r"must be a single technical insight|\*\*text source|"
    # GitHub org/user-page chrome (live 15.09.26: cycle_b_papers stored
    # "Updated Dec 19, 2013 People This organization has no public
    # members." as a research insight)
    r"has no public members|"
    # GitHub repo-page header (title-cased in the page itself)
    r"Code Issues Pull requests|Open more actions menu|"
    # Corporate first-person boilerplate (live 14.09.26: the efficiency cycle
    # stored "Bit-TLS-Verschlüsselung Für die sichere Datenübertragung nutzen
    # wir 256-Bit-TLS-…" — site chrome, but the bare digit 256 satisfied the
    # technical-signal gate). The giveaway is the vendor's first-person-plural
    # voice plus website/SSL-compliance vocabulary; each phrase is specific
    # enough never to appear in a genuine technical insight.
    r"nutzen wir|verwenden wir|wir nutzen|wir verwenden|wir setzen ein|"
    r"unsere website|unsere webseite|auf dieser website|ssl-?zertifikat|"
    r"f\u00fcr die sichere daten\u00fcbertragung|for secure data transmission|"
    # GitHub page chrome (live 13.09.26: the github cycle stored "Dismiss alert
    # {{ message }} Explore Topics Trending Collections Events GitHub Sponsors #
    # autonomous-agents Star Here are 5,319 public repositories matching this
    # topic." — nav text whose digits and '#' topic satisfied the technical gate.)
    r"dismiss alert|explore topics trending collections|"
    r"github sponsors|public repositories matching this topic|"
    r"star here are|events github sponsors|"
    # FR Wikipedia TOC + section-toggle chrome (live 13.09.26: the competitor
    # cycle stored "Début 1 Conjecture liée à la forme de la Terre ... 5
    # Géographie Afficher / masquer la sous-section" — same class as the DE
    # jargon above, different language.)
    r"afficher\s*/\s*masquer|masquer la sous-section|"
    r"wikip\u00e9dia|modifier le code|sous-section|"
    r"here'?s a thinking process|"
    # German + course-marketplace ad CTAs (live 14.09.26: the multi-domain cycle
    # stored "Legal-Tech-Software - Kanzleimanagement mit Advolux … Jetzt kostenlos
    # testen. … AI Law Course … Find the right instructor for you. Choose from ma"
    # — CTA copy whose >=90 length cleared the prose trust. Concrete phrases only.)
    r"jetzt kostenlos testen|kostenlos testen|kostenlos registrieren|"
    r"find the right instructor|right instructor for you|"
    r"choose from [\d,]+ (?:online )?courses|"
    # Blog pagination + newsletter footer chrome (live 15.09.26: the papers
    # cycle stored "Onboarding Code Comprehension ... 1 2 3 4 5 6 7 8 9 10 11
    # Next Stay Updated Get the latest insights on software development ...
    # delivered to your inbox." -- the pagination digits satisfied the tech
    # gate and the footer CTA cleared the >=90 length trust. Concrete
    # phrases only; the pagination rule needs 6+ run-together short numbers
    # immediately followed by "Next", which real English prose never has.)
    r"delivered to your inbox|stay updated|get the latest insights|"
    r"subscribe to our newsletter|"
    r"jetzt angebot sichern|jetzt kaufen|jetzt bestellen|"
    r"(?:\b\d{1,3} ){6,}\s*next\b)|"
    # GitHub pricing/plan chrome (live 16.09.26: cycle_c_github stored
    # "BILLED ANNUALLY $119 /yr Select First 7 days FREE then $119 billed
    # annually, cancel anytime Gaia+ $24 ." -- pure price-table copy, zero
    # prose. Measured over the live 300-row buffer: 1 hit, 0 real-prose rows).
    r"billed annually|min read article|"
    # AI-chat UI chrome (live 16.09.26: cycle_g_security stored the chat
    # feature list "Agent mode Let Chat calculate, ... Voice Chat
    # Standard AI Chat can make mistakes.").
    r"let chat calculate|hand off real-world tasks|"
    r"ai chat can make mistakes|products considered|"
    # review-site header (live 16.09.26: cycle_f_multi_domain stored
    # "Home Product categories AI Agents ... Last updated Sep 15, 2026
    # Based on 4,014 reviews". A run-together review count is page meta.)
    r"based on [\d,]{4,} reviews|"
    # MediaWiki wikitext markup (same live row as the writer-gate entry).
    # NOTE: every fragment in this alternation must end with `|` — the whole
    # pattern is ONE implicitly-joined literal, so a missing pipe silently
    # welds two phrases together (16.09.26: a missing pipe turned the wikitext
    # rule into `"wt":"award-winning`, killing it until the suite caught it).
    r'"wt":"|'
    # Consumer-app marketing voice
    # "Things - To-Do List App for Mac & iOS - Cultured Code — Things is the
    # award-winning personal task ..." — an App-Store blurb for a to-do app,
    # buffered as competitor intelligence. The giveaway is the product-blurb
    # voice, never a topic word; each phrase is specific enough to be safe.
    # Measured over the live 300-row buffer: 0 hits, 0 real-prose rows.)
    r"award-winning (?:personal )?(?:task|to-?do|app)|"
    r"to-?do list app|organize your (?:day|life|tasks)|"
    r"helps you (?:organize|track|manage) your|"
    r"available on the app store|google play|\bapp store\b|"
    # Contact-page chrome (live 16.09.26: a cycle stored the literal phone line
    # "You can also reach us at +1 (123) 456-7890." — the digits satisfied the
    # technical-signal gate.)
    # NOTE: the LAST fragment must NOT end with `|` — a trailing pipe closes the
    # alternation with an empty branch, which matches every string and turns the
    # whole junk gate into "reject everything" (16.09.26, caught by il_delta
    # showing 300/300 rejected).
    r"reach us at|contact us at|call us at|"
    # Social-share widget chrome (live 16.09.26: cycle_a_technews learned the
    # row "March 17, 2026 (UPDATED Sep 8, 2026) ... Reddit Post Share Threads
    # Support my work." — pure share/subscribe widget, zero prose; the digits
    # of the timestamps satisfied the technical-signal gate and the row cleared
    # the >=90 "long prose" trust). Reject at extraction so the cycle retries
    # with the wider k instead of spending itself on a write the writer drops.
    # Keyed on the widget VOICE, never on a topic or a clock: "support my work"
    # is a donation CTA, and the detached counter requires the number itself to
    # be missing ("K followers"), so prose that merely mentions a follower
    # count ("Mistral has 30k followers on GitHub") is untouched.
    # NOTE: the LAST fragment must NOT end with `|` (an empty alternative would
    # match every string and turn the gate into "reject everything").
    r"watch live key points|support my work|share threads support|"
    # 16.09.26 measured leaks: HN listing chrome (cycle_f), Wikipedia
    # infobox label chain (cycle_g) — same measured markers as
    # buffer_store._NAV_CHROME (keep both files in sync).
    r"auf duden online|visit\ website|points\ by\ |points\ ·|comments\ ·|connector\ type|\ months\ ago\ \(|every\ frontierbeat\ desk|min\ read\ explore|"
    # HN/Metafilter comment-listing pagination chain (live 16.09.26:
    # cycle_c_github stored "LegionWithin on March 10, 2025 | prev | next
    # [–] best acronym of 2025 (so far) emiliog07 on March 9, 2025 |
    # prev [–] What a name." — a listing LABEL CHAIN, zero prose;
    # the dates fed the technical-signal gate and the length cleared the
    # >=90 long-prose trust).
    # Keyed on PIPE+NAV ADJACENCY, never on the words alone: prose writes
    # "the prev and next control"/"the previous checkpoint" (no pipe), and
    # a markdown row `| key | value |` carries no nav token — both
    # measured as counter-cases over the live buffer (0 hits, 0 regressions).
    # PITFALL: must NOT start the regex with `|` — the preceding fragment
    # already ends with `|`, and `||` is an EMPTY alternative that matches
    # every string (gate becomes reject-everything).
    r"\|\s*prev\s*\|\s*next\b|\|\s*next\s*\|\s*prev\b|\|\s*prev\s*\[\u2013\]|\|\s*next\s*\[\u2013\]|"
    # German Wikipedia list/glossary page chrome (live 16.09.26:
    # cycle_g_security stored "Liste aller Wikipedia-Artikel, deren Titel
    # Agent enthaelt Wiktionary: Agent - Bedeutungserklaerungen ... Dies ist
    # eine Begriffsklaerungsseite ..." -- 210 chars cleared the >=90 length
    # trust and its digits fed the technical-signal gate. Same markers as
    # buffer_store._NAV_CHROME; keep both files in sync. Measured over the
    # live buffer: 1 hit and that hit IS the leaking row -> 0 prose FPs.)
    r"liste aller wikipedia-artikel|deren titel|wiktionary\s*:|the user pasted|identify\s+the\s+goal\s*:|the\s+insight\s+should\s+be|user\s+asks\s*:|find\s+the\s+structural\s+connection\s+between\s+these\s+two\s+situations\s*:|(?:what\s+is\s+the\s+)?shared\s+underlying\s+pattern\s*\??\s*$|\*\*\s*survey\s+the\s+papers\s*:\*\*|most\s+relevant/valuable\s+technical\s+insight|explore\s+microsoft\s+products\s+and\s+services\s+and\s+support\s+for\s+your\s+home\s+or\s+business|"
    # A sports-fixture list (live 16.09.26, cycle_c_github): a scoreline
    # followed by a pipe and a fixture date. Same rule as
    # buffer_store._FIXTURE_LIST_RE; keep both files in sync. Measured over
    # the live buffer: 1 hit and that hit IS the leaking row -> 0 prose FPs.
    r"\b\w+\s+vs\.?\s+\w+[^|]{0,25}\d{1,2}\s*[-\u2013]\s*\d{1,2}\s*\|\s*"
    r"\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|closed nifty|the economic times benchmarks|add free huggingface demo|"
    # GitHub releases-page ROW + slide-deck nav trio (classes 123/124,
    # live 21.09.26) -- same markers as buffer_store._NAV_CHROME; keep both
    # files in sync. Measured: 1 buffer hit each and that hit IS the leaking
    # row -> 0 prose FPs over 3,059 longterm_episodes + 7,442 buffer_junk
    # rows. Prose that merely discusses releases or slides stays learnable
    # (counter-cases measured).
    r"released\s+[^\n]{0,60}?\(github releases\)|show original\s+previous slide|"
    # NOTE: every fragment above ends with `|` -- the whole alternation is ONE
    # implicitly-joined literal, so a missing pipe welds two rules together and
    # an EMPTY branch matches every string (both hit on 16.09.26).
    # NOTE: the fragment below is the LAST one -- it keeps the closing comma
    # that the following re.IGNORECASE) closes.
    r"^\W*[kKmM]\s+followers\b",
    re.IGNORECASE)

# Percent-escapes mean the "insight" is a URL fragment, not prose. Their digits
# would otherwise satisfy the technical-signal gate (live 13.09.26).
_URL_ESC_RE = re.compile(r"%(?:[0-9A-Fa-f]{2})")

# Leaked task scaffolding openers (live 16.09.26: the "structural connection"
# cycles buffered their OWN instructions verbatim — "Situation 2: These",
# "Need find shared underlying pattern.", "Task: Identify the shared underlying
# pattern connecting these two.", "Goal: Find the structural connection between
# them (i.", "They want me to identify the shared underlying pattern").
#
# Anchored at the START of the text and imperatively voiced. This is essential:
# the same cycles produce genuine declarative ANSWERS ("The shared underlying
# pattern IS a closed-loop feedback system that …") which MUST stay learnable.
# A bare phrase match would swallow both — the instruction voice is the only
# reliable discriminator, so the rule keys on the opener, never the topic.
_INSTRUCTION_OPENER_RE = re.compile(
    r"^\s*\**\s*(?:"
    r"need\b|task\s*:|goal\s*:|ask\s*:|interpret\b|"
    # SIXTH echo shape (live 16.09.26): the model parroted the cross_connect
    # prompt as `Question: Find structural connection between these two
    # situations. What` -- article dropped, period instead of colon, so the
    # fragment/opener rules all missed it. Same anchored-question shape as
    # buffer_store._ECHO_QUESTION_RE (measured: 1 buffer hit = the leak,
    # 0 prose FPs, 0/11,342 corpus hits).
    r"question\s*:\s*(?:find|identify|what|how|why)\b|"
    r"find\s+(?:the\s+)?(?:structural\s+)?connection|"
    r"identify\s+(?:the\s+)?(?:shared\s+)?(?:underlying\s+)?pattern|"
    r"they\s+want\s+me\s+to|i\s+(?:need|should|will|must)\s+(?:to\s+)?(?:find|identify)|"
    r"what\s+(?:is\s+)?(?:the\s+)?(?:shared|structural)|"
    r"both\s+situations\s+describe|"
    r"situation\s*\d+\s*:"
    r")",
    re.IGNORECASE)


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
_PROMPT_ECHO_BULLET_RE = re.compile(
    r"(?:^|[\r\n])\s*[-*\u2022]\s+(?:Input\b|Output\b|I need to\b|"
    r"I must\b|I should\b|The task\b|Identify the\b|Steps?\b|"
    r"Constraints?\b|Format\b)",
    re.IGNORECASE)


def _is_prompt_echo_bullet_chain(text):
    """True when the text is the learner's own prompt echoed as bullets."""
    try:
        return len(_PROMPT_ECHO_BULLET_RE.findall(text)) >= 2
    except TypeError:
        return False


# A MID-SENTENCE search-snippet echo welded to the front of a real sentence
# (live 16.09.26, class 14). cycle_f_multi_domain stored, verbatim from the
# buffer row:
#   "at 11:44 am we asked four ai coding agents to In a recent experiment, four
#    AI coding agents were tasked with recreating the classic game Minesweeper,
#    revealing both the potential and limitations of ..."
# The extractor received Bing's snippet opening MID-SENTENCE ("... at 11:44 am
# we asked four AI coding agents to ...") and prepended it to the article's real
# first sentence. Both gates passed it: the clock digits fed the
# technical-signal gate (the alternation starts with \d+) and the length
# cleared the >=90 "long prose" trust.
#
# STRIP, not reject — the sentence BEHIND the fragment is the knowledge. The
# rule is structural and deliberately narrow: the text must START lowercase
# (a sentence starts with a capital, so ordinary prose is excluded by
# construction), carry a "<clock> am/pm" marker, then >=2 lowercase words,
# and the REAL sentence must follow with a capital. A genuine insight that
# merely mentions a time of day is untouched — measured over the live 4870-row
# corpus: 1 row touched (the leaking one), body a clean suffix, 4/4
# counter-cases unmodified.
_CLOCK_FRAGMENT_RE = re.compile(
    r"^(?:(?:at\s+)?\d{1,2}:\d{2}\s*(?:am|pm)\.?\s+)"
    r"(?:[a-z][\w'\u2019,\-]*\s+){2,}"
)


def _strip_clock_fragment(text):
    """Remove a leading mid-sentence snippet echo ("at 11:44 am we asked ... ").

    Returns `text` unchanged unless all three structural conditions hold:
    lowercase start, a clock-with-meridiem marker, and a capitalised real
    sentence after the fragment.
    """
    t = (text or "").lstrip()
    if not t or not t[0].islower():
        return text
    m = _CLOCK_FRAGMENT_RE.match(t)
    if not m:
        return text
    rest = t[m.end():]
    if not rest or not rest[0].isupper():
        return text
    return rest


def _strip_leading_clock_fragment(text):
    """Drop a leading ", <HH:MM AM/PM>" truncation artifact from a page excerpt.

    Live 19.09.26 (class 104): `cycle_c_github` stored
    `, 03:34 PM Anthropic, the AI company behind the Claude models, announced
    it will begin using user data, ...` -- an article header cut so that only
    the tail of the dateline survived (the comma is the remnant of
    `<Month> <day>, <year>, <HH:MM AM/PM>`). The prose after it is REAL
    knowledge, so STRIP the fragment and keep the paragraph -- never reject
    (same contract as `_strip_dateline_fragment` / `_strip_clock_fragment`,
    and the row-188 precedent).

    The leading comma + clock is the discriminator: a paragraph does not
    begin with `, 03:34 PM`. Measured on the live buffer: exactly 1 row
    changes (the leak), 0 of 3,059 `longterm_episodes`, 0 of 1,499 gate-test
    literals.
    """
    t = text or ""
    m = _LEADING_CLOCK_ARTIFACT_RE.match(t)
    if not m:
        return t
    rest = t[m.end():].strip()
    return rest if len(rest.split()) >= 5 else t




# a leading ", <HH:MM AM/PM>" truncation artifact (class 104, 19.09.26).
_LEADING_CLOCK_ARTIFACT_RE = re.compile(
    r"^\s*,\s*\d{1,2}:\d{2}\s*(?:AM|PM)\s+")

_PRINTABLE_WS = " \t\n" + chr(13)  # whitespace allowed in prose (not binary noise)


def _looks_binary(text):
    """True if `text` is raw bytes mis-decoded as text (PDF/compressed blob).

    Live 15.09.26: deep_learn() fetched an arxiv PDF and the cycle logged ~80
    chars of binary noise ("T\xefp\xef%...") as a trained insight — length and
    technical-signal gates both passed it because the noise happens to contain
    digits. Count non-printable / replacement characters and reject.
    """
    t = text or ""
    if len(t) < 20:
        return False
    bad = 0
    for c in t:
        o = ord(c)
        if o == 0xFFFD or (o < 32 and c not in _PRINTABLE_WS) or 0x7F <= o <= 0x9F:
            bad += 1
    return bad / len(t) > 0.08


# A clock time from a live ticker ("03:15", "1:12 PM"). Used only TOGETHER with
# a self-repeated phrase (see _is_ticker_loop) — a time code alone is normal
# prose and must never gate a row.
_TIME_CODE_RE = re.compile(r"\b\d{1,2}:\d{2}\b")

# arXiv ABSTRACT-PAGE chrome (live 16.09.26, class 10): cycle_b_papers stored
#   "Xiv-issued DOI via DataCite Submission history From: Shuming Ma
#    [ view email ] [v1] Tue, 27 Feb 2024 18:56:19 UTC (201 KB) Full-text
#    links: Access Paper: View a PDF of the paper titled The Era of 1-bit LLMs:
#    All Large Language Models are in 1."
# — 243 chars of pure page labels welded together, zero prose. Both gates
# passed it: the submission timestamp satisfied the technical-signal gate and
# the length cleared the >=90 "long prose" trust.
#
# Keyed on the LABEL CHAIN, never on the topic or a token such as "arXiv":
# a genuine insight about an arXiv paper ("BitNet stores weights in ternary
# form, so a 7B model fits in about 2 GB at int4.") must stay learnable.
# A single marker is NOT enough — real prose can legitimately mention a
# submission history or a preprint revision — so a row must carry TWO
# distinct label fragments to be judged chrome. Measured over the live
# 275-row buffer: catches the leaking row, 0 real-prose rows.
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
_ARXIV_PDF_LABEL_RE = re.compile(
    r"view\s+pdf\s+html\s*\(\s*experimental\s*\)",
    re.IGNORECASE)


def _is_arxiv_abstract_chrome(text):
    """True when `text` is an arXiv-style abstract page's label chain.

    Structural, not topical: two independent page labels from
    `_ARXIV_CHROME_MARKERS` must be present. One marker alone is left alone,
    so a real sentence that happens to mention a submission history or a
    preprint revision still reaches the buffer.
    """
    low = (text or "").lower()
    if not low:
        return False
    if _ARXIV_PDF_LABEL_RE.search(low):
        return True
    hits = sum(1 for m in _ARXIV_CHROME_MARKERS if m in low)
    return hits >= _ARXIV_CHROME_MIN_MARKERS


# Chinese Q&A / answer-portal chrome (live 16.09.26, class 12):
# cycle_h_efficiency stored, verbatim from the buffer row,
#   "CAD看图王 提供 嗨格式 2019-02-19 · 百度认证:苏州舜心科技有限公司 嗨格式 嗨格式是
#    苏州开心盒子软件有限公司旗下的独立品牌。 ... 已赞过 已踩过 你对这个回答的评价
#    是？ 评论 收起 读书小明白 高粉答主 2020-02-14 · 醉心答题，欢迎关注 知道答主
#    回答量： 12."
# — a Baidu-Zhidao answer-portal scrape with zero technical prose. Both gates
# passed it: the badge dates fed the technical-signal gate and the length cleared
# the >=90 "long prose" trust.
#
# Keyed on the portal's own LABEL CHAIN, never on the language: a row must carry
# TWO independent portal markers. Measured over the live 5013-row corpus (buffer
# + junk log, 16.09.26): 5 hits, every one of them chrome, 0 real-prose rows.
# The two genuine Chinese technical rows in the corpus (an LLM-agent survey
# summary and a quantization note) carry NO marker and stay learnable, and no
# row carries exactly one marker — so a language-agnostic "is CJK" rule, which
# would have eaten that real knowledge, is deliberately NOT used.
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


def _is_qa_portal_chrome(text):
    """True when `text` is a Chinese Q&A/answer-portal label chain.

    Structural, not topical: TWO independent portal markers must be present,
    so a genuine insight written in Chinese still reaches the buffer.
    """
    low = (text or "").lower()
    if not low:
        return False
    hits = sum(1 for m in _QA_PORTAL_CHROME_MARKERS if m in low)
    return hits >= _QA_PORTAL_CHROME_MIN_MARKERS


# German SaaS pricing/checkout chrome (live 16.09.26, class 13):
# cycle_c_github stored, verbatim from the buffer row,
#   "Bleib flexibel: Monatlich kündbar Lastschrift Kreditkarte Auf Rechnung
#    Jahrespaket 49,50 € / Jahr ~ 4,12 € pro Nutzer und Monat inkl."
# — a plan-comparison/checkout table with zero technical prose. Both gates
# passed it: the prices fed the technical-signal gate (the alternation starts
# with \d+, so "49" and "4" count) and the 133 chars cleared the >=90 "long
# prose" trust.
#
# Keyed on the checkout's own LABEL CHAIN, never on the topic or a bare price:
# TWO independent billing markers are required, so a genuine insight that
# merely mentions a price ("serving that model costs about 0,002 € per 1k
# tokens, annualised 12 € per agent") stays learnable. Measured over the live
# 4855-row corpus (buffer + junk log, 16.09.26): 6 marker hits, all in ONE row
# (the leaking row), 0 real-prose rows. The English twin of this class,
# "billed annually", already lives in buffer_store._NAV_CHROME.
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

    Structural, not topical: TWO independent billing markers must be present,
    so real prose that happens to cite a price still reaches the buffer.
    """
    low = (text or "").lower()
    if not low:
        return False
    hits = sum(1 for m in _DE_PRICING_CHROME_MARKERS if m in low)
    return hits >= _DE_PRICING_CHROME_MIN_MARKERS


# An AD-WALL / ad-blocker notice is page furniture, not knowledge (live
# 17.09.26, class 28). cycle_f_multi_domain stored
#   "Adblocker ausschalten Duden im Abo Nutzen Sie Duden online ohne Werbung
#    und Tracking auf allen Endgeräten für nur 2,99 €/Monat."
# Both gates passed it: the "2,99" fed the technical-signal gate (whose
# alternation starts with \d+) and the 104 chars cleared the >=90 "long prose"
# trust.
#
# Keyed on the NOTICE's own voice PLUS an offer signal inside one span, never
# on the topic: a notice is a CTA chain ("<blocker> ausschalten" -> "ohne
# Werbung" / "im Abo" / "für nur <n> €"). Prose ABOUT ad blockers or paywalls
# carries a technical verb and no offer span, so it stays learnable -- four
# counter-cases are asserted in the gate test.
_ADWALL_NOTICE_RE = re.compile(
    r"(?:adblocker|werbeblocker)\s*(?:bitte\s*)?(?:ausschalten|deaktivieren|entfernen)"
    r"[\s\S]{0,240}?"
    r"(?:ohne\s+werbung|werbefrei|im\s+abo|f[üu]r\s+nur\s+\d|\d+[,.]\d{2}\s*€)",
    re.IGNORECASE)


def _is_adwall_notice(text):
    """True when `text` is an ad-blocker-off / subscribe notice (page chrome).

    Structural, not topical: the notice VOICE must be followed by an offer
    signal inside the same 240-char span -- exactly the shape of a CTA chain
    and not of a sentence that reports a technical fact.
    """
    return bool(_ADWALL_NOTICE_RE.search(text or ""))


def _is_ticker_loop(text):
    """True when the text is a news-TICKER loop: a time code plus a phrase the
    text itself repeats.

    Live 16.09.26: cycle_a_technews learned the row
      "Trump praised Bezos for reversal 03:15 White House blasted Amazon for
       tariffs explainer, Trump praised Bezos for reversal (03:15) OpenAI backs
       measure that would require independent audits of AI models The AI bubble
       is leaking air, some economists say."
    A live news ticker re-renders the SAME headline with a fresh clock, so the
    extractor gets several unrelated headlines glued together and one phrase is
    present twice. Structure, not topic: a real technical insight does not
    repeat a >=15-char phrase of itself, and a bare "two clock times" rule was
    rejected as too broad (prose may legitimately mention two times). Measured
    over the live 270-row buffer: catches the leaking row, 0 real-prose rows.
    """
    t = text or ""
    if not _TIME_CODE_RE.search(t):
        return False
    words = t.split()
    n = len(words)
    for i in range(n):
        for j in range(i + 1, n):
            ph = " ".join(words[i:j])
            if len(ph) >= 15 and t.count(ph) >= 2:
                return True
    return False


# Diagram SOURCE (Mermaid / graphviz-DOT markup) is the rendering
# instruction for a picture, not prose. Live 16.09.26: cycle_e_competitors
# stored
#   'OKF Agent Memory resolves this dilemma with the Dual-Memory Agent
#    Architecture (DMAA) : flowchart TD subgraph PUSH["1.'
# -- an extractor lead-in sentence welded to the diagram body; 118 chars
# cleared the >=90 'long prose' trust, so neither length nor the
# technical-signal gate looked closer.
#
# Deliberately its OWN compiled pattern rather than another fragment of
# _JUNK_RE: that alternation is ONE implicitly-joined literal, and a
# missing/extra pipe welds two rules together or creates an empty branch
# that matches everything (both hit on 16.09.26). An insert here cannot
# break an existing rule by construction.
#
# Safe because BOTH a DSL keyword AND real markup punctuation (a labelled
# node or an edge arrow) must appear: prose that merely discusses a diagram
# carries the keyword but no node/arrow syntax. Measured over the live
# 297-row buffer + 1672 cycle results + 536 kta rows: 1 hit, and that hit
# IS the leaking row -> 0 prose false positives.
_DIAGRAM_DSL_RE = re.compile(
    r"\b(?:flowchart\s+(?:TD|TB|BT|RL|LR)|sequenceDiagram|classDiagram|"
    r"stateDiagram|erDiagram|subgraph\s+[A-Za-z_]\w*|"
    r"digraph\s+[A-Za-z_]\w*|graph\s+(?:TD|TB|BT|RL|LR)|"
    r"styling\s+node)\b",
    re.IGNORECASE)
# Markup PUNCTUATION: a labelled node (`ID["..."]`) or an edge arrow. A
# single `->` is ordinary ASCII prose and is deliberately NOT listed -- only
# the doubled/quadrupled diagram forms are.
_DIAGRAM_MARKUP_RE = re.compile(
    r"[A-Za-z_]\w*\s*\[\s*\x22|-->|---|==>|--x|--o|-.->")


def _is_diagram_markup(text):
    """True when `text` is diagram DSL source (Mermaid/graphviz), not prose.

    Requires a DSL keyword FOLLOWED WITHIN 400 CHARS by markup
    punctuation, so a sentence that merely names a diagram type stays
    learnable ("A flowchart TD block in the docs renders top-down, so the
    RAG chunker must split on the subgraph boundary …" -> untouched).
    """
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
    re.compile(r"view details", re.IGNORECASE),
    re.compile(r"file details", re.IGNORECASE),
    re.compile(r"details for the file", re.IGNORECASE),
    re.compile(
        r"uploaded\s+(?:[A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}|"
        r"\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"python\s+2\s+python\s+3", re.IGNORECASE),
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
_COURSE_CTA_RE = re.compile(
    r"\b(?:coming soon|enroll now|enrol now|register now|sign up today|"
    r"limited (?:seats|spots)|early bird|waitlist)\b",
    re.IGNORECASE)
_COURSE_BUNDLE_RE = re.compile(
    r"\b(?:certified|accredited)\b[^.]{0,60}" r"\b(?:expert|professional|"
    r"specialist|practitioner)\b|"
    r"\b(?:attack,\s*poison|poison\s*&\s*harden|curriculum\b|"
    r"what you'?ll learn)",
    re.IGNORECASE)


def _is_course_cta_chrome(text):
    """True when `text` is a course/certification landing-page CTA."""
    t = text or ""
    if len(t) > 500:
        return False
    return bool(_COURSE_CTA_RE.search(t) and _COURSE_BUNDLE_RE.search(t))


_ARCHIVE_LABEL_DATE_RE = re.compile(
    r"\b(?:insights|white-?paper|news|blog|articles?|posts?|press)\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+\d{1,2},?\s+\d{4}",
    re.IGNORECASE)


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


_ISSUE_ACTION_RE = re.compile(r"issue body actions", re.IGNORECASE)
_ISSUE_TEMPLATE_RE = re.compile(
    r"confirm this is an issue with|describe the bug|underlying openai api|"
    r"this is an issue with the \w+ library",
    re.IGNORECASE)


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


_PLAN_BULLET_RE = re.compile(
    r"^[\s\"'\u201c\u201d]*[-*\u2022]\s*(?:input text|goal|content|task|"
    r"text source|output format)\s*:",
    re.IGNORECASE | re.MULTILINE)


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


# Service-status / maintenance BANNER chrome (live 17.09.26, class 26):
# cycle_b_papers stored
#   "Login This service will be unavailable from Sep 18, 2026 19:00 PDT to
#    Sep 19, 2026 2:00 PDT due to maintenance."
# -- an arXiv status page announcement, zero insight. Both gates passed it:
# the timestamps fed the technical-signal gate (`_TECH_HINT_RE`'s alternation
# STARTS with \d+, so a date counts) and the length cleared the >=90
# "long prose" trust.
#
# TWO STRUCTURAL MARKERS, ANDed -- each alone is ordinary prose:
#   M1 a SCHEDULE: two absolute datetime stamps, each with a timezone,
#      joined by to / dash  -> a window was ANNOUNCED;
#   M2 the announcement VOICE (`this service`, `due to maintenance`,
#      `for maintenance`, or a leading standalone `Login` nav label).
#
# AND additionally the banner must be (almost) the WHOLE message:
# head <= 40 chars before, tail <= 40 chars after the announcement span.
# That last condition is what keeps prose ABOUT a downtime window alive --
# measured over 7,070 live corpus rows:
#   * the leak: caught (head=0, tail=18)
#   * 13 hand-written counter-cases: 0 false positives, incl.
#     "The vLLM maintenance window is Nov 3, 2026 22:00 UTC to Nov 4, 2026
#      02:00 UTC; requests are queued ..." (tail=68) and
#     "A row like service unavailable from Sep 18, 2026 19:00 PDT to
#      Sep 19, 2026 2:00 PDT due to maintenance is a banner, not an
#      insight ..." (head=35, tail=52).
# A measured-and-REJECTED candidate: M1 alone (`unavailable` + one dated
# timezone stamp) hit H1/H2/H4/H5 -- real prose about a downtime window.
_MAINT_STAMP = (r"[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}[ ,]+\d{1,2}:\d{2}\s*"
                r"(?:[APap][Mm]\s*)?[A-Z]{2,4}\b")
_MAINT_WINDOW_RE = re.compile(
    r"%s\s*(?:to|\u2013|\u2014|-)\s*%s" % (_MAINT_STAMP, _MAINT_STAMP),
    re.IGNORECASE)
_MAINT_VOICE_RE = re.compile(
    r"\bthis service\b|\bdue to maintenance\b|\bfor maintenance\b"
    r"|^\s*login\b",
    re.IGNORECASE)
_MAINT_EDGE = " \t\r\n.,;:!?-\u2013\u2014|/()[]\"'"


def _is_maintenance_banner(text, head_max=40, tail_max=40):
    """True when `text` is a service-status / maintenance BANNER.

    A banner ANNOUNCES a downtime window and is essentially the whole
    message. Prose that merely DESCRIBES such a window carries context
    before or after it, so the head/tail length is the discriminator.
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

# Release-note CHANGELOG bullet chain (live 17.09.26, class 27): cycle_d_docs
# stored
#   "FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled
#    disaggregated serving for GPT-OSS model [12/2025] Added support for
#    wav2vec2 Audio Model facebook/wav2vec2-base-960h [12/2025] Added
#    support for diffuser video generation model WAN 2."
# -- a rendered release-notes listing, zero prose. Both gates passed it: the
# version stamps fed the technical-signal gate and the length cleared the
# >=90 "long prose" trust.
#
# A listing is a CHAIN: three or more (version token, release verb) pairs,
# concatenated with spaces only. Prose that cites several versions always
# LINKS them with grammar, so the predicate additionally requires the row to
# carry NO prose connector (which/so/because/therefore/while/... or a
# participial linker). That is the same "a menu is a LABEL CHAIN, a sentence
# has grammar" discriminator used for the nav-strip family.
#
# Measured over the live corpora (300-row buffer + 1,719 kta/log/world rows)
# with 16 hand-written counter-cases:
#   * 6 of 7 realistic changelog shapes caught (the live leak among them);
#   * 0 genuine-buffer-prose false positives;
#   * 0/16 counter-cases hit -- incl. "The v0.9.1 release added streaming
#     output and v0.9.3 improved KV-cache reuse, so ..." and "PyTorch 2.4.0
#     added support ... while CUDA 12.4 improved ...";
#   * 0 hits across kta_log / internet_learn_log / world_model.
# A measured-and-accepted trade-off: a TWO-entry listing is NOT caught --
# two version+verb pairs are genuinely ambiguous against prose, so the rule
# stops at three. Documented, not accidental.
_CV_VERB = (r"(?:added|enabled|released|improved|fixed|introduced|updated|"
            r"removed|deprecated|supported|launched|migrated|bumped)\b")
_CV_VERTOK = (r"(?:\[\s*\d{1,2}/\d{4}\s*\]|\[\s*v?\d+(?:\.\d+){1,3}\s*\]|"
              r"\bv?\d+\.\d+(?:\.\d+){1,2}\b|\[\s*[a-z-]+\s+\d{4}\s*\])")
_CHANGELOG_CHAIN_RE = re.compile(
    r"(?:%s\s{0,3}(?:%s)[^,;.!?\n]{0,150}(?:\s|$)){3,}"
    % (_CV_VERTOK, _CV_VERB),
    re.IGNORECASE)
# prose links versions with grammar; a rendered listing never does
_CHANGELOG_CONN_RE = re.compile(
    r"\b(?:which|so|because|therefore|thus|hence|although|whereas|while)\b"
    r"|\bis exactly\b|\bmaking\b|\ballowing\b|\bgiving\b",
    re.IGNORECASE)


def _is_changelog_chain(text):
    """True when `text` is a rendered release-note / changelog bullet chain."""
    t = text or ""
    if not t or not _CHANGELOG_CHAIN_RE.search(t):
        return False
    return not _CHANGELOG_CONN_RE.search(t)


def _is_metric_row_fragment(text):
    r"""True when `text` is a METRIC-LABEL block with no sentence in it.

    Live 17.09.26 (class 43, `cycle_g_security`): the row
    `Attack Success Rate (360 runs — 60 payloads × 2 models × ~3 reps)
    Paradigm gemma4-e2b (local, Ollama) claude-haiku-4-5 ETP 73.` is a
    benchmark TABLE row -- column labels and counts welded together, zero
    prose. It cleared both gates through the familiar number-fed hole:
    `_TECH_HINT_RE`'s alternation starts with `\d+`, so the counts count as
    "technical signal", and the 126-char row cleared the >=90 trust.

    The discriminator is the same "a menu is a LABEL CHAIN, a sentence has
    grammar" rule used for the nav-strip family: a metric block carries a
    parenthesised ratio of counts (`(360 runs — 60 payloads`) or a
    tilde-approximated product (`× ~3 reps`) AND no finite verb anywhere.
    Both halves are required -- either half alone is ordinary English.

    Measured over the live 300-row buffer + 5,580 junk rows (5,880 total)
    with 11 hand-written counter-cases: 1 hit and it IS the leak -> 0
    real-prose FPs. The counter-cases that must stay learnable include the
    leak's OWN words inside a sentence:
      * "Attack success rate (360 runs — 60 payloads × 2 models) was
        measured on the local Ollama build and landed at 73% ..."  (has a verb)
      * "An attack success rate of 73% (360 runs — 60 payloads × 2 models
        × ~3 reps) is alarmingly high ..."                       (has a verb)
      * "A sweep over 12 seeds × 4 learning rates took 3 hours on one A100,
        and the best run reached 71.2% exact match."            (has a verb)
    The verb probe is deliberately WITHOUT `run`/`runs`: in the leak `runs` is
    a NOUN, and listing it would make the rule blind to its own target.

    Do NOT widen the ratio literal to a bare `×`: measured at 32 corpus hits
    including math derivations ("W_quantized × scale Where W is ...") and
    "3.6× faster", and a bare `\d+ \w+` pair matches ordinary prose.
    """
    t = text or ""
    if not (_METRIC_RATIO_RE.search(t) or _METRIC_XTILDE_RE.search(t)):
        return False
    return not _FINITE_VERB_RE.search(t)

# a parenthesised ratio of counts: "(360 runs — 60 payloads"
_METRIC_RATIO_RE = re.compile(
    "\\([^)]{0,90}?\\d+\\s+\\w+\\s*[\u2014\u2013-]\\s*\\d+\\s+\\w+")
# an approximated product of counts: "× ~3 reps"
_METRIC_XTILDE_RE = re.compile("\u00d7\\s*~\\s*\\d")
# any finite verb -> the row is a sentence, hence knowledge, not a label block
_FINITE_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|can|could|will|would|should|must|"
    r"shows?|showed|uses?|used|adds?|added|improves?|improved|reduces?|reduced|"
    r"requires?|required|means|meant|allows?|allowed|gives?|gave|makes?|made|"
    r"takes?|took|found|finds?|reports?|reported|achieves?|achieved|provides?|provided|"
    r"measures?|measured|compares?|compared|covers?|covered|enables?|enabled|"
    r"offers?|delivers?|drops?|raises?|falls?|grows?|stays?|keeps?|holds?|writes?|reads?|"
    r"landed|remains?|differs?|validates|prefers|matters|assigns|sits?|came|comes?|"
    r"stores?|needs?|reached|published|conspired|trust)\b",
    re.IGNORECASE)

def _is_sidebar_listing_chrome(text):
    """True when `text` is a blog-sidebar post-listing widget, not prose.

    Live 17.09.26 (class 29): `cycle_a_technews` stored
    `September 2, 2026 5 Views How to Spot AI Generated Images in 2026 (The Old
    Tricks Stopped Working) September 3, 2026 3 Views Our Picks Apple Added TV
    and 200 Games to Its Cheapest iCloud Plan.` -- a two-entry "recent posts"
    sidebar: date + view-counter + headline, twice. 189 chars and it carries
    digits, so both the `>=90` length trust and the technical-signal gate
    fired; no existing marker matched.

    Tight literal (the AH precedent: prefer the literal while only one row
    shape is live). Measured on the live 300-row buffer: 1 hit, and it IS the
    leak -> 0 real-prose FPs on an 8-sentence control corpus. Counter-only
    candidates were rejected: a bare `\\d+ views` matches real prose
    ("The survey gathered 500 views...", "In my view..."). Do NOT widen to
    `>=2 'N Views'` -- the literal is sufficient while this is the only shape.
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
    return bool(re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)\s*\|\s*\d{1,4}\b",
                          text or "", re.IGNORECASE))


# class 33/34 markers (live 17.09.26) -- see the two helpers below.
_REL_TIME_AGO_RE = re.compile(
    r"\d{1,3}\s+(?:minutes?|hours?|days?)\s+ago", re.IGNORECASE)
_NAV_WIDGET_LABEL_RE = re.compile(
    r"\bfor\s+you\b[\s\S]{0,40}\blatest\b[\s\S]{0,40}\btrending\b",
    re.IGNORECASE)


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
    return bool(re.search(
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
_FULL_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|"
    r"Nov|Dec)\.?\s+\d{1,2},\s+\d{4}\b")
_TITLE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'./-]*")


# class 36 markers (live 17.09.26) -- see _is_repo_tab_statbar_chrome.
_REPO_TAB_CHAIN_RE = re.compile(
    r"\bCode\s+Issues\s+Releases\b", re.IGNORECASE)
_REPO_STATBAR_RE = re.compile(
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
_PAGE_META_BLURB_RE = re.compile(
    r"^About\s+\S[\s\S]{0,200}?\bis the latest\b")


def _is_page_meta_blurb(text):
    """True when `text` is the page's own `About <Title> ... is the latest` blurb."""
    return bool(_PAGE_META_BLURB_RE.search(text or ""))


# A GitHub repo-LISTING row (live 17.09.26, class 32). `cycle_c_github` stored
# `Python 0 MIT 3,612 0 0 Updated Jun 13, 2025 ComfyUI Public Forked from
# Comfy-Org/ComfyUI The most powerful and modular stable diffusion GUI ...`
# -- a search-result listing row: language + counters + license + relative
# updated date + the repo's one-line description. 186 chars cleared the >=90
# "long prose" trust and the counters/license digits fed the technical-signal
# gate, so BOTH gates passed it.
#
# Keyed on the LISTING LABEL PAIR, not on the date or the counters alone:
# `Updated <Mon DD, YYYY>` is ordinary dates and `Public` is ordinary English
# ("Public health agencies ..."). Measured on the live corpora: 2 buffer hits
# (both ARE the leak), 0 of 3,056 longterm episodes, 0 of 323 test-asserted
# clean control literals. A bare `Forked from` was REJECTED -- it hits a real
# episode ("openclaw (386k GitHub stars) - what makes ... forked from ...").
_GH_LISTING_ROW_RE = re.compile(
    r"\bUpdated\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b[\s\S]{0,40}?"
    r"\bPublic\s+(?:Forked|Code|Archive|Mirror)\b")


def _is_gh_listing_row(text):
    """True when `text` is a GitHub repo-listing row (counters + Updated + label)."""
    return bool(_GH_LISTING_ROW_RE.search(text or ""))


# class 37 markers (live 17.09.26) -- see _is_hn_feed_listing_chrome.
_AGO_PIPE_COMMENTS_RE = re.compile(
    r"\b(?:minutes?|hours?|days?|weeks?|months?)\s+ago\s*\|\s*\d{1,5}\s*comments\b",
    re.IGNORECASE)


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
_HN_ITEM_CHROME_RE = re.compile(
    r"\bby\s+[\w.\-]+\s*\|\s*\d{1,5}\s+comments?\b[\s\S]{0,40}?\bon\s+Hacker\s+News\b"
    r"|\bNew ask Hacker News story\b",
    re.IGNORECASE)


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
    """True for an Hacker-News item row whose headline carries a `Show HN:` tag.

    Live 19.09.26 (class 105): `cycle_b_papers` stored

        CameronBanga 9 hours ago | 10 comments 175 Show HN: Cactus Needle 3:
        8-29MB automation models can match DeepSeek V4 Flash (cactuscompute.

    A single aggregator row (submitter handle + relative time + `| N comments`
    + points + `Show HN:` headline, cut off mid-hostname). It carries digits
    and real headline prose, so the `>=90` length trust and the
    technical-signal gate both fired. The existing HN gates miss it:
    `_is_hn_feed_listing_chrome` needs the unit REPEATED (>=2) and
    `_is_hn_item_chrome` needs the feed's own `by <handle>`/`on Hacker News`
    label or `New ask Hacker News story` -- this page ships the HN-native
    `Show HN:` tag instead.

    The discriminator is the CONJUNCTION of the feed unit and the site's own
    `Show HN:` label, with the points counter between them. Measured on the
    live buffer: 1 hit and it IS the leak -> 0 real-prose FPs (incl. the
    class-37 clean control `... | N comments 58 points Some headline about
    models.`, which has no `Show HN:`); 0/3,059 `longterm_episodes`.
    """
    return bool(_HN_SHOW_RUN_RE.search(text or ""))




# a HN item row: feed unit + points + the site's own `Show HN:` tag
# (class 105, 19.09.26).
_HN_SHOW_RUN_RE = re.compile(
    r"\b\w+\s+\d{1,2}\s+(?:minutes?|hours?|days?)\s+ago\s*\|\s*"
    r"\d{1,5}\s*comments?\b\s+\d{1,4}\s+\bShow\s+HN\s*:", re.IGNORECASE)


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
_BLOG_NAV_FEATURE_RE = re.compile(
    r"(?:(?:Software|People|Events|Resources|Cheatsheets|Videos|Blog|About|"
    r"Community|Support|Docs|Pricing|Careers|Contact|Login|Home)\b[\s,]*){8,}"
    r"[\s\S]{0,160}?\bFeatured\s+#", re.IGNORECASE)

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
_DATED_LISTING_RE = re.compile(
    _ROW_DASH + r"\b" + _LISTING_DATE + r"\b.{0,140}?" + _ROW_DASH
    + r"\b" + _LISTING_DATE + r"\b", re.I | re.S)
_READTIME_CARD_RE = re.compile(
    r"\b" + _MONTH_NAME + r"\b\s*\d{1,2},\s*\d{4}.{0,60}?"
    r"\b\d+\s+min\s+min\s+read\b", re.I | re.S)


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
_INFOBOX_FACTROW_TAIL_RE = re.compile(
    _RELAGO_TEMPLATE + r"[\s\S]{0,60}?" + _INFOBOX_LICENSE_LABEL, re.I)


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
_NAV_WIDGET_RE = re.compile(
    r"skip carousel|go to (?:previous|next) items|footer menu|back to top"
    r"|about scribd",
    re.IGNORECASE)


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
_DE_PORTAL_FACTBOX_RE = re.compile(
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
_PROMPT_ECHO_FRAGMENT_RE = re.compile(
    r"^\s*(?:The\s+)?shared underlying pattern"
    r"(?:[^\n]{0,30}?\bone sentence)?\s*\.?\s*$",
    re.IGNORECASE | re.MULTILINE)


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
_PROMPT_PLAN_ECHO_RE = re.compile(
    r"^\s*(?:KI-Performance-Optimierung|AI Performance Optimization"
    r"|Performance Optimization)\s*:[\s\S]{0,200}?\+[\s\S]{0,120}?[\r\n]+\s*\d{1,2}\.\s*$",
    re.IGNORECASE | re.MULTILINE)


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
_BYLINE_WEEKDAY_SHARE_RE = re.compile(
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
_HERO_CTA_STAR_RE = re.compile(
    r"\[\*\]\s+(?:With|Mit)\s+(?:over|\u00fcber)\s+[\d.,]+",
    re.IGNORECASE)

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
_HERO_ADOPTION_BRAG_RE = re.compile(
    r"With\s+over\s+[\d.,]+[kKmM]?\s+GitHub\s+[Ss]tars,\s*"
    r"[\d.,]+[kKmM]?\s+contributors,\s*and\s+over\s+[\d.,]+[kKmM]?\s+commits",
    re.IGNORECASE)


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
_BYLINE_PUBLISHED_RE = re.compile(
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
_PLATFORM_SELECTOR_RE = re.compile(
    r"(?:macOS|Windows|Linux)\s+(?:Apple\s+Silicon|Intel)\s*\([^)]*\)")
_PLATFORM_SEL_SUBREDDIT_RE = re.compile(
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



# class 45 markers (live 17.09.26) -- see _is_operator_spotlight_chain.
_OPERATOR_SPOTLIGHT_RE = re.compile(r"Operator\s+Spotlight", re.IGNORECASE)


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
_PREPRINT_CHAIN_RE = re.compile(
    r"([A-Z][A-Za-z0-9][\w\- ]{6,60}?)\s+(\d{1,2}/\d{1,2}/\d{4})\s+"
    r"([A-Z0-9][\w\-: ]{5,60})[.\s]*$")
_PREPRINT_TITLEWORD_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]{2,}\b")
_PREPRINT_LOWERWORD_RE = re.compile(r"\b[a-z]{4,}\b")


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
_BLOG_ABOUT_RE = re.compile(r"\bAbout\b")


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
_PRICING_HERO_RE = re.compile(r"%\s*OFF\s+base pricing", re.IGNORECASE)


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
_DOCS_CTA_AFTER_SERP_RE = re.compile(
    r"\u2026\s*;\s*Welcome to\s",
    re.IGNORECASE)


def _is_docs_cta_serp_run(text):
    """True when a SERP run ends on a docs site's `Welcome to …` page intro."""
    return bool(_DOCS_CTA_AFTER_SERP_RE.search(text or ""))


# class 55 markers (live 18.09.26) -- see _is_news_aggregator_listing_run.
# A press round-up: `| <Site> <Mon DD, YYYY> <Headline>` repeated (the site
# name is capitalised but not ALL-CAPS, the date is a full `Mon DD, YYYY`).
_PIPE_SITE_DATE_HEAD_RE = re.compile(
    r"\|\s*[A-Z][A-Za-z0-9]*\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
    r"\d{1,2},\s+\d{4}\s+[A-Z]")


def _is_news_aggregator_listing_run(text):
    """True when `text` is a run of press-roundup rows.

    Live 18.09.26 (class 55): `cycle_e_competitors` stored

        Protocol ACP | Techzine Oct 08, 2025 Zed Code Editor Adds Agent Protocol
        for Flexible AI Integration | WebProNews Aug 28, 2025 Google Integrates
        Gemini CLI into Zed Code Editor | SD Times Aug 28, 2025 Daily drive with
        Zed Code at the speed of thought.

    Each pipe segment is one syndication row: `| <Site> <Mon DD, YYYY>` followed
    by a Capitalised headline. It carries dates, so the `>=90` length trust and
    the technical-signal gate both fired and no existing marker matched -- it is
    not a `_is_serp_snippet` (no em-dash tail) and not a `_is_nav_list` (it has
    commas). The discriminator is REPETITION: one such segment is ordinary prose
    (`Coverage appeared | Techzine Oct 08, 2025 and again in the roundup.`), a
    run of >=2 is a listing. Measured: 1 buffer hit and it IS the leak -> 0
    real-prose FPs on a 14-sentence control corpus, 0 of the gate test file's
    literals, 0/3,058 `longterm_episodes`.
    """
    return len(_PIPE_SITE_DATE_HEAD_RE.findall(text or "")) >= 2


# class 56 markers (live 18.09.26) -- see _is_devto_card_tail.
# A syndicated dev.to card tail: the read-counter bar `N projects | dev.to`.
_DEVTO_CARD_TAIL_RE = re.compile(r"\b\d{1,4}\s+projects?\s*\|\s*dev\.?\s*$")


def _is_devto_card_tail(text):
    """True when `text` ends on a dev.to cross-post card counter bar.

    Live 18.09.26 (class 56): `cycle_e_competitors` stored

        Use `model: inherit` to Keep APC Agents Portable 2 projects | dev.

    A dev.to article card: the headline, then the site's own engagement bar
    `<N> projects | dev.` truncated at the site name. Only 66 chars, so the
    `>=90` length trust never applied -- a reminder the trust is not the only
    way chrome gets in. The anchor is the TAIL (`$`), because `2 projects |
    dev.to` mid-sentence is ordinary prose (`We shipped 2 projects | dev.to
    published the writeups afterwards.`). Measured: 1 buffer hit and it IS the
    leak -> 0 FPs on the control corpus, 0 test literals, 0/3,058 episodes.
    """
    return bool(_DEVTO_CARD_TAIL_RE.search(text or ""))


# class 57 markers (live 18.09.26) -- see _is_services_menu_chain.
# A studio menu strip: an ALL-CAPS `A & B` nav label ANDED with >=2
# TitleCase service labels.
_SERVICE_MENU_AND_RE = re.compile(r"\b[A-Z]{2,}\s*&\s*[A-Z]{2,}\b")
_SERVICE_LABEL_RE = re.compile(
    r"\b(?:RPA\s+Development|Computer\s+Vision|AI\s+Integration"
    r"|AI\s+Product\s+Engineering)\b")


def _is_services_menu_chain(text):
    """True when `text` is an agency/services page's menu strip.

    Live 18.09.26 (class 57): `cycle_a_technews` stored

        L Development RPA Development Computer Vision INTEGRATION & ENGINEERING
        AI Integration AI Product Engineering Youtube 9 Sep, 2026 The Rise of
        Enterprise Vertical AI Agents in 2026 The businesses that move now will
        be impossible to catch by end of 2026.

    A services site's own nav labels (an ALL-CAPS `INTEGRATION & ENGINEERING`
    separator plus the four service titles) welded to a blog card. 252 chars
    with a date, so the length trust and the technical-signal gate both fired.
    The discriminator is the nav bar itself: an ALL-CAPS `X & Y` label ANDED
    with >=2 service titles. Measured: 1 buffer hit and it IS the leak; 0 FPs
    on the control corpus (incl. `We combine AI & ML research with DevOps
    Engineering and Data Engineering practice.`), 0 test literals, 0 episodes.
    The bare ALL-CAPS-token count was REJECTED (>=4 gave 36 buffer hits, 384
    episodes and a control FP), and adding `Data Engineering`/`DevOps
    Engineering` to the label set re-introduced that FP -- keep the set to the
    four service titles the live page actually ships.
    """
    t = text or ""
    if not _SERVICE_MENU_AND_RE.search(t):
        return False
    return len(_SERVICE_LABEL_RE.findall(t)) >= 2


# class 58 markers (live 18.09.26) -- see _is_pagination_newsletter_widget.
_PAGINATION_NEWSLETTER_RE = re.compile(
    r"\bPrevious\s+Page\s+\d+\s+of\s+\d+\s+Next[\s\S]{0,200}?"
    r"\bNew articles by email\b", re.IGNORECASE)


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
_FULLSCREEN_TOGGLE_RE = re.compile(
    r"\bEnter fullscreen mode\s+Exit fullscreen mode\b", re.IGNORECASE)


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
_TAG_RUN_RE = re.compile(
    r"(?:#\s*[A-Za-z][A-Za-z0-9_-]{1,}\s+){2,}#\s*[A-Za-z][A-Za-z0-9_-]{1,}")
_TITLE_HEADLINE_RE = re.compile(r"(?:[A-Z][A-Za-z0-9'-]*\s+){4,}$")


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
_DATED_TAG_STRIP_RE = re.compile(r"\u00b7\s*#\s*")
_TAG_STRIP_TOKEN_RE = re.compile(
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
_UPDATED_DATE_RE = re.compile(r"\bUpdated\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b")
_SIZE_DOT_UPDATED_RE = re.compile(
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
_STAR_COUNTER_RE = re.compile(r"\u2605\s*\d+(?:\.\d+)?k\s*\+\d+")
_LANG_STAT_RE = re.compile(
    r"\b\d{1,3}\s+(?:Python|Go|TypeScript|JavaScript|Rust|C\+\+|Java|Jupyter|Shell)\b")
_REPO_SLUG_RE = re.compile(r"\b[A-Za-z0-9][\w.-]*/\s*[A-Za-z0-9][\w.-]*")


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
_JOURNAL_ISSUE_INDEX_RE = re.compile(
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
_TRUNCATED_SERP_TAIL_RE = re.compile(
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
_DOCS_FEATURE_LABEL_WELD_RE = re.compile(
    r"(?:" + _DOCS_FEATURE_LABELS + r")"
    r"[\s:]{1,4}"
    r"(?:" + _DOCS_FEATURE_LABELS + r")",
    re.IGNORECASE)


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
_LABEL_BULLET_RE = re.compile(r"[A-Z][A-Za-z]+(?: [A-Za-z]+){0,3} : ")


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
_TAG_COUNTER_PAIR_RE = re.compile(r"\b[\w.\-]{2,}\s*\(\s*[1-9]\s*\)")


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
_INSTITUTION_ABSTRACT_TAIL_RE = re.compile(
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
_TRENDING_CARD_HEADER_RE = re.compile(
    r"this\s+week\s+last\s+update\s*:\s*\d{1,3}\s+days?\s+ago\s+see\s+project\s+\d{1,3}",
    re.IGNORECASE)


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
_AGGREGATOR_ROW_RE = re.compile(
    r"\b\d{1,2}\s+(?:minutes?|hours?|days?)\s+ago\s*\|\s*\d{1,5}\s*comments?\b"
    r"[\s\S]{0,80}?\(\s*(?:19|20)\d\d\s*\)", re.IGNORECASE)


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
#
# The trailing handle is matched CASE-SENSITIVELY via the scoped inline flag
# `(?-i:...)`: the page emits handles capitalized, while the surrounding row
# is matched case-insensitively. Without the scope, `[A-Z]` under
# IGNORECASE re-admits lowercase prose (`... and then 193 runs:`).
_FEED_HANDLE_TOKEN_RE = r"[A-Za-z][\w.\-]{2,20}"
_FEED_HANDLE_TAIL_RE = r"(?-i:[A-Z])[\w.\-]{1,20}"
_FEED_HANDLE_UNIT_RE = re.compile(
    r"\b" + _FEED_HANDLE_TOKEN_RE + r"\s+\d{1,3}\s+"
    r"(?:minutes?|hours?|days?|weeks?)\s+ago\s*\|\s*\d{1,5}\s*comments?\b"
    r"[\s\S]{0,80}?\b\d{1,5}\s+" + _FEED_HANDLE_TAIL_RE + r"\s*:",
    re.IGNORECASE)


def _is_feed_handle_unit_row(text):
    """True when `text` is a single feed row: handle + time + comments + points + handle (143).

    Live 22.09.26 (class 143): `cycle_e_competitors` stored

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
_DE_CONSULT_PHRASE_RE = re.compile(
    r"\b(?:beraten|Beratung|Bestellung|Kaufberatung|Angebot|Hotline|Telefon)\b",
    re.IGNORECASE)
_DE_CONTACT_MARK_RE = re.compile(
    r"\b0\d{2,5}[\s/-]\d{3,8}\b"
    r"|\b\+49\b"
    r"|\bUhr\b"
    r"|\bHotline\b"
    r"|\bTelefon\b",
    re.IGNORECASE)


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
_PIPE_BYLINE_SHARES_RE = re.compile(
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
_PORTAL_COUNTER_BAR_RE = re.compile(
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
_CHANGELOG_PR_RE = re.compile(
    r"\(\s*#\d{3,}\s*\)\s*(?:Allow|Add|Fix|Support|Enable|Improve|Update|Remove|Bump|Refactor)\b")


_RELEASE_NOTE_EMOJI_RE = re.compile(
    r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\bv?\d+\.\d+(?:\.\d+){1,2}\b"
    r"|\[\s*\d{1,2}/\d{4}\s*\])"
    r"[^\n]{0,40}?"
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF]{1,3}\s*"
    r"(?:Released|Add(?:ed)?|Update[ds]?|Fixed|Removed|Improved|Launched"
    r"|Introduced|Deprecated|Enabled)\b",
    re.I,
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
_MIDTEXT_BYLINE_RE = re.compile(
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
_RELTIME_COUNTER_ROW_RE = re.compile(
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
_PROJECT_COUNT_NEWS_TAIL_RE = re.compile(
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
_COURSE_CTA_OPENER_RE = re.compile(
    r"^Start this course\s*(?:\u2192|->)", re.MULTILINE)


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
_CODE_LINENUM_RE = re.compile(r"\b\d(?:\s+\d){5,}\s+#\s+[A-Z][a-z]")


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
_SHARE_EXEC_SUMMARY_RE = re.compile(r"\bShare\s+Executive\s+Summary\b")


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
_RELATIVE_STAMP_NEWS_RUN_RE = re.compile(
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
_CITATION_COUNTER_RUN_RE = re.compile(
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
_BIO_CARD_DATELINE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\s*/\s*"
    r"\d{1,2}:\d{2}\s*(?:AM|PM)\b", re.IGNORECASE)
_BIO_CARD_LABEL_RE = re.compile(r"read\s+full\s+bio", re.IGNORECASE)


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
_DECORATIVE_ALT_TEXT_RE = re.compile(
    r"github\s+logo\s*\S{0,3}\s*decorative\s+\w+\s+pattern\s+background",
    re.IGNORECASE)


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
_TABLE_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|shows?|reached|measured|achieved|improves?|"
    r"gives?|uses?|makes?|allows?|enables?|trains?|runs?|keeps|compares?|lists?|"
    r"contains?|reports?|supports?|works?|means?|indicates?|found|became|remained|"
    r"needs?|does|do|did)\b", re.IGNORECASE)
_TABLE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'./@+-]*")


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
                 if re.search(r"(?<![A-Za-z0-9])" + re.escape(c) + r"(?![A-Za-z0-9])", t))
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
_REPO_STAT_FOOTER_RE = re.compile(
    r"\b\d[\d,]*\s+stars?\s+\d[\d,]*\s+forks?\b\s+"
    r"(?:Python|Go|TypeScript|JavaScript|Rust|C\+\+|Java|Jupyter(?:\s+Notebook)?|Shell|C)\s+"
    r"(?:Apache|MIT|GPL|BSD|MPL|LGPL)[\w.\-]*\s*\.\s*$")
_EXAMPLE_CUE_RE = re.compile(
    r"(?:e\.g\.|for example|such as|\blike\b|example:)\s*(?:[A-Za-z<>/|,.\-]+\s+){0,4}$",
    re.IGNORECASE)


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
_REPEAT_BADGE_GLYPH_RE = re.compile(r"\U0001f195")


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
_ADVISORY_ROW_RE = re.compile(
    r"(?:\s--\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+CVE-\d{4}-\d{4,}\b"
    r"|CVE-\d{4}-\d{4,}\s+(?:CRITICAL|HIGH|MEDIUM|LOW)\s+\d{1,2}(?:\.\d)?\.?\s*$)",
    re.IGNORECASE)

# A site-branded HEADLINE STUB stored as the answer: a short multi-TitleCase run,
# a colon, then `<year> Comparison of ...` and nothing else -- the SERP card's
# title line, never a sentence.
#   "Tech Frontline Low-Code AI Workflow Automation: 2026 Comparison of Zapier,
#    Make, and Tray."
# A bare `20xx Comparison of` is ordinary prose (3 control FPs); the brand run
# BEFORE the colon is the discriminator (0 FPs at 2-4 TitleCase tokens).
_SITE_HEADLINE_STUB_RE = re.compile(
    r"^\s*(?:[A-Z][\w&.\-]*\s+){2,4}[^:\r\n]{0,50}:\s*20\d\d\s+Comparison of\b",
    re.MULTILINE)

# An incident/vendor FACT BOX: the page's own label pair `Key Points` ...
# `Affected objects:` welded in one run.
#   "Key Points Event time: 2026-05-10, James Shore published an analysis article
#    -Affected objects: All developers and technical teams who use AI coding agents"
# 191 chars with digits -> both gates fired. `Affected objects` alone is ordinary
# prose (the vendor's own label is the anchor); the WELDED pair is the marker.
_FACT_BOX_LABEL_CHAIN_RE = re.compile(
    r"\bKey Points\b[\s\S]{0,200}\bAffected objects\s*:",
    re.IGNORECASE)


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
_DE_NAV_WELD_HEADLINE_RE = re.compile(
    r"(?i)\b" + _DE_NAV_WELD_LABELS + r"(?:\s+" + _DE_NAV_WELD_LABELS + r"){1,}"
    r"[\s\S]{0,80}?[A-ZÄÖÜ][^:\r\n]{8,80}:\s*\S")


def _is_de_nav_weld_headline_chrome(text):
    """True for a German nav-label weld stored as the answer (class 82).

    The page's menu lost its separators, so its own labels are welded together
    and run into the article headline. A `,`/`und`-joined list of the SAME
    labels is ordinary German prose and stays learnable.
    """
    return bool(_DE_NAV_WELD_HEADLINE_RE.search(text or ""))
_OWN_PLAN_PLUS_RUN_RE = re.compile(
    r"^\s*(?:Energy efficiency|KI-Performance-Optimierung|AI performance optimization"
    r"|Performance optimization|Efficiency|Continuous Learning Loop"
    r"|Kontinuierliche Lernschleife)[^:\r\n]{0,40}:"
    r"[^\r\n]{0,200}\+[^\r\n]{0,120}\+[^\r\n]{0,120}\+",
    re.IGNORECASE | re.MULTILINE)


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
_BARE_HEADING_FRAGMENT_RE = re.compile(
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
_GERMAN_GLOSSARY_ECHO_RE = re.compile(
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
_RELATED_SUBJECTS_SIDEBAR_RE = re.compile(
    r"explore related subjects[\s\S]{0,40}discover the latest",
    re.IGNORECASE)


def _is_related_subjects_sidebar(text):
    """True for a publisher's welded 'related content' sidebar label run."""
    return bool(_RELATED_SUBJECTS_SIDEBAR_RE.search(text or ""))


# class 102/103 markers (live 19.09.26) -- see the two helpers below.
# (a) class 102: a model-aggregator landing page stored as the answer. The
# affordance label `Read full article` / `Try on <Brand>` is welded to the
# site's own read-time label `\u00b7 N min`:
#   "Pricing GPT-5 Claude Gemini Vincony Read full article -> Try on Vincony
#    Ranking Jul 15, 2026 . 9 min Best AI Model Aggregators in 2026 (Ranked)
#    AI aggregators let you access GPT-5, Claude, Gemini and more from one
#    account."
# The read-time label ALONE was MEASURED AND REJECTED (1 gate-test literal:
# "General Compute . March 18, 2026 . 6 min read Quantization reduces ..."),
# and the topic phrase `AI aggregators let you access ... from one account`
# alone flagged my own topic-matched control. The welded affordance +
# read-time pair is the discriminator.
_AGGREGATOR_AFFORDANCE_MIN_RE = re.compile(
    r"(?:read\s+full\s+article|try\s+on\s+[A-Z][A-Za-z0-9]{2,})"
    r"[\s\S]{0,60}?\u00b7\s*\d{1,3}\s*min",
    re.IGNORECASE)


def _is_aggregator_affordance_min_run(text):
    """True for an aggregator's affordance label welded to its read time."""
    return bool(_AGGREGATOR_AFFORDANCE_MIN_RE.search(text or ""))


# (b) class 103: a tech-startup portal's OWN welded nav label run, stored with
# a headline and a byline credit:
#   "Home >> Artificial Intelligence Data Featured Startup Spotlight Startups
#    Tech Startup News Tech Startups Technology News Claude-powered AI coding
#    agent deletes production database and backups in 9 seconds Daniel Levi
#    Posted On April 28, 2026 0 3."
# The discriminator is the portal's own three-label nav run, not the topic:
# "Featured startup spotlight: our editors pick one young company every week.",
# "Tech startup news and funding rounds arrive in the newsletter every Tuesday."
# and "Home >> Artificial Intelligence is the breadcrumb the crawler stored as
# nav." are ordinary prose and stay learnable.
_STARTUP_PORTAL_NAV_RE = re.compile(
    r"featured\s+startup\s+spotlight[\s\S]{0,40}?tech\s+startup\s+news"
    r"[\s\S]{0,20}?tech\s+startups",
    re.IGNORECASE)


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
_SDK_FAMILY_WELD_RE = re.compile(
    r"open[- ]source\s+SDKs?\s*\(?\s*e\.g\.?[\s\S]{0,80}?youtubei",
    re.IGNORECASE)


def _is_platform_sdk_family_weld(text):
    """True for a platform's own client-SDK family welded to an SDKs opener."""
    return bool(_SDK_FAMILY_WELD_RE.search(text or ""))


def _is_startup_portal_nav_run(text):
    """True for a startup portal's welded nav label run."""
    return bool(_STARTUP_PORTAL_NAV_RE.search(text or ""))


# class 128 (live 21.09.26): an AI-agent INDEX landing page stored as the
# answer -- its affordance nav run welded to the site's own category labels:
#   "AI Agent Index Categories Find Agent + Submit Compare Alternatives Stacks
#    Advertise API Home / AI Coding Agents Best AI Coding Agents (2026): IDEs,
#    Terminals, Autonomous Updated September 2026 AI coding agents have moved
#    well beyond autocomplete."
# This is one of the TWO rows that made the KTA competitor-gap experiment
# report `signal NOT mappable` / map a false capability: the consumer reads the
# LAST lexicon-matching buffer row, so a nav row appended late poisons every
# subsequent run.
#
# REJECT, not strip: the only prose behind the run is a generic lede ("AI
# coding agents have moved well beyond autocomplete") with no capability token,
# so stripping would leave a contentless stub -- and the pair itself is the
# discriminator. TWO independent conjuncts in order, per the lazy-bridge trap:
# a single token like `compare alternatives` is ordinary English. Measured with
# probe_marker_candidates.py: 1 buffer hit (= this leak), 0 prose FPs,
# 0 longterm_episodes FPs, 0 gate-test-literal FPs.
_AGENT_INDEX_NAV_RE = re.compile(
    r"compare\s+alternatives[\s\S]{0,80}?advertise\s+api",
    re.IGNORECASE)


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
_BADGE_RIBBON_RE = re.compile(
    r"^[\s\S]{0,40}?#\s*\d{1,3}\b[\s\S]{0,60}?\bFeatured\s+Blog\b"
    r"[\s\S]{0,60}?\d{1,3}\s*%", re.IGNORECASE)


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
_SOURCE_TALLY_CTA_RE = re.compile(
    r"^\W*(?:curated|compiled|aggregated|sourced|collected|gathered)\s+"
    r"from\s+\d{1,4}\+?\s+sources?\b[^.]{0,160}?\band\s+more\.?\s*$",
    re.IGNORECASE)


def _is_source_tally_cta(text):
    """True when `text` is a widget's "Curated from N sources ... and more" CTA."""
    return bool(_SOURCE_TALLY_CTA_RE.search(text or ""))


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
_DATE_STRIP_PAIR_RE = re.compile(
    r"\b([A-Za-z]{2,})\s+((?:19|20)\d\d-\d\d-\d\d)")
_DATE_STRIP_ISO_RE = re.compile(
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
_CREDIT_BYLINE_RE = re.compile(
    r"\bBy\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2}")
_CREDIT_DATELINE_RE = re.compile(
    r"\b[A-Z][a-z]{2,8}\s+\d{1,2},\s+(?:19|20)\d\d\b")
_CREDIT_CLOCK_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", re.IGNORECASE)


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
_ARXIV_SUBMITTER_WELD_RE = re.compile(
    r"\b\d+\s+authors?\s+\d+\s*submitted\s+by\b", re.I)


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
_AGGREGATOR_CARD_HEADER_RE = re.compile(
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
_AGG_CARD_AFFORDANCE_RE = re.compile(
    r"View\s+Original[\s\S]{0,40}?(?:\u2606|\u2b50|\u2605|\u22c6)\s*Save"
    r"[\s\S]{0,60}?TL;DR",
    re.IGNORECASE)


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
_BREADCRUMB_RE = re.compile(
    r"^\s*Home\s*(?:/|\u203a|\u00bb|>)\s*[^\n]{1,80}?(?:/|\u203a|\u00bb|>)\s*([^\n]+)$")


# class 138 (live 22.09.26): an ALL-CAPS nav lockup welded to a Title-Case word.
# The lookahead requires the weld (`SOLACE AGENT MESH Take ...`); the rule body
# then requires the SAME name in Title Case elsewhere in the string.
_CAPS_LOCKUP_ANCHOR_RE = re.compile(
    r"\b[A-Z][A-Z0-9]{2,}(?:\s+[A-Z][A-Z0-9]{2,})+(?=\s+[A-Z][a-z])")


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
_AUTHOR_AFFIL_SEG_RE = re.compile(
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
_SERP_YEAR_WELD_RE = re.compile(r"^[^\n]{0,80}?(?:19|20)\d\d:\s")
_SERP_PRICE_REPEAT_RE = re.compile(
    r"(\$\s?[1-9][\d,]*(?:\.\d+)?(?:/\$?\s?\d[\d,]*)?)[^\n]{0,160}?\1")
_SERP_PCT_PAIR_RE = re.compile(
    r"\b([A-Za-z]{4,})(?:s|d|ed|ing)?\s+(\d{1,3})\s*%[^\n]{0,160}?"
    r"\b\1(?:s|d|ed|ing)?\s+\2\s*%", re.IGNORECASE)
_SERP_TOKEN_RE = re.compile(r"[A-Za-z0-9$%./-]+")
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

_ARTICLE_BYLINE_AFFORDANCE_RE = re.compile(
    r"(?:\bKey Takeaways\b)"
    r"|(?:\bWritten by\s+[A-Z])"
    r"|(?:\bReply to this comment\b)"
    r"|(?:\bPosted by\s+[A-Z][\w.\-]*\s*\|)"
    r"|(?:\b\d{1,3} min read\b)"
)
_ARTICLE_DATELINE_RE = re.compile(
    r"(?:\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"\d{1,2},?\s+20\d\d\b)"
    r"|(?:\b20\d\d-\d{2}-\d{2}\b)"
    r"|(?:\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+20\d\d\b)"
)


def _is_article_byline_chrome(text):
    """True for an article's own byline/dateline header welded to its lede
    (class 142).

    Live 22.09.26 (cycle_a_technews): the stored insight was
      "Written by Gus Mallett Published on April 29, 2026 Key Takeaways
       PocketOS, a company that designs software for car rental businesses,
       had its entire database mistakenly wiped by an AI agent ."
    -- a page byline + dateline + "Key Takeaways" affordance with the lede
    welded on.  4 of 276 online_buffer rows carried this class; the dates
    and the numeral in "11 min read" satisfy the technical-signal gate, so
    the VOICE/affordance is the only reliable discriminator.

    ``_is_byline_published_article_header`` (class 40) misses every shape
    here: it requires a LEADING byline, while these pages lead with a
    headline ("NVIDIA RTX PRO 5500 Blackwell: ... 11 min read Sep 15,
    2026"), with the date ("April 29, 2026 Key Takeaways ..."), or with a
    comment affordance ("OpenClaw Like Like Posted by kim Bruning |
    February 13, 2026, 5:05 pm Reply to this comment ps.").

    Discriminator = an article affordance AND a full dateline, BOTH inside
    the first 200 chars (header region), so prose that merely credits an
    author or cites a date mid-text is untouched.  The affordance regex is
    CASE-SENSITIVE on purpose: these are rendered page labels, and the
    case-insensitive form (measured 22.09.26) fired on two genuine prose
    controls -- "published on April 29, 2026 and updated later that day"
    and "Published on June 17, 2025 / 5:28 PM EDT and later revised".

    Keyed on the voice/affordance, never on the topic: a genuine
    "TLS 1.3 removes a handshake round trip" insight still passes
    (counter-case in the test corpus).  Measured 22.09.26: 5/5 known leaks
    (incl. "min read" / "Key Takeaways" / "Reply to this comment" shapes);
    0/5 natural prose controls; 0/1,301 test-corpus string literals that
    are not chrome; 0/3,064 longterm_episodes; 83/8,836 buffer_junk rows
    (already-refused chrome).
    """
    head = (text or "")[:200]
    return (bool(_ARTICLE_BYLINE_AFFORDANCE_RE.search(head))
            and bool(_ARTICLE_DATELINE_RE.search(head)))


def _is_junk(text):
    """True if `text` looks like boilerplate rather than actual content."""
    t = (text or "").strip()
    if len(t) < 25:
        return True
    if _looks_binary(t):
        return True
    # an article's own byline + dateline header welded to its lede (class 142, 22.09.26)
    if _is_article_byline_chrome(t):
        return True
    # a SERP run welded to a docs site's CTA (class 53, 18.09.26)
    if _is_docs_cta_serp_run(t):
        return True
    # a press-roundup listing run (class 55, 18.09.26)
    if _is_news_aggregator_listing_run(t):
        return True
    # a syndicated dev.to card tail (class 56, 18.09.26)
    if _is_devto_card_tail(t):
        return True
    # an agency services menu strip (class 57, 18.09.26)
    if _is_services_menu_chain(t):
        return True
    # a blog archive pagination widget + newsletter promo (class 58, 18.09.26)
    if _is_pagination_newsletter_widget(t):
        return True
    # a code-block FULLSCREEN toggle widget pair (class 59, 18.09.26)
    if _is_fullscreen_toggle_chrome(t):
        return True
    # a post headline welded to its hashtag run (class 60, 18.09.26)
    if _is_hashtag_run_after_headline(t):
        return True
    # a dated card headline + tag strip (class 61, 18.09.26)
    if _is_dated_tag_strip_chrome(t):
        return True
    # a model-hub listing row run (class 62, 18.09.26)
    if _is_model_listing_run_chrome(t):
        return True
    # a GitHub trending row (class 63, 18.09.26)
    if _is_trending_repo_row_chrome(t):
        return True
    # a journal volume/issue index run (class 67, 18.09.26)
    if _is_journal_issue_index_chrome(t):
        return True
    # a truncated site-suffixed SERP snippet (class 68, 18.09.26)
    if _is_truncated_serp_tail(t):
        return True
    # a docs feature-list with welded labels (class 69, 18.09.26)
    if _is_docs_feature_label_weld(t):
        return True
    # a colon-label bullet chain with lost newlines (class 70, 18.09.26)
    if _is_label_bullet_chain(t):
        return True
    # a repeated page badge glyph on list entries (class 71, 18.09.26)
    if _is_repeat_badge_glyph_run(t):
        return True
    # a repo page's stat footer welded onto its description (class 72, 19.09.26)
    if _is_repo_stat_footer_run(t):
        return True
    # a repo page's stat footer welded onto its description (class 72, 19.09.26)
    if _is_repo_stat_footer_run(t):
        return True
    # a benchmark table's header row (class 73, 19.09.26)
    if _is_table_header_value_run(t):
        return True
    # a page's welded decorative alt-text run (class 74, 19.09.26)
    if _is_decorative_alt_text_chrome(t):
        return True
    # a page's welded decorative alt-text run (class 75, 19.09.26)
    if _is_bio_page_furniture_pair(t):
        return True
    # a result page's tag-counter run (class 76, 19.09.26)
    if _is_tag_counter_run_chrome(t):
        return True
    # an affiliation welded to a truncated abstract ordinal (class 81, 19.09.26)
    if _is_institution_abstract_tail_chrome(t):
        return True
    # a trending card's welded header pair (class 82, 19.09.26)
    if _is_trending_card_header_pair(t):
        return True
    # an aggregator row welded to an arXiv year tail (class 83, 19.09.26)
    if _is_aggregator_row_year_tail(t):
        return True
    # a single feed row: handle + time + comments + points + handle (class 143, 22.09.26)
    if _is_feed_handle_unit_row(t):
        return True
    # German consultation/contact chrome (class 144, 22.09.26)
    if _is_de_consultation_contact_chrome(t):
        return True
    # a pipe-dateline byline welded to the site's Shares (class 84, 19.09.26)
    if _is_pipe_byline_shares_header(t):
        return True
    # a portal counter bar welded to a comparison headline (class 85, 19.09.26)
    if _is_portal_counter_bar_comparison(t):
        return True
    # a release-notes changelog bullet welded to its PR number (class 86, 19.09.26)
    if _is_release_notes_pr_bullet(t):
        return True
    if _is_release_note_emoji_bullet(t):
        return True
    # a headline run welded to a mid-text byline counter bar (class 87, 19.09.26)
    if _is_midtext_byline_counter_run(t):
        return True
    # a feed row: relative time + bare counters + headline (class 88, 19.09.26)
    if _is_relative_time_counter_row(t):
        return True
    # a newsroom cross-post counter bar at the tail (class 89, 19.09.26)
    if _is_project_count_news_tail(t):
        return True
    # a course landing-page arrow CTA opener (class 90, 19.09.26)
    if _is_course_cta_opener(t):
        return True
    # a code block whose line-number gutter was welded in (class 92, 19.09.26)
    if _is_code_linenum_run(t):
        return True
    # an article header's Share Executive Summary affordance (class 93, 19.09.26)
    if _is_share_exec_summary_header(t):
        return True
    # a reference-counter run repeated inside prose (class 94, 19.09.26)
    if _is_citation_counter_run(t):
        return True
    # a dated newsroom feed run: repeated relative stamps (class 95, 19.09.26)
    if _is_relative_stamp_news_run(t):
        return True
    # a publisher's welded related-content sidebar label run (class 99, 19.09.26)
    if _is_related_subjects_sidebar(t):
        return True
    # an aggregator's affordance label welded to its read time (class 102, 19.09.26)
    if _is_aggregator_affordance_min_run(t):
        return True
    # a startup portal's welded nav label run (class 103, 19.09.26)
    if _is_startup_portal_nav_run(t):
        return True
    # an AI-agent index landing page's affordance nav run (class 128, 21.09.26)
    if _is_agent_index_nav_run(t):
        return True
    # a blog badge ribbon welded to a headline stack (class 129, 21.09.26)
    if _is_badge_ribbon_chrome(t):
        return True
    # a platform's own client-SDK family named as the subject (class 126, 21.09.26)
    if _is_platform_sdk_family_weld(t):
        return True
    # a bare markdown heading stored as the whole answer (class 96, 19.09.26)
    if _is_bare_markdown_heading_fragment(t):
        return True
    # the agent's own German glossary line (class 97, 19.09.26)
    if _is_german_glossary_echo(t):
        return True
    # a widget's "Curated from N sources ... and more" CTA (class 130, 22.09.26)
    if _is_source_tally_cta(t):
        return True
    # a bare date-stamped listing strip (class 131, 22.09.26)
    if _is_date_stamp_listing_strip(t):
        return True
    # a news photo-credit strip + byline + dateline (class 132, 22.09.26)
    if _is_credit_byline_run(t):
        return True
# a paper/arXiv listing row's submitter weld (class 135, 22.09.26)
    if _is_arxiv_submitter_run(t):
        return True
# an aggregator card header welded to the article title (class 136, 22.09.26)
    if _is_aggregator_card_header_weld(t):
        return True
# an aggregator card's affordance rail welded to the card (class 141, 22.09.26)
    if _is_aggregator_card_affordance_rail(t):
        return True
    # a breadcrumb run welded to a repeated title prefix (class 137, 22.09.26)
    if _is_breadcrumb_title_repeat(t):
        return True
    # an ALL-CAPS nav lockup welded to prose + repeated in Title Case
    # (class 138, 22.09.26)
    # a paper/arXiv author list with affiliation superscripts (class 140, 22.09.26)
    if _is_affiliation_author_list(t):
        return True
    # a year-welded SERP title restated by its own snippet (class 141, 22.09.26)
    if _is_serp_title_snippet_repeat(t):
        return True
    # a nav-menu weld run into a card title restated twice (class 149, 23.09.26)
    if _is_nav_weld_repeat_chrome(t):
        return True
    if _is_caps_nav_lockup_weld(t):
        return True
    # a page-meta listing widget (same narrow rule as
    # buffer_store._is_sidebar_listing_chrome)
    if _is_sidebar_listing_chrome(t):
        return True
    # the page's own META blurb (same rule as buffer_store._is_page_meta_blurb)
    if _is_page_meta_blurb(t):
        return True
    # a GitHub repo-listing row (same rule as buffer_store._is_gh_listing_row)
    if _is_gh_listing_row(t):
        return True
    if _is_byline_counter_chrome(t):
        return True
    # a news-card stub / relative-time nav chain (class 33/34, 17.09.26)
    if _is_news_card_stub(t):
        return True
    if _is_relative_time_nav_chain(t):
        return True
    # a repeated aggregator feed listing (class 37, 17.09.26)
    if _is_hn_feed_listing_chrome(t):
        return True
    # a single aggregator item row with its feed tail (class 49, 18.09.26)
    if _is_hn_item_chrome(t):
        return True
    # a HN item row with the site's own `Show HN:` tag (class 105, 19.09.26)
    if _is_hn_show_run_chrome(t):
        return True
    # a site nav-label run welded to `Featured #` (class 106, 19.09.26)
    if _is_blog_nav_feature_run_chrome(t):
        return True
    # a German newsletter double-opt-in confirmation page (class 107, 20.09.26)
    if _is_de_double_optin_newsletter_chrome(t):
        return True
    # a job-board's repeated brand + slogan ad run (class 108, 20.09.26)
    if _is_jobboard_ad_run_chrome(t):
        return True
    # a dated aggregator listing run: headline welded to its date, twice (class 113, 20.09.26)
    if _is_dated_listing_run(t):
        return True
    # a review card's date + glued read-time badge (class 114, 20.09.26)
    if _is_readtime_card_widget(t):
        return True
    # a wiki infobox fact-row tail: relative-age template + license field (class 118, 20.09.26)
    if _is_infobox_factrow_tail(t):
        return True
    # a run of a document-hosting page's nav widgets (class 50, 18.09.26)
    if _is_nav_widget_run_chrome(t):
        return True
    # a broadcast-news byline + weekday dateline + Share header (class 51, 18.09.26)
    if _is_news_byline_share_header(t):
        return True
    # a landing-page hero CTA chain (class 38, 17.09.26)
    if _is_marketing_hero_cta_chrome(t):
        return True
    # a platform selector glued to a subreddit feed row (class 39, 17.09.26)
    if _is_platform_selector_listing_chrome(t):
        return True
    # an "Operator Spotlight" widget row stored twice (class 45, 17.09.26)
    if _is_operator_spotlight_chain(t):
        return True
    # a paper-title + slash-date + project-title header chain (class 46, 17.09.26)
    if _is_preprint_header_chain(t):
        return True
    # a personal-blog header nav run (class 47, 17.09.26)
    if _is_personal_blog_nav_chain(t):
        return True
    # a competitor pricing hero (class 48, 17.09.26)
    if _is_pricing_hero_chrome(t):
        return True
    # an article-header byline + `Published <dd Mon yy>` (class 40, 17.09.26)
    if _is_byline_published_article_header(t):
        return True
    # a date-stamped headline listing (class 35, 17.09.26)
    if _is_date_heading_listing(t):
        return True
    # a repo-page tab bar + language/size stat bar (class 36, 17.09.26)
    if _is_repo_tab_statbar_chrome(t):
        return True
    # the LLM's verdict ABOUT the page returned as an insight (class 44, 17.09.26)
    if _is_source_verdict_chrome(t):
        return True
    # a service-status / maintenance BANNER is page chrome, not knowledge
    # (live 17.09.26, class 26). Refuse at EXTRACTION time so the cycle
    # retries with the wider k instead of spending itself on a write the
    # writer gate drops. Same predicate as buffer_store._is_maintenance_banner.
    if _is_maintenance_banner(t):
        return True
    # a rendered release-note / changelog bullet chain
    if _is_changelog_chain(t):
        return True
    # a benchmark/metric TABLE row: column labels + counts, no sentence
    # (live 17.09.26, class 43). Same rule as
    # buffer_store._is_metric_row_fragment.
    if _is_metric_row_fragment(t):
        return True
    if _JUNK_RE.search(t):
        return True
    # a deep-read prompt echoed back as a bullet chain (17.09.26)
    if _is_prompt_echo_bullet_chain(t):
        return True
    # a German portal's own byline + summary label pair (18.09.26)
    if _is_de_portal_fact_box_chrome(t):
        return True
    # the learner's own task template echoed back (18.09.26)
    if _is_prompt_echo_fragment(t):
        return True
    # a generated plan echoed back as a truncated fragment (18.09.26)
    if _is_generated_plan_echo_fragment(t):
        return True
    if _is_generated_plan_echo_fragment(t):

        return True

    # a security-advisory listing row / headline stub / fact box / own plan

    # (classes 77-80, 19.09.26)

    if _is_advisory_row(t):

        return True

    if _is_site_headline_stub(t):

        return True

    if _is_fact_box_label_chain(t):

        return True

    if _is_own_plan_plus_run(t):

        return True
    # a German nav-label weld run into the article headline (class 82, 20.09.26)
    if _is_de_nav_weld_headline_chrome(t):

        return True

    if _INSTRUCTION_OPENER_RE.match(t):
        return True
    if _is_arxiv_abstract_chrome(t):
        return True
    if _is_qa_portal_chrome(t):
        return True
    if _is_de_pricing_chrome(t):
        return True
    # an ad-blocker-off / subscribe notice is a CTA chain, not a fact
    # (live 17.09.26, class 28 -- see _ADWALL_NOTICE_RE above)
    if _is_adwall_notice(t):
        return True
    if _is_course_cta_chrome(t):
        return True
    if _is_plan_scaffold_echo(t):
        return True
    if _is_github_issue_chrome(t):
        return True
    if _is_archive_listing(t):
        return True
    if _is_package_index_chrome(t):
        return True
    if _is_diagram_markup(t):
        return True
    if _is_ticker_loop(t):
        return True
    # A short extract ending on a bare section ordinal with no verb is a
    # chopped TOC item, not an insight (live 16.09.26:
    # `Probabilistic methods for uncertain reasoning 2.`). Same structural
    # rule as buffer_store.is_ordinal_stub -- reject at EXTRACTION time so
    # the cycle retries instead of burning a write the writer would drop.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from buffer_store import is_ordinal_stub
    except Exception:
        is_ordinal_stub = None
    if is_ordinal_stub is not None and is_ordinal_stub(t):
        return True
    # A legal-imprint / contact block must be refused at EXTRACTION time too
    # (live 16.09.26: cycle_c_github burned its deep read on a Transparenzliste
    # page whose 106-char address block cleared both gates). Same structural
    # rule as the writer gate -- postcode + international phone + e-mail.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from buffer_store import is_contact_block
    except Exception:
        is_contact_block = None
    if is_contact_block is not None and is_contact_block(t):
        return True
    # A company/Wikipedia infobox financial label chain must be refused at
    # EXTRACTION time too (live 17.09.26: cycle_e_competitors buffered the
    # JetBrains revenue/operating-income infobox). Same structural rule as the
    # writer gate -- >=2 (financial label, year in parens). No regex mirror:
    # the rule is logic, not a page phrase, exactly like is_contact_block.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from buffer_store import is_financial_infobox
    except Exception:
        is_financial_infobox = None
    if is_financial_infobox is not None and is_financial_infobox(t):
        return True
    # Ask the writer gate too: a 2B word salad scores a HIGH unique-token
    # ratio (the motif sits inside otherwise-distinct words), so only
    # buffer_store.is_glued_motif sees it. Rejecting it HERE lets the cycle
    # retry (k=6) instead of burning itself on a write the writer drops.
    try:
        # same sibling-import idiom as store() below
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from buffer_store import is_glued_motif
    except Exception:
        return False
    return bool(is_glued_motif(t))


def _writer_gate_refuses(text):
    """True when the WRITER (buffer_store.is_junk) would refuse this text.

    2026-09-22, MEASURED: the extractor gate above (`_is_junk`) keeps 40+
    single-class chrome detectors, and store_or_deep's fallback chain ends in a
    buffer write decided by buffer_store.is_junk. Of 600 audited
    `reason="junk"` rows, 368 (61%) were SILENT DROPS: this module believed it
    had a learnable insight, the writer refused it, and the cycle logged only
    the generic "rejected, not trained". Missing detectors: _is_serp_snippet
    222 (dated SERP titles), the `self-critique` marker 109, _is_nav_chrome 88.
    That silent disagreement is what the 57% rejection rate is made of.

    Deliberately a SEPARATE predicate, not folded into `_is_junk`: the two
    gates have intentionally different strictness (the extractor must keep
    prose that merely *mentions* an ad-wall or a plan, and `_clean_insight`
    depends on that — measured: folding the writer into `_is_junk` regressed 4
    gate tests). This is consulted only at the WRITE DECISION in store(), so
    the refusal becomes explicit and auditable instead of silent.
    """
    if not text:
        return False
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from buffer_store import is_junk as _writer_is_junk
    except Exception:
        return False
    try:
        return bool(_writer_is_junk(text))
    except Exception:
        return False


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


def _filter_junk(results):
    """Drop junk 'Title :: snippet' entries from a raw search-result string."""
    if not results or "||" not in results:
        return results
    keep = []
    for p in results.split("||"):
        if "::" not in p:
            continue
        title, _, snippet = p.partition("::")
        if _is_junk(snippet) or _is_junk(title):
            continue
        keep.append(p.strip())
    return " || ".join(keep) if keep else ""


def search(query, k=3):
    """Web search via the tool server (CDP browser). Junk parts are dropped."""
    try:
        req = urllib.request.Request(LIVE + "/execute_tool",
            data=json.dumps({"tool": "web_search", "params": {"query": query}}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=90))
        raw = r.get("result", {}).get("results", "")[:2000]
        return _filter_junk(raw) or raw
    except Exception:
        return ""


def _strip_html(html):
    """Strip tags/scripts/styles from HTML to plain text (pure, testable)."""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_bing_url(redirect):
    """Decode a Bing ck/a redirect to its real target URL (pure, testable)."""
    import base64
    u = re.search(r"[?&]u=a1([^&]+)", redirect)
    if not u:
        return ""
    b64 = u.group(1).replace("-", "+").replace("_", "/")
    b64 += "=" * (-len(b64) % 4)
    try:
        return base64.b64decode(b64).decode("utf-8", "replace")
    except Exception:
        return ""


def _fetch_page(url, max_chars=6000):
    """Fetch and strip a real web page to plain text (deep reading, not titles)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        return _strip_html(html)[:max_chars]
    except Exception:
        return ""


# A candidate sentence must carry technical signal, otherwise the extractor is
# merely returning whatever chrome the page rendered FIRST. Live 13.09.26, two
# cycles in a row "learned" ad/nav chrome as the insight:
#   docs      -> "LoRA PEFT 🏡 View all docs AWS Trainium &amp; Inferentia …"
#   competitor-> "Unsere Werbepartner Einkaufen Ferienwohnungen Freizeit und …"
# A number or a technical noun/verb is the cheapest reliable signal that a
# sentence is worth learning from; if NO sentence qualifies we fall through to
# LLM distillation instead of storing page furniture.
_TECH_HINT_RE = re.compile(
    r"\b(\d+|model|models|agent|agents|llms?|tokens?|train(?:ing|ed|s)?|"
    r"inference|latency|throughput|memory|benchmarks?|datasets?|embeddings?|"
    r"attention|transformers?|fine-?tun\w*|quantiz\w*|distill\w*|prompts?|"
    r"context|weights?|layers?|gpus?|cpus?|optimizers?|gradients?|loss|"
    r"accuracy|architectures?|frameworks?|apis?|pipelines?|retrieval|rag|"
    r"reasoning|polic(?:y|ies)|evaluation|scaling|sparse|mixture|state space|"
    r"mamba|rlhf|lora|peft|vllm|openai|hugging\s?face|pytorch|tensorflow|"
    r"nvidia|cuda|modell\w*|inferenz|trainings?\w*|agenten\w*|sprach\w*|"
    r"sicherheit\w*|lern\w*)\b",
    re.IGNORECASE)


def _looks_like_content(sentence):
    """True when a candidate sentence carries real technical signal."""
    return bool(_TECH_HINT_RE.search(sentence or ""))


def _has_alpha_signal(text):
    """True when the technical signal is a real keyword, not a bare digit.

    Live 16.09.26: `_clean_insight` trusted ANY short (<90) candidate whose
    `_TECH_HINT_RE` matched — but that alternation also matches a bare number,
    so a document heading ("Distinction between classical and modern physics
    2.") was buffered as multi-domain knowledge on the strength of the section
    numeral `2`. A bare digit is a section number, not knowledge.
    Measured over the live 300-row buffer: requiring an ALPHABETIC keyword
    rejects 42 verbless fragments (leaked extraction scaffolding, "Situation
    2:" stubs, phone/contact chrome) and keeps all 13 rows that carry a real
    technical keyword — no insight lost.
    Live 16.09.26 (second pass): scanning only the FIRST match rejected real
    prose whose opening technical-ish token is a bare number —
    "By contrast, the 2024 study found quantization recovers 97% of fp16
    accuracy at INT4." matched "2024" first and never saw "quantization". Scan
    every match; accept when ANY is alphabetic. Strictly widens acceptance to
    text that carries a genuine keyword, so no junk class can slip in.
    """
    for m in _TECH_HINT_RE.finditer(text or ""):
        if any(c.isalpha() for c in m.group(0)):
            return True
    return False


# A real sentence has a verb; a nav/menu fragment ("Blog - Neutree Projects ▾
# ... and project updates.") has none. Cheapest reliable way to tell prose from
# a link list before it reaches the buffer (live 14.09.26).
_VERB_RE = re.compile(
    r"\b(is|are|was|were|be|been|being|has|have|had|do|does|did|can|could|will|"
    r"would|should|may|might|must|use[sd]?|using|show[s]?|provide[sd]?|"
    r"require[sd]?|enable[sd]?|reduce[sd]?|improve[sd]?|allow[sd]?|makes?|"
    r"gives?|give|offers?|supports?|achieve[sd]?|increases?|decreases?|"
    r"runs?|run|works?|work|means?|helps?|needs?|lets?|let|takes?|"
    r"reports?|finds?|found|adds?|added|removes?|introduces?|keeps?|gets|"
    r"become[s]?|remains?|appears?|seems?|contains?|includes?|"
    r"verwendet|bietet|erm\u00f6glicht|reduziert|verbessert|nutzt|ist|sind|wird|werden)\b",
    re.IGNORECASE)


def _is_nav_list(text):
    """True when `text` is a link/nav list, not prose.

    Live 14.09.26: deep_learn returned vLLM's docs sidebar verbatim
    ("Generation RunPod SkyPilot Streamlit NVIDIA Triton Integrations ... What
    is Layerwise (Re)loading?"). At >=90 chars it cleared the length-based
    prose trust in `_clean_insight` and would have been stored as a "learning".
    Real prose mixes case and uses commas; a run of >=6 TitleCase tokens with no
    comma/semicolon is a menu. Narrow by design — untitled lowercase prose and
    ordinary sentences (few capitalised words, commas present) never match.
    """
    t = text or ""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", t)
    if len(words) < 6:
        return False
    titlecase = sum(1 for w in words if w[:1].isupper() and w[1:].islower())
    return titlecase >= 6 and ("," not in t) and (";" not in t)


# Result URLs Bing's DOM sometimes collapses to a bare domain
# ("the-agent-report.com") or a stub with no article id ("arxiv.org/abs",
# "arxiv.org/html"). Those are unfetchable, yet the old `if urls: return
# urls[:k]` handed them straight to deep_learn and starved it — 4 consecutive
# cycles (14.09.26) were gated with zero learning because nothing reachable was
# ever fetched. Rejecting them lets the HTTP ck/a fallback below run.
_URL_STUB_PATHS = frozenset({"abs", "html", "index.html"})

# class 134 (22.09.26): a NEWSROOM INDEX page is not an article.
#
# Live: cycle_a_technews "learned", verbatim from online_buffer.jsonl,
#   "UK My dream to serve in the UK army was ended by childhood eye surgery
#    Some 114,000 Army application were rejected on medical grounds in the past
#    five years, Freedom of Information figures show."
#
# That is a BBC index strip: the query's top result was the truncated URL
# `https://www.bbc.com/news/articles` (an index, not an article), and
# deep_learn scored an extracted "sentence" that is really CARD[i]'s country
# tag (`UK`) welded to CARD[i+1]'s headline. The strip's own relative stamps
# (`6 hrs ago`, `8 hrs ago`, `5 hrs ago`) sit BETWEEN the cards, so the
# sentence regex `[A-Z][^.!?]{40,250}[.!?]` spans the boundary; the tag and the
# headline then read as one grammatical sentence, the stamps are stripped by
# `_clean_insight`'s clock/byline helpers, and the digits (`114,000`) satisfy
# the technical-signal gate. Nothing text-level catches this: the stored string
# carries no `ago` at all, and the tag shape is NOT a discriminator —
# `^[A-Z]{2,3}\s+[A-Z][a-z]` matched 190 rows across the corpora, almost all
# genuine prose ("AI Coding Agents Are Reshaping...", "CEO Andy Jassy told...",
# "AI Consciousness asks whether...").
#
# So the discriminator is PAGE-LEVEL, not text-level: a newsroom index/feed
# repeats the site's own relative-stamp UNIT across its card stream, while an
# article page carries at most one. Measured 22.09.26 (fetch + the exact
# 4000-char window deep_learn scores):
#   index pages   bbc.com/news/articles 19/10 · bbc.co.uk/news 36/24 ·
#                 techcrunch.com 23/17 · news.ycombinator.com 30/30 ·
#                 huggingface.co/models 27/21   (>=10 stamps in-window)
#   prose pages   bbc.com article 0 · arxiv.org/abs 0 · HF PEFT docs 0 ·
#                 github.com/<repo> 0 · github.com/trending 0 ·
#                 HN item 0 · reddit.com/r/... 0 · openai.com/index/... 0 ·
#                 blog.langchain.dev 0                 (all exactly 0)
# A `>= 3` threshold sits far inside that gap: every real page measured 0, the
# lowest flagged page measured 10. `hrs?`/`mins?` are included because the
# BBC strip writes `5 hrs ago` and `_REL_TIME_AGO_RE` (used by the class-34
# nav-chain helper) does not cover those spellings — this is a separate regex
# on purpose, so that helper's measured semantics stay untouched.
_PAGE_REL_STAMP_RE = re.compile(
    r"\b\d{1,3}\s+(?:minutes?|mins?|hours?|hrs?|days?)\s+ago\b", re.IGNORECASE)


def _is_news_index_page(text):
    """True when a fetched PAGE is a newsroom/feed index, not an article (134).

    Counts the site's own repeated relative-stamp unit over the page text.
    Only consulted on the fetched page, never on a candidate insight: a single
    `<n> hours ago` inside real prose is ordinary (`It ran 3 hours ago with 12
    4 retries recorded in the log.`) and must stay learnable.
    """
    t = text or ""
    if len(t) < 500:
        return False  # too short to be an index; a snippet keeps prose trust
    return len(_PAGE_REL_STAMP_RE.findall(t)) >= 3



def _fair_share_window(texts, budget=4000, floor=700):
    """Give EVERY fetched page a slice of the distillation window.

    Root cause V (live 16.09.26): deep_learn used `" ".join(texts)[:4000]`.
    A single page is truncated to 6000 chars, so the FIRST page always ate
    the whole 4000-char window and pages 1..k-1 contributed 0 characters
    (measured: page[0]=4000/6000, pages[1..4]=0/5426,0/6000,0/6000,0/6000).
    deep_learn(k=2) and deep_learn(k=6) therefore returned the SAME string,
    and store_or_deep's guard `deep2 not in (insight, deep)` skipped the
    k=6 second chance entirely - the documented rescue path was a no-op on
    every cycle whose top page was weak (live: 2 of 4 rejects were this).
    """
    texts = [t for t in texts if t]
    if not texts:
        return []
    per = max(floor, budget // len(texts))
    out, used = [], 0
    for t in texts:
        take = t[:per]
        if used + len(take) > budget:
            take = take[:max(0, budget - used)]
        if take:
            out.append(take)
            used += len(take)
        if used >= budget:
            break
    return out

def _usable_urls(urls, k):
    """Keep only fetchable result URLs (drop bare domains and known stubs)."""
    good = []
    for u in urls:
        path = re.sub(r"^https?://[^/]+", "", u).strip("/")
        if path and path not in _URL_STUB_PATHS:
            good.append(u)
    return good[:k]


def _http_search_urls(q, k=3):
    """Direct-HTTP Bing search with ck/a redirect decode (the FALLBACK path).

    Also used to TOP UP the CDP path: Bing's rendered DOM truncates result
    paths, so the browser path alone yields fewer than k fetchable URLs.
    q must already be URL-quoted.
    """
    import html as _html
    raw = urllib.request.urlopen(urllib.request.Request(
        f"https://www.bing.com/search?q={q}",
        headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8", "replace")
    raw = _html.unescape(raw)
    out = []
    seen = set()
    for m in re.finditer(r"href=\"(https://www\.bing\.com/ck/a\?[^\"]+)\"", raw):
        dec = _decode_bing_url(m.group(1))
        if dec.startswith("http") and "microsoft" not in dec and dec not in seen:
            seen.add(dec)
            out.append(dec)
    return out[:k]


def _search_urls(query, k=3):
    """Return real result URLs for a query.

    PRIMARY: via the CDP browser (:9222, real Chrome session) — Bing serves
    anonymous crawlers regional garbage (Chinese CSDN for a LoRA query),
    while the browser session gets relevant results.
    FALLBACK: direct HTTP with ck/a redirect decode.
    """
    try:
        import html as _html
        q = urllib.parse.quote(query)
        # PRIMARY: navigate the CDP browser and read result links from the DOM
        try:
            req = urllib.request.Request(LIVE + "/execute_tool",
                data=json.dumps({"tool": "browser_action",
                                 "params": {"action": "navigate",
                                            "url_or_selector": f"https://www.bing.com/search?q={q}"}}).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
            time.sleep(3)  # let the page render
            req = urllib.request.Request(LIVE + "/execute_tool",
                data=json.dumps({"tool": "browser_action", "params": {"action": "read"}}).encode(),
                headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=30))
            content = r.get("result", {}).get("content", "")
            # Bing renders result URLs as "domain › path › subpath" sequences
            # next to each result. Reconstruct full URLs from that pattern.
            urls = []
            seen = set()
            # find "https://domain › path" patterns and rebuild them
            for m in re.finditer(r"(https?://[a-zA-Z0-9.\-]+\.[a-z]{2,})((?:\s*›\s*[^\s›│]+)*)", content):
                host = m.group(1)
                path = re.sub(r"\s*›\s*", "/", m.group(2)).strip()
                u = host + path if path else host + "/"
                u = u.rstrip("/.,;")
                if "…" in u or u.endswith("."):
                    continue  # truncated by Bing's display — unfetchable
                if u not in seen and len(u) > 15:
                    seen.add(u)
                    urls.append(u)
            good = _usable_urls(urls, k)
            if len(good) >= k:
                return good
            # The rendered DOM only shows TRUNCATED result paths ("..."),
            # which _usable_urls must skip, so this path alone returns far
            # fewer than k fetchable URLs (measured 11/36 vs 36/36 over 6
            # queries, live 16.09.26). Top up from the HTTP path instead of
            # returning early - deep_learn's k=6 retry could not compensate
            # because _search_urls(k=6) still returned only 2 URLs.
            merged = list(good)
            for u in _http_search_urls(q, k):
                if u not in merged:
                    merged.append(u)
            if merged:
                return merged[:k]
        except Exception:
            pass
        # FALLBACK: direct HTTP with ck/a redirect decode
        return _http_search_urls(q, k)
    except Exception:
        return []


def deep_learn(query, k=2):
    """Search, then READ the top result pages and extract a deep insight.

    This is the difference between collecting headlines and actually learning:
    we fetch the real article text and distill one actionable insight from it.
    """
    urls = _search_urls(query, k=k)
    if not urls:
        return ""
    texts = []
    for u in urls:
        t = _fetch_page(u)
        # Raw PDF byte streams are not prose: they carry no extractable sentence
        # and their mis-decoded mojibake has reached the buffer before (root
        # cause P). Skip them so they cannot occupy a fair-share slot.
        if len(t) > 200 and not t.lstrip().startswith("%PDF"):
            # class 134: a newsroom INDEX page is a card stream, not an article.
            # Its relative stamps sit between the cards, so the sentence regex
            # spans card boundaries and welds one card's country tag onto the
            # next card's headline. Skipping the page lets a later URL (an
            # actual article) hold the slot instead.
            if _is_news_index_page(t):
                continue
            texts.append(t)
    if not texts:
        return ""
    combined = " ".join(_fair_share_window(texts, 4000))[:4000]
    # PRIMARY: deterministic extraction — first meaningful sentence of the page.
    # Reliable, no model dependency. The 2B model (Qwen3.5 thinking family)
    # emits reasoning traces that are not reliably parseable, so we don't
    # depend on it for the core learning signal.
    _NAV = ("search", "log in", "create account", "donate", "upload file",
            "community portal", "recent changes", "personal tools", "contents",
            "move to sidebar", "toggle", "navigation", "main menu", "appearance",
            "special pages", "random article", "about wikipedia", "contact us",
            "cookie", "privacy", "terms of use", "jump to", "skip to",
            # site chrome / docs navigation (huggingface etc.)
            "alle docs anzeigen", "docs anzeigen", "tools", "developer tools",
            "hub python bibliothek", "alle docs", "bersicht", "übersicht",
            # marketing chrome / testimonials (live 11.09.26): the extractor
            # returned "No thanks “Sebastian is an incredible educator and
            # always has invaluable insights" TWICE in one day — that is a
            # course-landing-page testimonial, not a research insight.
            "no thanks", "testimonial", "subscribe", "newsletter",
            "sign up", "signup", "register", "all rights reserved",
            "read more", "click here", "follow us", "join our",
            "share this", "leave a reply", "cookie policy", "privacy policy",
            # login walls / anti-bot pages (live 13.09: the github cycle stored
            # the literal "You switched accounts on another tab or window.")
            "switched accounts", "another tab or window", "sign in to",
            "are you a robot", "verify you are human", "captcha",
            "access denied", "not found", "view all docs")
    best, best_score = "", 0
    for t in texts:
        for m in re.finditer(r"([A-Z][^.!?]{40,250}[.!?])", t):
            s = m.group(1).strip()
            low = s.lower()
            if any(n in low for n in _NAV):
                continue  # skip navigation/boilerplate
            # skip sentences that are mostly link-lists (many "›" separators)
            # A single raw entity (&amp;/&#39;) means the sentence is doc-site
            # navigation chrome, not prose — live 13.09: the docs cycle returned
            # the literal "LoRA PEFT 🏡 View all docs AWS Trainium &amp; ...".
            if s.count("›") > 0 or "&amp;" in s or "&#" in s:
                continue
            # skip pure praise / first-person marketing voice — no technical
            # content (a testimonial carries no learning signal)
            if re.search(r"\b(incredible|amazing|awesome|best (course|teacher)|"
                         r"highly recommend|thank you|thanks)\b", low):
                continue
            if _is_nav_list(s):
                continue  # sidebar/menu run, not a sentence
            # SCORE, don't take the first match. Live 14.09.26: the first
            # sentence-shaped string on most pages is chrome ("Blog - Neutree
            # Projects ▾ ... Product notes, architecture, and project updates.")
            # which cleared every gate and was stored as a "learning". Real
            # prose has a verb and usually technical nouns; a menu has neither.
            tech = len(_TECH_HINT_RE.findall(s))
            has_verb = bool(_VERB_RE.search(s))
            if not has_verb and tech == 0:
                continue  # fragment, not a sentence with content
            score = tech * 10 + (5 if has_verb else 0)
            n = len(s)
            if n < 60 or n > 220:
                score -= 5  # prefer mid-length full sentences
            if any(ch in s for ch in "\u25be\u2502\u00bb\u00b7"):
                score -= 8  # menu glyphs
            if score > best_score:
                best_score, best = score, s
    if best:
        return best
    # SECONDARY: deep distillation via smart_route — the free cloud chain
    # (nemotron-550b, minimax-m2.7, glm-5.2 ...) gives ASI-grade extraction
    # at 0 EUR. Falls back to local 4B via Ollama if cloud fails.
    try:
        req = urllib.request.Request(LIVE + "/v1/chat/completions",
            data=json.dumps({"model": "mini-openamer", "max_tokens": 900,
                "use_tools": False,
                "messages": [
                    {"role": "user", "content":
                     f"{combined}\n\nDistill the ONE most valuable technical insight "
                     f"from this for an autonomous AI agent. One sentence, no preamble. "
                     f"Start with [INSIGHT]"}
                ]}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=300))
        content = r["choices"][0]["message"]["content"].strip()
        src = r.get("routed_to", "local")
        if "[INSIGHT]" in content:
            content = content.split("[INSIGHT]", 1)[1].strip()
        content = re.sub(r"^\s*\{.*?\}\s*", "", content, flags=re.DOTALL)
        content = re.sub(r"^(Here is|Here's|The key|Sure|Okay|I'll|Let me).*?:\s*", "", content, flags=re.IGNORECASE)
        return _clean_insight(content, 250)
    except Exception:
        # fallback: local 4B via Ollama (background task, speed irrelevant)
        try:
            req = urllib.request.Request("http://localhost:11434/api/generate",
                data=json.dumps({"model": "qwen3.5:4b-q4_K_M",
                    "prompt": f"Summarize the key technical insight from this in ONE sentence "
                              f"(no preamble, just the sentence):\n\n{combined}",
                    "stream": False, "keep_alive": 0}).encode(),
                headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=600))
            content = r.get("response", "").strip()
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1].strip()
            return _clean_insight(content, 200)
        except Exception:
            return ""


_BYLINE_SEP = " \u00b7 "
_BYLINE_SEP_RE = re.compile(r"\s*[\u00b7|\u2022]\s*")

# A date literal, in the three shapes pages actually emit. Reused by both
# byline regexes so the two can never drift apart.
_DATE_ALT = (
    r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"\d{1,2},?\s+\d{2,4}"                       # "June 11, 2026"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"\d{4}"                                      # "August 2026"
    r"|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+\d{2,4}"  # "14 September 26"
    r"|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"          # "11.06.2026"
    r")")

# One byline/dateline SEGMENT (between separators). Deliberately narrow: it is
# only consulted for the leading segments of a text, and only to be *removed*
# so the prose behind it survives.
_ATTRIB_SEG_RE = re.compile(
    r"^(?:"
    r"(?:written|reviewed|published|posted|updated|authored|edited|"
    r"last\s+(?:updated|reviewed|modified))\s+by\b.*"
    r"|(?:published|posted|updated|reviewed|modified|"
    r"last\s+(?:updated|reviewed|modified))\b.*\d{4}\s*$"
    r"|by\s+[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3}\s*$"
    r"|" + _DATE_ALT + r"\s*$"
    r")",
    re.IGNORECASE)

# Attribution that LEADS the text with no separator before it, e.g. the live
# 16.09.26 shape "... · Last reviewed July 23, 2026 AI Consciousness asks ...".
# A real date literal (or "<verb> by <Name>") is REQUIRED. That is what keeps
# genuine prose safe: "Published research from Stanford in 2024 shows
# transformers scale ..." has neither, so it is left untouched.
_BARE_ATTRIB_RE = re.compile(
    r"^\s*(?:"
# Live 16.09.26 (2nd shape): a publisher dateline with the article title
# welded straight on -- "This article was published on August 6, 2026
# Artificial Intelligence OpenAI and four rivals just agreed ..." -- where
# the body sentence carries no byline verb of its own, so the segment/date
# rules never match it. Strip the leading "This article was <verb> [on] <date>".
    r"this\s+article\s+was\s+(?:published|posted|updated|reviewed)\s+"
    r"(?:on\s+)?(?:" + _DATE_ALT + r"|\d{4})\s*"
    r"|(?:written|reviewed|published|posted|updated|authored|edited)\s+by\s+"
    r"[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3}(?:,\s*[^\u00b7|\u2022.]{0,40})?\s*"
    r"|by\s+[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,3}\s+"
    r"(?:published|posted|updated|reviewed|last\s+reviewed)\s+(?:on\s+)?"
    + _DATE_ALT + r"\s*"
    r"|(?:last\s+)?(?:reviewed|updated|published|posted|modified)\s+(?:on\s+)?"
    + _DATE_ALT + r"\s*"
    r")",
    re.IGNORECASE)


_READ_TIME_RE = re.compile(r"^\s*\d{1,3}\s*min\s*read\b[\s:\u00b7|\u2013-]*")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.'-]*")

# Platform names a share widget lists. Kept as a plain alternation so the rules
# below stay readable.
_PLATFORM_ALT = (r"(?:x|twitter|facebook|linkedin|reddit|whatsapp|hn|"
                 r"hacker\s*news|bluesky|pinterest|email)")

# A social share widget is page furniture only when it sits in the PAGE HEADER,
# i.e. directly after a date literal, a read time, or a `//` nav separator —
# prose never has that adjacency (live 16.09.26, three rows of the same class):
#   "… / JUN 1, 2026 / 0 comments … 32 min read Share on Twitter , LinkedIn …"
#   "3 min read Illustration The Agent Times // Share X LinkedIn HN Copy link …"
#   "… Published on: May 21, 2026 Share Facebook Twitter Bluesky Fields ranging …"
#
# A voice-only rule ("share on <platform>" anywhere) was measured and REJECTED:
# it ate a real sentence ("We share on Twitter the benchmark results …") and
# truncated a second row. Only the ANCHORED form is safe — that is why this
# needs the header anchor and no general fallback.
_SHARE_WIDGET_RE = re.compile(
    r"(?:" + _DATE_ALT + r"|\b\d{1,3}\s*min\s*read\b|//)[\s:\u00b7|\u2013-]*"
    r"share\s+(?:on\s+)?" + _PLATFORM_ALT + r"\b(?:\s*,?\s*" + _PLATFORM_ALT + r"\b)*[\s,]*",
    re.IGNORECASE)

# A share widget at the very START of the text that lists SEVERAL platforms
# ("Share X LinkedIn HN") is header furniture. The >=2-platform requirement is
# what keeps a sentence that merely opens with a share verb safe:
# "Share on Twitter is not a strategy; accuracy comes from quantization at int4."
# is untouched (single platform + prose follows). Measured live 16.09.26: 1 hit
# (the leaking row), 0 real-prose rows.
_LEADING_SHARE_WIDGET_RE = re.compile(
    r"^\s*share\s+(?:on\s+)?" + _PLATFORM_ALT +
    r"\b(?:\s*,?\s*" + _PLATFORM_ALT + r"\b)+[\s,]*",
    re.IGNORECASE)

# "Copy link" is a share-widget ACTION button; real prose says "the link
# between latency and batch size", never "Copy link". Measured over the live
# 277-row buffer: 1 hit (the leaking row), 0 real-prose rows.
_COPY_LINK_RE = re.compile(r"\bcopy\s+link\b", re.IGNORECASE)


def _strip_read_time_header(text):
    """Drop a leading "<N> min read <category nav>" blog header.

    Live 16.09.26 (two separate cycles): the multi-domain cycle learned rows
    that are page furniture welded to a real headline --
      "11 min read China Semiconductors AI Infrastructure Geopolitics China AI
       Chip Boom: CAICT 417% Demand vs 128% Supply 2026 Caixin Sept 15, 2026:
       CAICT says China AI compute demand jumped 417% YoY in Q1 ..."
      "12 min read Nvidia AI Infrastructure GPUs FinOps Wall Street Nvidia
       $500B AI Compute Fund: What Developers Need to Know ..."
    The knowledge is the headline BEHIND the read-time and its category nav, so
    STRIP rather than reject (same call as the byline prefix).

    The boundary is found structurally, not by guessing a word count: the
    category nav repeats a word the headline then re-uses ("China ... China AI
    Chip Boom"), so the SECOND occurrence is where the article starts. No
    duplicate -> the text is left untouched, which is what keeps a real
    sentence that merely mentions a read time safe.
    """
    t = (text or "").strip()
    m = _READ_TIME_RE.match(t)
    if not m:
        return t
    rest = t[m.end():].lstrip()
    # A `//` nav separator terminates the header just like a repeated nav word
    # does (live 16.09.26: "3 min read Illustration The Agent Times // Share X
    # LinkedIn HN Copy link The specific article …").
    slash = rest.find("//")
    if 0 <= slash <= 60:
        out = rest[slash + 2:].strip()
        # the // nav separator is followed by the share widget on this shape,
        # so consume it here (the anchor is gone by the time the blog-stack
        # stripper runs) — live 16.09.26 row "… The Agent Times // Share X
        # LinkedIn HN Copy link The specific article …"
        out = _SHARE_WIDGET_RE.sub(" ", out)
        out = _LEADING_SHARE_WIDGET_RE.sub(" ", out)
        out = _COPY_LINK_RE.sub(" ", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out if len(out.split()) >= 5 else t
    seen, boundary = set(), None
    for tok in _WORD_RE.finditer(rest):
        w = tok.group(0)
        if not w[:1].isupper():
            break                       # nav run ended, no repeat -> not a header
        key = w.lower()
        if key in seen:
            boundary = tok.start()      # the headline repeats a nav word
            break
        seen.add(key)
    if boundary is None:
        return t
    out = rest[boundary:].strip()
    # only strip when a real sentence body remains; else leave the chrome alone
    return out if len(out.split()) >= 5 else t


# A LEADING blog/magazine header that CLOSES with its own "<N> min read" label
# (live 17.09.26 — the family the skill had listed as measured-but-unfixed).
# Four live shapes, one structure: page furniture welded in FRONT of the
# article body, where the furniture carries the header's closing label.
#
#   "Building is my Passion Post Cancel Efficient Fine-tuning with PEFT and
#    LoRA Posted Aug 21, 2023 By Niklas Heidloff 3 min read Classic
#    fine-tuning of Large Language Models typically changes most weights ..."
#   "Updated: September 7, 2026 15 min read As enterprises rapidly deploy ..."
#   "General Compute \u00b7 March 18, 2026 \u00b7 6 min read AI Inference Fundamentals
#    View all 17 \u2192 Technical deep-dives on the building blocks ..."
#   "Feb 7, 2026 18 min read Read article All Articles Security LLM Red
#    Teaming Playbook: ..."
#
# STRIP, never reject — the body behind the header is the knowledge.
#
# The discriminator is structural, not a word list: the head BEFORE the read
# time must (a) contain a real DATE literal and (b) carry NO sentence
# terminator once the date matches are removed. Page furniture is a LABEL
# CHAIN, so it never ends a sentence; prose that merely MENTIONS a read time
# carries full stops around it and is untouched by construction.
#
# Measured live 17.09.26: 3/3 documented leak shapes stripped with the body
# byte-identical, 0 of 8 hand-written counter-cases changed (a 32 min read /
# 6 min read / 11 min read sentence, a byline sentence, "Published research
# from Stanford in 2024 ...", "By contrast, the 2024 study ..." and a
# two-clock-time sentence), 7 of the 300 live buffer rows touched — every one
# genuine header chrome. The head window is capped at 220 chars so a real
# sentence that merely ENDS with a read time can never be reached.
_READ_TIME_CLOSE_RE = re.compile(
    r"\b\d{1,3}\s*min\s*read\b[\s:\u00b7|\u2013-]*", re.IGNORECASE)
_BLOG_HEAD_DATE_RE = re.compile(_DATE_ALT, re.IGNORECASE)
_BLOG_HEAD_SENT_END_RE = re.compile(r"[.!?]")
_HEAD_WINDOW = 220
_BLOG_HEAD_LOWER_RE = re.compile(r"\b[a-z]{2,}\b")


def _strip_trailing_read_time_header(text):
    """Drop a leading blog header that closes with its own "<N> min read".

    Live 17.09.26: cycle_d_docs learned the PEFT/LoRA row whose page furniture
    rode in front of the article's opening sentence. The body is the knowledge,
    so this is a strip. See the module comment above for the guard design.
    """
    t = (text or "").strip()
    head_zone = t[:_HEAD_WINDOW]
    m = _READ_TIME_CLOSE_RE.search(head_zone)
    if not m:
        return t
    body = t[m.end():].strip()
    if len(body.split()) < 5:
        return t                       # no real sentence behind it -> leave it
    # live 17.09.26 (class 41): a DIGIT-LED headline ("8 best open-source AI
    # agent frameworks ...") is a real sentence body too, so allow it here.
    if not (body[:1].isupper() or body[:1].isdigit()):
        return t
    head = head_zone[:m.end()]
    if _BLOG_HEAD_SENT_END_RE.search(_BLOG_HEAD_DATE_RE.sub(" ", head)):
        return t                       # furniture never ends a sentence
    if _BLOG_HEAD_DATE_RE.search(head):
        return body                    # a dateline makes it a header
    # No dateline: a short PURE-TitleCase label chain ("AI Agents", "Machine
    # Learning") is page furniture as well. Real prose that merely MENTIONS a
    # read time sits inside a sentence and carries lowercase words ("... the
    # reading time was about 8 min read ..."), so it stays untouched.
    # Measured live 17.09.26: 2/2 leaked rows stripped with a byte-identical
    # body, 0 of 3,056 longterm episodes, 0 hand-written prose controls.
    core = _READ_TIME_CLOSE_RE.sub(" ", head)
    core = _BLOG_HEAD_DATE_RE.sub(" ", core)
    core = re.sub(r"[^A-Za-z0-9&+.'\- ]", " ", core).strip()
    words = core.split()
    if 1 <= len(words) <= 4 and not _BLOG_HEAD_LOWER_RE.search(core):
        return body
    return t


_ARROW_NAV_RE = re.compile(r"\s*-{1,2}>\s*")
_POSTED_BY_RE = re.compile(
    r"^\s*(?:posted|published|updated)\s+on\s+[^,]{3,40}\s+by\s+[A-Za-z][\w.'-]*\s*",
    re.IGNORECASE)

# Leading blog header stack: "<author> / <DATE> / <N> comments" (live 16.09.26,
# fourth shape of the byline family). Slash-separated page furniture welded to
# the headline. STRIP, like the other byline shapes — the headline behind it is
# the knowledge. Measured over the live 277-row buffer: 1 hit (the leaking row),
# 0 real-prose rows.
_BLOG_HEADER_STACK_RE = re.compile(
    r"^\s*[A-Za-z][\w .'\-]{0,40}\s*/\s*" + _DATE_ALT + r"\s*/\s*\d+\s*comments?\b\s*",
    re.IGNORECASE)


# Leading CLOCK-DATELINE fragment welded to the article body (live 16.09.26,
# class 13 of the leading-chrome family): cycle_e_competitors stored
#
#   "at 11:44 am we asked four ai coding agents to In a recent experiment,
#    four AI coding agents were tasked with recreating the classic game
#    Minesweeper, revealing both the potential and limitations of modern AI in
#    programming."
#
# The extractor cut the byline mid-sentence, so a LOWERCASE fragment rides in
# front of a genuine paragraph. STRIP -- the body behind it is the knowledge.
#
# Two guards keep real prose safe (measured over the live 5046-row corpus:
# exactly 1 hit, the leaking row; 0 real-prose rows):
#   1. the row must OPEN with literal lowercase "at" + a clock time.
#      A sentence never starts "at 11:44 am ..." -- that is a byline cut
#      -- so the capitalized form "At 12:30 pm the batch job starts ..."
#      cannot match (the pattern is deliberately NOT case-insensitive).
#   2. the boundary is the first Capitalized token AFTER the dateline: the
#      fragment is lowercase by construction, so the article's opening word
#      is where it ends. A >= 5-word body must remain, else the text is
#      returned byte-identical.
_DATELINE_FRAGMENT_RE = re.compile(r"^at\s+\d{1,2}:\d{2}\s*(?:am|pm)\b\s*")


def _strip_dateline_fragment(text):
    """Drop a leading lowercase "at <time> am|pm" byline fragment.

    Live 16.09.26: cycle_e_competitors learned "at 11:44 am we asked four ai
    coding agents to In a recent experiment, four AI coding agents were tasked
    with recreating the classic game Minesweeper ..." — a mid-sentence byline
    cut prefixed a real paragraph. Strip, never reject: the paragraph is the
    knowledge. See the module comment above for the two guards.
    """
    t = (text or "").strip()
    m = _DATELINE_FRAGMENT_RE.match(t)
    if not m:
        return t
    rest = t[m.end():]
    boundary = None
    for tok in _WORD_RE.finditer(rest):
        if tok.group(0)[:1].isupper():
            boundary = tok.start()
            break
    if boundary is None:
        return t
    out = rest[boundary:].strip()
    return out if len(out.split()) >= 5 else t

# Leading NAV-LABEL STACK terminated by a publisher dateline (live 16.09.26,
# class 14 of the leading-chrome family): cycle_g_security stored
#
#   "SECURITY resources Whitepapers/Guides OWASP GenAI LLM Top 10 2026
#    August 3, 2026 About OWASP Top 10 for LLM Applications 2026 is the latest
#    community-driven guide to the most critical security risks facing
#    applications powered by large language models."
#
# The section nav (with its slash-joined menu pair) plus the dateline are page
# furniture; the sentence behind them is the knowledge -> STRIP.
#
# A GENERIC "<nav-run> <date> <body>" rule was MEASURED and REJECTED:
# it matched FOUR GitHub-advisory rows (real prose: "Critical Authenticated
# Arbitrary Data Export Theft via Mass Assignment in sendFileMessage
# GHSA-fhc2-x8cp-c5ch ...") as well as two counter-cases
# ("The paper compares German/English tokenizers on a March 3, 2026
# benchmark", "Whitepapers/Guides are listed on the site; the August 3,
# 2026 revision adds three sections.").
#
# The surviving rule adds the structural fact that separates a MENU from a
# sentence: the head before the date must be LABEL-LIKE -- a slash-joined
# Capitalized pair must be present AND the head may carry no function word
# (the/of/and/is/...) and at most one lowercase word. Measured over the live
# 5057-row corpus: 1 hit (the leaking row), 0 prose-like heads, 0 real-prose
# counter-cases.
_NAV_LABEL_DATE_ALT = (
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s*\d{4}"
)
_NAV_LABEL_STACK_RE = re.compile(
    r"^(?P<head>\S.{0,119}?[A-Z]\w{2,}/[A-Z]\w{2,}.{0,80}?)"
    r"(?P<date>" + _NAV_LABEL_DATE_ALT + r")\s+"
    r"(?P<body>[A-Z\x22\x27].{20,})$",
    re.S)
_NAV_LABEL_FUNC_WORDS = frozenset((
    "the", "of", "is", "are", "and", "on", "in", "to", "a", "an", "for",
    "with", "was", "were", "that", "this", "at", "by", "as", "it",
))


# A DATED HEADER STACK closed by a short LABEL, welded to the article body
# (live 17.09.26, class 29). cycle_g_security stored
#   "OWASP GenAI LLM Top 10 2026 OWASPGenAIProject Editor / August 3, 2026 /
#    Resources OWASP Top 10 for LLM Applications 2026 is the latest
#    community-driven guide to the most critical security risks facing
#    applications powered by large language models."
# The date fed the technical-signal gate and the 247 chars cleared the >=90
# trust; _NAV_LABEL_STACK_RE needs a slash-joined Capitalized PAIR (the head
# here is "OWASPGenAIProject", one glued token) and _BLOG_HEADER_STACK_RE needs
# "<N> comments", so nothing caught it. STRIP, not reject: the article's own
# sentence is the knowledge, and the earlier cycle had already stripped exactly
# this page's "SECURITY resources Whitepapers/Guides ..." head (class 14) --
# this is the SECOND variant of the same header, so it is the same family.
#
# The generic "<nav-run> <date> <body>" rule was MEASURED and REJECTED on
# 16.09.26 (see the _NAV_LABEL_STACK_RE note): it ate GitHub advisories and two
# prose counter-cases. This is the narrower surviving form, reusing the SAME
# proven discriminator -- the head must be LABEL-LIKE (no sentence terminator,
# <= 1 lowercase word, no function word), the closing label must be a SINGLE
# Capitalized token, and the body must open a sentence. Measured over 7,185
# live rows (buffer + junk log + learn log + world_model): 1 hit (the leaking
# row), 0 counter-case hits, 0 junk-log/learn-log hits.
_DATED_HEADER_SLASH_RE = re.compile(
    r"^(?P<head>\S[^.!?\n]{3,120}?)\s+/\s*" + _NAV_LABEL_DATE_ALT + r"\s*/\s*"
    r"(?P<label>[A-Z][\w'\-]{1,20})\s+"
    r"(?P<body>[A-Z\x22\x27].{25,})$",
    re.S)


def _strip_dated_header_slash_stack(text):
    """Drop a leading "<label stack> / <Month D, YYYY> / <Label> <body>".

    Structural, never topical: a menu is a LABEL CHAIN, a sentence has grammar.
    Real prose that merely cites a date between slashes carries a full stop (or
    a function word) in its head and is therefore untouched.
    """
    t = (text or "").strip()
    m = _DATED_HEADER_SLASH_RE.match(t)
    if not m:
        return t
    words = _WORD_RE.findall(m.group("head"))
    low = [w for w in words if w[:1].islower()]
    if len(low) > 1 or any(w.lower() in _NAV_LABEL_FUNC_WORDS for w in low):
        return t                      # prose head -> untouched
    out = m.group("body").strip()
    return out if len(out.split()) >= 5 else t


# Leading BYLINE STACK: author + date + engagement counters + a Share button
# (live 16.09.26, class 15 of the leading-chrome family): cycle_b_papers
# stored, verbatim,
#
#   "Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: We show that LLM agents
#    can figure out who you are from your anonymous online posts."
#
# The paper's byline row rides in front of its own TL;DR, which IS the
# knowledge -> STRIP. The structural signature is the ORDER: a Name, a date
# literal, then engagement counters, then the widget's "Share" control.
# Each element alone is prose-safe; only the welded RUN is page furniture.
#
# Two guards, each measured over the live 5068-row corpus (1 hit = the leaking
# row; 0 real-prose rows):
#   1. the counters must be BARE numbers (no nouns after them) AND be followed
#      directly by "Share", so a real sentence citing the date and its
#      metrics ("Alice Smith Jan 5, 2026 reported 40% lower decode
#      latency ...") cannot match.
#   2. the Name+date must sit at the START (re.match), so a date mid-sentence
#      ("The Feb 24, 2026 release of vLLM adds 3 new kernels") is untouched.
# A bare "N words then Share" rule was measured and rejected: it also ate
# prose that merely mentions sharing.
_BYLINE_STACK_RE = re.compile(
    r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+"
    r"(?:" + _DATE_ALT + r")\s+"
    r"(?:\d{1,3}\s+){1,4}"
    r"[Ss]hare\s+(?=[A-Z\x22\x27\W])",
    re.IGNORECASE)


def _strip_byline_stack(text):
    """Drop a leading "<Name> <date> <counters> Share" byline row.

    Live 16.09.26: cycle_b_papers learned "Simon Lermen Feb 24, 2026 54 5 8
    Share TL;DR: We show that LLM agents can figure out who you are ..." — the
    byline row prefixed the paper's own TL;DR. Strip, never reject: the TL;DR
    is the knowledge. See the module comment for the two measured guards.
    """
    t = (text or "").strip()
    m = _BYLINE_STACK_RE.match(t)
    if not m:
        return t
    rest = t[m.end():].strip()
    return rest if len(rest.split()) >= 5 else t

def _strip_nav_label_stack(text):
    """Drop a leading label-only nav stack that ends at a publisher dateline.

    Live 16.09.26: cycle_g_security learned "SECURITY resources
    Whitepapers/Guides OWASP GenAI LLM Top 10 2026 August 3, 2026 About OWASP
    Top 10 ..." — a section menu welded to a real sentence. Strip, never
    reject: the sentence is the knowledge. The head must be LABEL-LIKE (a
    slash-joined Capitalized pair, no function words, <= 1 lowercase word),
    which is what separates a menu from a sentence beginning with prose.
    """
    t = (text or "").strip()
    m = _NAV_LABEL_STACK_RE.match(t)
    if not m:
        return t
    words = _WORD_RE.findall(m.group("head"))
    low = [w for w in words if w[:1].islower()]
    if len(low) > 1 or any(w.lower() in _NAV_LABEL_FUNC_WORDS for w in low):
        return t                      # prose head -> untouched
    out = m.group("body").strip()
    return out if len(out.split()) >= 5 else t

def _strip_blog_header_stack(text):
    """Drop a leading "<author> / <DATE> / <N> comments" header stack and any
    header-adjacent share widget.

    Live 16.09.26 (cycle_e_competitors): the competitor cycle learned
      "Team / JUN 1, 2026 / 0 comments AI Coding Agents: The Complete Guide to
       Autonomous Software Development (2026) 32 min read Share on Twitter ,
       LinkedIn Software development is undergoing its biggest transformation
       since the invention of version control."
    All three runs are page furniture; the headline between them is what the
    page is about, so STRIP rather than reject (same call as the byline prefix).

    Every rule is structural — a slash-delimited dateline, a share CTA anchored
    to a header marker, a widget-only button label — never a bare voice match,
    so ordinary prose that merely mentions a share or a read time is untouched.
    """
    t = (text or "").strip()
    t = _BLOG_HEADER_STACK_RE.sub("", t).strip()
    t = _SHARE_WIDGET_RE.sub(" ", t)
    t = _LEADING_SHARE_WIDGET_RE.sub(" ", t)
    t = _COPY_LINK_RE.sub(" ", t)
    # Only collapse whitespace when something was actually removed — otherwise
    # an untouched row must come back byte-identical (a blanket re.sub would
    # silently rewrite 6 innocent rows on the live buffer, 16.09.26).
    if t != (text or "").strip():
        t = re.sub(r"\s+", " ", t).strip()
    else:
        t = (text or "").strip()
    # only keep the strip when a real sentence body remains; else leave it alone
    return t if len(t.split()) >= 5 else (text or "").strip()


# Leading MASTHEAD NAV CHAIN welded to the site's own headline (live 17.09.26,
# sixth shape of the leading-chrome family, class 43). cycle_a_technews stored
#
#   "Blog Guides Insights Breaking story Breaking AI News Salesforce Launches
#    Koa: CRM Reasoning Model for Agentforce Salesforce unveils Koa at
#    Dreamforce 2026, a reasoning model trained on 27 years of CRM data that
#    delivers 3x fewer errors on sales tasks."
#
# The site's section menu (Blog / Guides / Insights / Breaking story /
# Breaking AI News) rides in front of the real lede. 251 chars WITH digits ->
# the >=90 length trust AND the technical-signal gate both fired, and every
# existing leading-chrome helper needs a HARD anchor that this row lacks:
#   - _strip_nav_label_stack / _strip_dated_header_slash_stack need a slash,
#   - _strip_blog_header_stack needs a "/ <date> / N comments" stack,
#   - _strip_arrow_nav_prefix needs an HTML-comment arrow,
#   - _is_nav_list wants >= 6 TitleCase tokens with no comma.
# STRIP, never reject: the lede behind the menu IS the knowledge.
#
# The discriminator is a CHAIN of this family's masthead labels, not any single
# one -- each label alone is ordinary English ("Breaking AI News: Anthropic
# ships ...", "Our Breaking AI News desk covers ...", "Blog Guides Insights are
# three content formats ..."). Two-or-more such labels inside the first 80
# chars, with no sentence terminator in front of the last one, is a menu run.
# Measured: 1 hit over the live buffer (= this leak), 0 over 5,582 junk-log
# rows, 3,056 longterm_episodes and the learn/world logs; 0 false positives on
# a 15-sentence hostile control corpus (each bare label, plus comma'd and
# sentence-embedded forms) -- only deliberately chain-shaped controls strip.
_MASTHEAD_NAV_RE = re.compile(
    r"\bBlog\s+Guides\s+Insights\b|\bBreaking\s+AI\s+News\b|\bBreaking\s+story\b|"
    # class 127 (live 21.09.26): a benchmark site's masthead nav pair welded to
    # its own lede. `cycle_c_github` stored
    #   "Aug 10, 2026 See our ethical norms Cite This Benchmark We benchmarked
    #    4 popular open-source agentic frameworks across 2,000 runs ..."
    # -- the KTA cycle then reported `signal NOT mappable` for 46 of 158
    # competitor runs, because the consumer reads the LAST matching row and a
    # nav pair carries no capability token. The lede behind the menu IS the
    # knowledge (a real multi-framework benchmark), so this is a STRIP in the
    # SAME >= 2-labels-in-the-first-80-chars chain form as class 43 -- a bare
    # label alone is ordinary English and must stay learnable.
    #
    # Measured with probe_marker_candidates.py over all 4 corpora: 1 buffer hit
    # and that hit IS the leaking row -> 0 prose FPs, 0 episode FPs, 0 test-
    # literal FPs. Hostile controls that stay byte-identical:
    #   "The paper cites this benchmark as the strongest evidence for ..."
    #   "See our ethical norms page for how we handle user data."
    #   "Cite This Benchmark in your paper and the leaderboard updates ..."
    r"\bSee\s+our\s+ethical\s+norms\b|\bCite\s+This\s+Benchmark\b")


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
_VERDICT_SRC_RE = re.compile(
    r"\b(?:provided|given|supplied|extracted)\s+"
    r"(?:text|document|page|content|snippet|input)\b",
    re.IGNORECASE)
_VERDICT_FURNITURE_RE = re.compile(
    r"\b(?:boilerplate|webpage\s+(?:footer|header)|navigation\s+links?|"
    r"nav(?:igation)?\s+menus?|legal\s+notices?|cookie\s+(?:banner|notice)|"
    r"site\s+furniture|page\s+chrome)\b",
    re.IGNORECASE)
_VERDICT_VERB_RE = re.compile(
    r"\b(?:is|are|appears?\s+to\s+be|consists?\s+of|contains?\s+only|"
    r"contains?\s+no)\b",
    re.IGNORECASE)


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

def _strip_masthead_nav_chain(text):
    """Drop a leading "Blog Guides Insights ... Breaking AI News <lede>" menu run.

    Live 17.09.26 (cycle_a_technews): see the module comment above. Requires
    >= 2 masthead labels inside the first 80 chars and no sentence terminator
    before the LAST one, so real prose that merely names a section is
    untouched. Returns the text byte-identical unless a >= 5-word body remains.
    """
    t = (text or "").strip()
    head = t[:80]
    ms = list(_MASTHEAD_NAV_RE.finditer(head))
    if len(ms) < 2:
        return t
    if re.search(r"[.!?]", head[:ms[-1].start()]):
        return t                      # prose before the labels -> untouched
    rest = t[ms[-1].end():].strip()
    return rest if len(rest.split()) >= 5 else t

def _strip_arrow_nav_prefix(text):
    """Drop a leading nav/breadcrumb run terminated by an HTML-comment arrow.

    Live 16.09.26 (third shape of the same family): the security cycle learned
      "Studies Blogs Contact Arsha --> Posted on May 2, 2025 by admin --> Prompt
       Engineering Is Dead in 2025 Introduction Prompt engineering, once hailed
       as the essential skill ... has become obsolete by 2025."
    `-->` is an HTML comment terminator leaked from the page markup -- real
    prose never contains it, which makes it a precise boundary marker. The
    headline behind the nav is the knowledge, so STRIP rather than reject.

    The arrow must sit in the LEADING chrome region (< 120 chars): an arrow
    deep inside a text is content, not a breadcrumb.
    """
    t = (text or "").strip()
    arrows = [m for m in _ARROW_NAV_RE.finditer(t) if m.start() < 120]
    if not arrows:
        return t
    rest = t[arrows[-1].end():].lstrip()
    rest = _POSTED_BY_RE.sub("", rest).strip()
    return rest if len(rest.split()) >= 5 else t


# Wikipedia/MediaWiki section-edit markup welded to a real paragraph (live
# 16.09.26, leading-chrome family): cycle_g_security stored
#
#   "Publications [ edit ] OWASP Top Ten The \"Top Ten\", first published in
#    2003 and updated periodically (subsequent editions appeared in 2004, 2007,
#    2010, 2013, 2017, 2021 and 2025), is a listing of the most critical
#    application security risks."
#
# The bracket control is page furniture; the sentence behind it IS the
# knowledge, so STRIP rather than reject. NARROW BY CONSTRUCTION -- the
# guards below were each measured against the live 5021-row corpus (buffer
# + junk log), where the bracket marker occurs exactly once, in that row:
#
#   1. the leading section name must be SENTENCE CASE and apostrophe-free
#      (`Publications`, never `Wikipedia's`). A possessive therefore cannot
#      match at all -- which keeps the counter-case
#        "Wikipedia's [ edit ] button is a MediaWiki control, not content;"
#      untouched. A looser first version DID gut it to "button is a
#      MediaWiki control...", which is why this guard exists.
#   2. the body after the marker must OPEN a sentence (uppercase, digit or
#      quote). An edit control is always followed by the article's first
#      sentence, so a lowercase continuation means the text merely MENTIONS
#      an edit button.
#   3. leading position only (re.match) and a >= 5-word body must remain.
#
# The edit word is localized and case-tolerant; guard 1 rests on the name
# rule NOT being case-insensitive.
_WIKI_EDIT_WORD = (
    r"(?:[Ee]dit|[Bb]earbeiten|[Ee]ditieren|[Ss]ource\s+[Ee]dit|[Mm]odifier|"
    r"[Mm]odifica|[Bb]ewerken|[Rr]ediger|[Rr]edigera|[Mm]uokkaa|[Ee]dytuj|"
    r"[Ss]zerkeszt[e\u00e9]s)"
)
_WIKI_SECTION_PREFIX_RE = re.compile(
    r"^\s*(?:[A-Z\d]\w*(?:\s+[a-z]\w*){0,5}\s*)?"
    r"\[+\s*" + _WIKI_EDIT_WORD + r"\s*\]+"
    r"(?=\s*[A-Z\x22\x27\u201c\u2018\d])")


def _strip_wiki_section_prefix(text):
    """Drop a LEADING "<Section> [ edit ]" encyclopedia marker.

    Live 16.09.26: cycle_g_security learned "Publications [ edit ] OWASP
    Top Ten ..." -- the MediaWiki section-edit control prefixed a genuine
    paragraph. Strip, never reject: the paragraph is the knowledge. Leading
    only, and only when a real sentence body (>= 5 words) remains; every
    other shape is returned byte-identical (see the module comment above).
    """
    t = (text or "").strip()
    m = _WIKI_SECTION_PREFIX_RE.match(t)
    if not m:
        return t
    rest = t[m.end():].strip()
    return rest if len(rest.split()) >= 5 else t


def _strip_byline_prefix(text):
    """Remove a leading author/date byline so the body prose is judged alone.

    Live 16.09.26: cycle_f_multi_domain stored the row "Written by Christian
    Gleitze · Published June 11, 2026 · Last reviewed July 23, 2026 AI
    Consciousness asks whether an Artificial Intelligence system could have
    subjective experience, ...". The extractor had legitimately pulled the
    article's opening sentence, but the page's byline prefixed it; at >90 chars
    the "long prose is trusted" rule in _clean_insight never looked closer, so
    page furniture entered the LoRA buffer. Strip rather than reject: the
    knowledge is the sentence AFTER the byline. Only LEADING, byline-shaped
    segments are removed; prose that merely mentions a byline mid-sentence is
    untouched.
    """
    t = (text or "").strip()
    for _ in range(6):
        before = t
        t = _BARE_ATTRIB_RE.sub("", t).strip()
        segs = _BYLINE_SEP_RE.split(t)
        if len(segs) > 1:
            i = 0
            # skip empty segments too: stripping the name above leaves a
            # dangling leading "· " ("· Published June 11, 2026 · ...").
            while i < len(segs) - 1 and (not segs[i].strip() or _ATTRIB_SEG_RE.match(segs[i].strip())):
                i += 1
            if i:
                t = _BYLINE_SEP.join(segs[i:]).strip()
        if t == before:
            break
    return t


def _clean_insight(text, max_len=250):
    """Final gate on a distilled insight. Returns "" for page furniture.

    Live 13.09.26: once the sentence extractor started rejecting chrome, the
    LLM fallback became the last door junk could walk through — it distilled
    the literal "Download PDF Download PDF Review Article Open access Publish".
    Short candidates must therefore carry a technical signal; longer prose
    (>= 90 chars) is trusted on its own merit so non-tech domains survive.
    Live 16.09.26: that length trust let a >90-char byline-PREFIXED row through,
    so the byline is stripped before the text is judged.
    """
    t = (text or "").strip()
    if _URL_ESC_RE.search(t):
        t = urllib.parse.unquote(t).strip()  # judge the decoded words, not %20
    t = _strip_wiki_section_prefix(t)
    t = _strip_dateline_fragment(t)
    t = _strip_nav_label_stack(t)
    t = _strip_dated_header_slash_stack(t)
    t = _strip_byline_stack(t)
    t = _strip_byline_prefix(t)
    t = _strip_clock_fragment(t)
    t = _strip_leading_clock_fragment(t)
    t = _strip_read_time_header(t)
    t = _strip_arrow_nav_prefix(t)
    t = _strip_blog_header_stack(t)
    t = _strip_masthead_nav_chain(t)
    t = _strip_trailing_read_time_header(t)
    if len(t) < 20 or _is_junk(t):
        return ""
    if _is_nav_list(t):
        return ""  # doc-site sidebar/menu, not prose
    if len(t) < 90 and not _has_alpha_signal(t):
        return ""
    return t[:max_len]

def extract_insight(topic, raw, max_tokens=100):
    """Extract insights directly from search results (titles are the signal).
    Falls back to LLM only if direct extraction fails."""
    if not raw or len(raw) < 50:
        return ""
    # search results format: 'Title :: snippet || Title :: snippet || ...'
    parts = [p.strip() for p in raw.split("||") if "::" in p]
    insights = []
    for p in parts[:3]:
        title = p.split("::")[0].strip()
        snippet = p.split("::")[1].strip()[:150]
        if len(title) > 15:
            insights.append(f"{title} — {snippet}")
    out = "; ".join(insights[:2])[:300] if insights else ""
    # Quality gate: a login wall / anti-bot page is NOT knowledge. Reject it so
    # the cycle falls back to deep_learn() instead of buffering page chrome.
    return "" if (not out or _is_junk(out)) else out

def _extract_insight_2b(topic, raw, max_tokens=100):
    try:
        req = urllib.request.Request(LIVE + "/v1/chat/completions",
            data=json.dumps({"model": "mini-openamer", "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content":
                     "Extract ONE actionable insight for an autonomous AI agent. "
                     "Format: [INSIGHT] <sentence>. Be specific and actionable."},
                    {"role": "user", "content": f"Topic: {topic}\n\nInfo: {raw[:1200]}"}
                ]}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=120))
        content = r["choices"][0]["message"]["content"].strip()
        if "[INSIGHT]" in content:
            return content.split("[INSIGHT]")[1].strip()
        return content[:150] if len(content) > 20 else ""
    except Exception:
        return ""

def cycle_a_technews():
    """Tech news: what's new in AI agents? (deep-reads the top result)"""
    queries = ["AI agent news today", "LLM agents breakthrough", "autonomous AI 2026"]
    q = _novel_query("AI agent news", queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)  # fall back to actually reading the page
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Internet learning ({q}): What should an AI agent know?", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"learned: {insight[:80]}"

def cycle_b_papers():
    """New arxiv papers in AI/CL/LG. (deep-reads the abstract page)"""
    queries = [
        "arxiv new papers meta-learning LLM agents 2026",
        "arxiv test-time training state space models 2026",
        "arxiv efficient fine-tuning small language models",
    ]
    q = _novel_query(["arxiv meta-learning LLM agents", "self-improving LLM agents",
                      "arxiv LLM"], queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Latest research insight: {q}", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"paper-learn: {insight[:80]}"

def cycle_c_github():
    """Trending AI-agent repos — what are others building? (deep-reads)"""
    queries = ["github trending AI agent framework 2026",
               "new open source autonomous agent repos"]
    q = _novel_query("open source AI agent framework", queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep("What new agent architectures are trending on GitHub?", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"github-learn: {insight[:80]}"

def cycle_d_docs():
    """Best practices from official documentation. (deep-reads the doc page)"""
    queries = [
        "vLLM optimization best practices",
        "transformers library efficient inference tips",
        "PEFT LoRA training best practices",
    ]
    q = _novel_query("vLLM inference optimization", queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Best practice from official docs: {q}", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"doc-learn: {insight[:80]}"

def cycle_e_competitors():
    """What are competitors building? What can we learn? (deep-reads)"""
    queries = [
        "Devin AI agent new features 2026",
        "OpenHands agent architecture updates",
        "AutoGPT improvements 2026",
    ]
    q = _novel_query("AI coding agent", queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Competitor intelligence: {q}", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    observe_world(f"Competitor update: {q}",
                  f"OpenAmer should evaluate: {insight[:100]}")
    return f"competitor-learn: {insight[:80]}"

def cycle_f_multi_domain():
    """Learn from ANY domain: medicine, law, science, philosophy, business. (deep-reads)"""
    domains = [
        "medical diagnosis AI breakthrough",
        "legal AI automation 2026",
        "physics simulation AI advances",
        "philosophy of consciousness AI",
        "business automation AI agents",
        "climate science AI models",
        "education AI personalization",
        "financial markets AI prediction",
    ]
    d = random.choice(domains)
    q = _novel_query(d, [d])
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Multi-domain learning ({q}): What should an intelligent agent know?", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"domain-learn: {insight[:80]}"

def cycle_g_security():
    """Learn from AI security research — adversarial attacks, guardrails, safety. (deep-reads)"""
    queries = [
        "LLM prompt injection defense techniques 2026",
        "AI agent security vulnerabilities guardrails",
        "jailbreak prevention large language models",
        # Diversified 2026-09-14: the three seeds above saturated (66 duplicate
        # rejects for this cycle in buffer_junk.jsonl, 28 on the prompt-injection
        # seed alone) — the rotation advanced the angle but every (seed, angle)
        # pair had already been learned. New sub-domains give the cycle fresh
        # ground without touching the gates.
        "MCP server tool poisoning attack mitigation",
        "agent sandboxing permission model best practices",
        "AI supply chain model weight backdoor detection",
        "OWASP LLM Top 10 agentic threat model 2026",
    ]
    q = _novel_query("LLM prompt injection security", queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Security learning ({q}): What should a safe agent know?", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"security-learn: {insight[:80]}"


def cycle_h_efficiency():
    """Learn from efficiency research — energy, quantization, small models. (deep-reads)"""
    queries = [
        "small language model energy efficient inference",
        "quantization techniques GGUF int4 int8 comparison",
        "edge AI deployment low power LLM",
    ]
    q = _novel_query(["quantization LLM inference efficiency", "quantization LLM",
                      "GGUF quantization", "energy efficient LLM"], queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    insight = store_or_deep(f"Efficiency learning ({q}): How do agents run leaner?", q, insight)
    if not insight:
        return "rejected, not trained (shallow + deep read both gated)"
    return f"efficiency-learn: {insight[:80]}"


CYCLES = [cycle_a_technews, cycle_b_papers, cycle_c_github,
          cycle_d_docs, cycle_e_competitors, cycle_f_multi_domain,
          cycle_g_security, cycle_h_efficiency]

def next_cycle():
    n = 0
    if os.path.exists(ROT):
        n = int(open(ROT, encoding="utf-8").read().strip() or 0)
    c = CYCLES[n % len(CYCLES)]
    with open(ROT, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    return c

def run_one():
    c = next_cycle()
    t0 = time.time()
    try:
        result = c()
    except Exception as e:
        result = f"error: {str(e)[:100]}"
    elapsed = round(time.time() - t0, 1)
    log({"ts": datetime.datetime.now().isoformat(), "source": c.__name__,
         "result": result, "elapsed_s": elapsed})
    print(f"[internet-learn] {c.__name__}: {result} ({elapsed}s)", flush=True)
    return result

def run_loop(interval=600):
    print(f"[internet-learner] 24/7 loop started: 1 source every {interval}s", flush=True)
    while True:
        try:
            run_one()
        except Exception as e:
            print(f"[internet-learner] loop error: {e}", flush=True)
        time.sleep(interval)

if __name__ == "__main__":
    mode = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else ""
    if mode == "loop":
        run_loop(int(sys.argv[2]) if len(sys.argv) > 2 else 600)
    elif mode == "once":
        run_one()
    else:
        print("=== RUNNING ALL 5 SOURCES ONCE (test) ===")
        for c in CYCLES:
            try:
                print(f"  {c.__name__}: {c()}")
            except Exception as e:
                print(f"  {c.__name__}: ERR {str(e)[:80]}")
