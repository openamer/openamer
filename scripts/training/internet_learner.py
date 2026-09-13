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

T = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training")
BUFFER = os.path.join(T, "online_buffer.jsonl")
LOG = os.path.join(T, "internet_learn_log.jsonl")
ROT = os.path.join(T, ".il_rotation")
LIVE = "http://localhost:8081"
REPO = os.path.join(str(Path.home()), "openamer-repo")

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
    try:
        before = buffer_store.count(buf)
        after = buffer_store.append(user_text, cleaned, buffer=buf)
    except Exception as e:
        print(f"[internet-learn] buffer write failed: {e}", flush=True)
        return False
    return after > before


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
    r"przepisy|kuchnia|inspiracje|porady|dania na grilla)",
    re.IGNORECASE)

# Percent-escapes mean the "insight" is a URL fragment, not prose. Their digits
# would otherwise satisfy the technical-signal gate (live 13.09.26).
_URL_ESC_RE = re.compile(r"%(?:[0-9A-Fa-f]{2})")


def _is_junk(text):
    """True if `text` looks like boilerplate rather than actual content."""
    t = (text or "").strip()
    if len(t) < 25:
        return True
    return bool(_JUNK_RE.search(t))


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
            if urls:
                return urls[:k]
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
            if not _looks_like_content(s):
                continue  # page furniture, not a learning signal
            return s
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
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)  # fall back to actually reading the page
    if not insight:
        return "no insight"
    if not store(f"Internet learning ({q}): What should an AI agent know?", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"learned: {insight[:80]}"

def cycle_b_papers():
    """New arxiv papers in AI/CL/LG. (deep-reads the abstract page)"""
    queries = [
        "arxiv new papers meta-learning LLM agents 2026",
        "arxiv test-time training state space models 2026",
        "arxiv efficient fine-tuning small language models",
    ]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Latest research insight: {q}", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"paper-learn: {insight[:80]}"

def cycle_c_github():
    """Trending AI-agent repos — what are others building? (deep-reads)"""
    queries = ["github trending AI agent framework 2026",
               "new open source autonomous agent repos"]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store("What new agent architectures are trending on GitHub?", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"github-learn: {insight[:80]}"

def cycle_d_docs():
    """Best practices from official documentation. (deep-reads the doc page)"""
    queries = [
        "vLLM optimization best practices",
        "transformers library efficient inference tips",
        "PEFT LoRA training best practices",
    ]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Best practice from official docs: {q}", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"doc-learn: {insight[:80]}"

def cycle_e_competitors():
    """What are competitors building? What can we learn? (deep-reads)"""
    queries = [
        "Devin AI agent new features 2026",
        "OpenHands agent architecture updates",
        "AutoGPT improvements 2026",
    ]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Competitor intelligence: {q}", insight):
        return f"rejected, not trained ({insight[:60]})"
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
    q = random.choice(domains)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Multi-domain learning ({q}): What should an intelligent agent know?", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"domain-learn: {insight[:80]}"

def cycle_g_security():
    """Learn from AI security research — adversarial attacks, guardrails, safety. (deep-reads)"""
    queries = [
        "LLM prompt injection defense techniques 2026",
        "AI agent security vulnerabilities guardrails",
        "jailbreak prevention large language models",
    ]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Security learning ({q}): What should a safe agent know?", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"security-learn: {insight[:80]}"


def cycle_h_efficiency():
    """Learn from efficiency research — energy, quantization, small models. (deep-reads)"""
    queries = [
        "small language model energy efficient inference",
        "quantization techniques GGUF int4 int8 comparison",
        "edge AI deployment low power LLM",
    ]
    q = random.choice(queries)
    raw = search(q)
    insight = extract_insight(q, raw) if raw else ""
    if not insight:
        insight = deep_learn(q)
    if not insight:
        return "no insight"
    if not store(f"Efficiency learning ({q}): How do agents run leaner?", insight):
        return f"rejected, not trained ({insight[:60]})"
    return f"efficiency-learn: {insight[:80]}"


CYCLES = [cycle_a_technews, cycle_b_papers, cycle_c_github,
          cycle_d_docs, cycle_e_competitors, cycle_f_multi_domain,
          cycle_g_security, cycle_h_efficiency]

def next_cycle():
    n = 0
    if os.path.exists(ROT):
        n = int(open(ROT).read().strip() or 0)
    c = CYCLES[n % len(CYCLES)]
    with open(ROT, "w") as f:
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
