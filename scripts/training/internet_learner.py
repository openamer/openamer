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
    r"przepisy|kuchnia|inspiracje|porady|dania na grilla|"
    # HuggingFace docs sidebar nav (live 14.09.26: the docs cycle stored the
    # verbatim product-label list "Inference Providers Kernels LeRobot
    # Leaderboards … Tokenizers Trackio Transformers". At 200 chars it cleared
    # the >=90 length trust, so it needs its own narrow signature.)
    r"inference providers kernels|lerobot leaderboards|reachy mini|"
    r"openenv optimum|tokenizers trackio|"
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
    r"Code Issues Pull requests|"
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
    r'"wt":"',
    re.IGNORECASE)

# Percent-escapes mean the "insight" is a URL fragment, not prose. Their digits
# would otherwise satisfy the technical-signal gate (live 13.09.26).
_URL_ESC_RE = re.compile(r"%(?:[0-9A-Fa-f]{2})")


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


def _is_junk(text):
    """True if `text` looks like boilerplate rather than actual content."""
    t = (text or "").strip()
    if len(t) < 25:
        return True
    if _looks_binary(t):
        return True
    if _JUNK_RE.search(t):
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


def _usable_urls(urls, k):
    """Keep only fetchable result URLs (drop bare domains and known stubs)."""
    good = []
    for u in urls:
        path = re.sub(r"^https?://[^/]+", "", u).strip("/")
        if path and path not in _URL_STUB_PATHS:
            good.append(u)
    return good[:k]


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
            if good:
                return good
        except Exception:
            pass
        # FALLBACK: direct HTTP with ck/a redirect decode
        req = urllib.request.Request(f"https://www.bing.com/search?q={q}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
        raw = _html.unescape(raw)
        urls = []
        seen = set()
        for m in re.finditer(r"href=\"(https://www\.bing\.com/ck/a\?[^\"]+)\"", raw):
            dec = _decode_bing_url(m.group(1))
            if dec.startswith("http") and "microsoft" not in dec and dec not in seen:
                seen.add(dec)
                urls.append(dec)
        return urls[:k]
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
        if len(t) > 200:
            texts.append(t)
    if not texts:
        return ""
    combined = " ".join(texts)[:4000]
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


def _clean_insight(text, max_len=250):
    """Final gate on a distilled insight. Returns "" for page furniture.

    Live 13.09.26: once the sentence extractor started rejecting chrome, the
    LLM fallback became the last door junk could walk through — it distilled
    the literal "Download PDF Download PDF Review Article Open access Publish".
    Short candidates must therefore carry a technical signal; longer prose
    (>= 90 chars) is trusted on its own merit so non-tech domains survive.
    """
    t = (text or "").strip()
    if _URL_ESC_RE.search(t):
        t = urllib.parse.unquote(t).strip()  # judge the decoded words, not %20
    if len(t) < 20 or _is_junk(t):
        return ""
    if _is_nav_list(t):
        return ""  # doc-site sidebar/menu, not prose
    if len(t) < 90 and not _looks_like_content(t):
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
