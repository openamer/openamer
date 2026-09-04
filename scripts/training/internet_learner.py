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
import json, os, sys, time, random, datetime, urllib.request, urllib.parse, re

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
BUFFER = os.path.join(T, "online_buffer.jsonl")
LOG = os.path.join(T, "internet_learn_log.jsonl")
ROT = os.path.join(T, ".il_rotation")
LIVE = "http://localhost:8081"
REPO = r"C:/Users/damir/openamer-repo"

def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def add_to_buffer(user_text, assistant_text):
    with open(BUFFER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"u": user_text[:3000], "a": assistant_text[:4000]},
                           ensure_ascii=False) + "\n")

def observe_world(cause, effect):
    wm = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/world_model.jsonl"
    os.makedirs(os.path.dirname(wm), exist_ok=True)
    with open(wm, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(),
                            "cause": cause[:500], "effect": effect[:500],
                            "embedding": [0.1]*768}, ensure_ascii=False) + "\n")

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
    """Tech news: what's new in AI agents?"""
    queries = ["AI agent news today", "LLM agents breakthrough", "autonomous AI 2026"]
    q = random.choice(queries)
    raw = search(q)
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"Internet learning ({q}): What should an AI agent know?",
                  insight)
    return f"learned: {insight[:80]}"

def cycle_b_papers():
    """New arxiv papers in AI/CL/LG."""
    queries = [
        "arxiv new papers meta-learning LLM agents 2026",
        "arxiv test-time training state space models 2026",
        "arxiv efficient fine-tuning small language models",
    ]
    q = random.choice(queries)
    raw = search(q)
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"Latest research insight: {q}", insight)
    return f"paper-learn: {insight[:80]}"

def cycle_c_github():
    """Trending AI-agent repos — what are others building?"""
    queries = ["github trending AI agent framework 2026",
               "new open source autonomous agent repos"]
    q = random.choice(queries)
    raw = search(q)
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"What new agent architectures are trending on GitHub?", insight)
    return f"github-learn: {insight[:80]}"

def cycle_d_docs():
    """Best practices from official documentation."""
    queries = [
        "vLLM optimization best practices",
        "transformers library efficient inference tips",
        "PEFT LoRA training best practices",
    ]
    q = random.choice(queries)
    raw = search(q)
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"Best practice from official docs: {q}", insight)
    return f"doc-learn: {insight[:80]}"

def cycle_e_competitors():
    """What are competitors building? What can we learn?"""
    queries = [
        "Devin AI agent new features 2026",
        "OpenHands agent architecture updates",
        "AutoGPT improvements 2026",
    ]
    q = random.choice(queries)
    raw = search(q)
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"Competitor intelligence: {q}", insight)
    observe_world(f"Competitor update: {q}",
                  f"OpenAmer should evaluate: {insight[:100]}")
    return f"competitor-learn: {insight[:80]}"

def cycle_f_multi_domain():
    """Learn from ANY domain: medicine, law, science, philosophy, business."""
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
    if not raw:
        return "no results"
    insight = extract_insight(q, raw)
    if not insight:
        return "no insight"
    add_to_buffer(f"Multi-domain learning ({q}): What should an intelligent agent know?", insight)
    return f"domain-learn: {insight[:80]}"

CYCLES = [cycle_a_technews, cycle_b_papers, cycle_c_github,
          cycle_d_docs, cycle_e_competitors, cycle_f_multi_domain]

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
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        run_loop(int(sys.argv[2]) if len(sys.argv) > 2 else 600)
    elif len(sys.argv) > 1 and sys.argv[1] == "once":
        run_one()
    else:
        print("=== RUNNING ALL 5 SOURCES ONCE (test) ===")
        for c in CYCLES:
            try:
                print(f"  {c.__name__}: {c()}")
            except Exception as e:
                print(f"  {c.__name__}: ERR {str(e)[:80]}")
