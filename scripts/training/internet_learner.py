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

def add_to_buffer(user_text, assistant_text):
    with open(BUFFER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"u": user_text[:3000], "a": assistant_text[:4000]},
                           ensure_ascii=False) + "\n")

def observe_world(cause, effect):
    """Write through the central world model (single source of truth)."""
    import world_model
    return world_model.observe(cause, effect)

def search(query, k=3):
    """Web search via the tool server (CDP browser)."""
    try:
        req = urllib.request.Request(LIVE + "/execute_tool",
            data=json.dumps({"tool": "web_search", "params": {"query": query}}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=90))
        return r.get("result", {}).get("results", "")[:2000]
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
            "hub python bibliothek", "alle docs", "bersicht", "übersicht")
    for t in texts:
        for m in re.finditer(r"([A-Z][^.!?]{40,250}[.!?])", t):
            s = m.group(1).strip()
            low = s.lower()
            if any(n in low for n in _NAV):
                continue  # skip navigation/boilerplate
            # skip sentences that are mostly link-lists (many "›" separators)
            if s.count("›") > 0 or s.count("&amp;") > 1:
                continue
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
        return content[:250] if len(content) > 20 else ""
    except Exception:
        # fallback: local 4B via Ollama (background task, speed irrelevant)
        try:
            req = urllib.request.Request("http://localhost:11434/api/generate",
                data=json.dumps({"model": "qwen3.5:4b-q4_K_M",
                    "prompt": f"Summarize the key technical insight from this in ONE sentence "
                              f"(no preamble, just the sentence):\n\n{combined}",
                    "stream": False}).encode(),
                headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=600))
            content = r.get("response", "").strip()
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1].strip()
            return content[:200] if len(content) > 20 else ""
        except Exception:
            return ""

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
    return "; ".join(insights[:2])[:300] if insights else ""

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
    add_to_buffer(f"Internet learning ({q}): What should an AI agent know?",
                  insight)
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
    add_to_buffer(f"Latest research insight: {q}", insight)
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
    add_to_buffer(f"What new agent architectures are trending on GitHub?", insight)
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
    add_to_buffer(f"Best practice from official docs: {q}", insight)
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
    add_to_buffer(f"Competitor intelligence: {q}", insight)
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
    add_to_buffer(f"Multi-domain learning ({q}): What should an intelligent agent know?", insight)
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
    add_to_buffer(f"Security learning ({q}): What should a safe agent know?", insight)
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
    add_to_buffer(f"Efficiency learning ({q}): How do agents run leaner?", insight)
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
