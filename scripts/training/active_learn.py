#!/usr/bin/env python3
"""Active Learning Loop — the agent actively seeks knowledge, doesn't wait.

Runs every 10 min and performs ONE learning action from a rotation:
  1. WEB-LEARN: Search for new AI developments, extract insights
  2. SELF-TEST: Ask itself questions, verify answers with recursive loop
  3. WORLD-EXPLORE: Find new cause-effect pairs from system logs
  4. SKILL-CHALLENGE: Test a random skill and record results
  5. CROSS-CONNECT: Find analogies between unrelated memories

Each action feeds results into: brain buffer + world model + structures.
The agent GROWS actively instead of waiting passively.
"""
import json, os, sys, time, random, datetime, urllib.request, subprocess
sys.path.insert(0, r"C:/Users/damir/AppData/Local/openamer-laptop/scripts")
sys.path.insert(0, r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training")

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
BUFFER = os.path.join(T, "online_buffer.jsonl")
LIVE = "http://localhost:8081"
ROTATION_FILE = os.path.join(T, ".learn_rotation")

def chat(messages, max_tokens=200):
    req = urllib.request.Request(LIVE + "/v1/chat/completions",
        data=json.dumps({"model": "mini-openamer", "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return r["choices"][0]["message"]["content"].strip()

def add_to_buffer(user_text, assistant_text):
    with open(BUFFER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"u": user_text[:3000], "a": assistant_text[:4000]},
                           ensure_ascii=False) + "\n")

def observe_world(cause, effect):
    wm = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/world_model.jsonl"
    os.makedirs(os.path.dirname(wm), exist_ok=True)
    edge = {"ts": datetime.datetime.now().isoformat(),
            "cause": cause[:500], "effect": effect[:500], "embedding": [0.1]*768}
    with open(wm, "a", encoding="utf-8") as f:
        f.write(json.dumps(edge, ensure_ascii=False) + "\n")

# ---- Learning Actions ----

def web_learn():
    """Search for new AI developments and extract learnings."""
    topics = [
        "AI agent architecture 2026",
        "energy efficient LLM inference",
        "small language model fine-tuning",
        "agentic AI frameworks",
        "neuromorphic computing AI",
    ]
    topic = random.choice(topics)
    try:
        # search via tool server
        req = urllib.request.Request(LIVE + "/execute_tool",
            data=json.dumps({"tool": "web_search", "params": {"query": topic}}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        results = r.get("result", {}).get("results", "")[:800]
        if not results:
            return "no results"
        # extract learning via the model
        learning = chat([
            {"role": "system", "content":
             "Extract ONE key insight from these search results. "
             "Format: [INSIGHT] <one sentence>. Focus on actionable knowledge."},
            {"role": "user", "content": f"Topic: {topic}\nResults: {results}"}],
            max_tokens=100)
        if "[INSIGHT]" in learning:
            insight = learning.split("[INSIGHT]")[1].strip()
            add_to_buffer(f"What did you learn about {topic}?",
                         f"Key insight: {insight}")
            return f"web-learn: {insight[:80]}"
        return "no insight extracted"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def self_test():
    """Ask itself a question and verify the answer with recursive loop."""
    questions = [
        "What are the most common causes of system failures in distributed AI systems?",
        "How does energy efficiency relate to intelligence scalability?",
        "What is the difference between correlation and causation in system diagnostics?",
        "Explain how sleep consolidation improves memory in biological and artificial systems.",
        "What makes a self-improving system safe?",
    ]
    q = random.choice(questions)
    try:
        # initial answer
        answer = chat([{"role": "user", "content": q}], max_tokens=150)
        # self-critique
        critique = chat([
            {"role": "user", "content":
             f"Question: {q}\nAnswer: {answer}\n\n"
             "Critique this answer: is it accurate? complete? what's missing? "
             "Reply with [GOOD] or [NEEDS_IMPROVEMENT]: <specific issue>."}],
            max_tokens=100)
        # add both to buffer as learning example
        add_to_buffer(q, f"{answer}\n\nSelf-critique: {critique}")
        status = "good" if "[GOOD]" in critique else "needs-improvement"
        return f"self-test: {status} on '{q[:50]}'"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def world_explore():
    """Find new cause-effect pairs from system logs and recent errors."""
    try:
        # scan recent cron outputs for errors
        output_dir = r"C:/Users/damir/AppData/Local/openamer-laptop/cron/output"
        recent_errors = []
        now = time.time()
        for jdir in os.listdir(output_dir):
            jpath = os.path.join(output_dir, jdir)
            if not os.path.isdir(jpath):
                continue
            for f in os.listdir(jpath):
                fp = os.path.join(jpath, f)
                if os.path.getmtime(fp) > now - 3600:  # last hour
                    content = open(fp, encoding="utf-8", errors="replace").read()
                    if "error" in content.lower() or "failed" in content.lower():
                        # extract cause-effect
                        for line in content.splitlines():
                            if "error" in line.lower() or "failed" in line.lower():
                                recent_errors.append(line.strip()[:200])
        if not recent_errors:
            # generate a synthetic learning from known patterns
            patterns = [
                ("High memory usage in long-running process",
                 "Process should implement periodic cleanup or use streaming"),
                ("Network timeout on external API",
                 "Implement exponential backoff with jitter"),
                ("Race condition in concurrent access",
                 "Add proper locking or use atomic operations"),
            ]
            cause, effect = random.choice(patterns)
            observe_world(cause, effect)
            return f"world-explore: synthetic pattern ({cause[:40]})"
        # record real errors as world-model edges
        err = random.choice(recent_errors[:5])
        observe_world(f"System error: {err[:100]}",
                     "Needs investigation and root-cause fix")
        return f"world-explore: recorded {len(recent_errors)} recent errors"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def skill_challenge():
    """Test a random skill and record performance."""
    try:
        skills = [
            ("reason_deep", {"question": "What are the tradeoffs between speed and accuracy in AI systems?"}),
            ("run_python", {"code": "import math; print(round(math.pi * 100, 2))"}),
            ("read_memory", {"query": "system repair"}),
            ("web_search", {"query": "latest AI agent developments"}),
        ]
        tool, params = random.choice(skills)
        req = urllib.request.Request(LIVE + "/execute_tool",
            data=json.dumps({"tool": tool, "params": params}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=120))
        result = r.get("result", {})
        success = "error" not in result
        return f"skill-challenge: {tool} -> {'PASS' if success else 'FAIL'}"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def cross_connect():
    """Find analogies between unrelated memories."""
    try:
        from longterm_memory import query
        topics = ["system failure", "learning process", "energy efficiency", "tool usage"]
        t1, t2 = random.sample(topics, 2)
        r1 = query(t1, k=1)
        r2 = query(t2, k=1)
        if r1 and r2:
            insight = chat([
                {"role": "user", "content":
                 f"Find the structural connection between these two situations:\n\n"
                 f"1. {t1}: {r1[0][1]['text'][:200]}\n\n"
                 f"2. {t2}: {r2[0][1]['text'][:200]}\n\n"
                 f"What is the shared underlying pattern? One sentence."}],
                max_tokens=80)
            add_to_buffer(f"Structural connection between {t1} and {t2}?", insight)
            return f"cross-connect: {insight[:80]}"
        return "cross-connect: not enough memories"
    except Exception as e:
        return f"error: {str(e)[:100]}"

# ---- Rotation ----
ACTIONS = [web_learn, self_test, world_explore, skill_challenge, cross_connect]

def get_next_action():
    """Round-robin through actions."""
    n = 0
    if os.path.exists(ROTATION_FILE):
        n = int(open(ROTATION_FILE).read().strip() or 0)
    action = ACTIONS[n % len(ACTIONS)]
    with open(ROTATION_FILE, "w") as f:
        f.write(str(n + 1))
    return action

def run_one():
    action = get_next_action()
    start = time.time()
    try:
        result = action()
    except Exception as e:
        result = f"error: {str(e)[:100]}"
    elapsed = round(time.time() - start, 1)
    print(f"[active-learn] {action.__name__}: {result} ({elapsed}s)", flush=True)
    return result

def run_loop(interval=600):
    print(f"[active-learn] starting: 1 action every {interval}s", flush=True)
    while True:
        run_one()
        time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        run_loop()
    elif len(sys.argv) > 1 and sys.argv[1] == "once":
        run_one()
    else:
        # run all 5 once for testing
        for a in ACTIONS:
            try:
                r = a()
                print(f"  {a.__name__}: {r}")
            except Exception as e:
                print(f"  {a.__name__}: ERR {str(e)[:80]}")
