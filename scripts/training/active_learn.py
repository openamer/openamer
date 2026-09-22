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
import os
import json, os, re, sys, time, random, datetime, urllib.request, subprocess
from pathlib import Path
sys.path.insert(0, os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts"))
sys.path.insert(0, os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training"))

T = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training")
BUFFER = os.path.join(T, "online_buffer.jsonl")
LIVE = "http://localhost:8081"
ROTATION_FILE = os.path.join(T, ".learn_rotation")

def chat(messages, max_tokens=200):
    # Follows the configured default model (config.yaml model.default).
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from model_config import chat_default
    return chat_default(messages, max_tokens=max_tokens)

def add_to_buffer(user_text, assistant_text):
    # Single source of truth: append + enforce cap on EVERY write.
    import buffer_store
    return buffer_store.append(user_text, assistant_text, buffer=BUFFER)

def store_if_trainable(user_text, assistant_text):
    """Write only what the writer gate will actually accept. True on a real append.

    Measured 2026-09-22: active_learn.self_test buffered its OWN reasoning trace
    (`<answer>\\n\\nSelf-critique: <critique>`). `Self-critique` is a
    reasoning-trace marker in buffer_store._JUNK_MARKERS, so the writer refused
    every one of those writes — 167 of 600 audited junk rejections, and because
    the refusal is silent the action still reported "self-test: good". One third
    of the whole learner's gate loss came from this single call site.

    The success test mirrors internet_learner.store: a real append can leave the
    line count unchanged once the buffer is at MAX_BUF (enforce_cap trims it
    back), so count growth alone is not proof — fall back to a presence check.
    """
    import buffer_store
    txt = (assistant_text or "").strip()
    if not txt or buffer_store.is_junk(txt):
        return False
    n_before = buffer_store.count(BUFFER)
    add_to_buffer(user_text, txt)
    if buffer_store.count(BUFFER) > n_before:
        return True
    rec = {"u": (user_text or "")[:3000], "a": txt[:4000]}
    try:
        return bool(buffer_store._is_duplicate(rec, BUFFER))
    except Exception:
        return False

def observe_world(cause, effect):
    """Write through the central world model (single source of truth)."""
    import world_model
    return world_model.observe(cause, effect)

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
            insight = _strip_reasoning_trace(learning.split("[INSIGHT]")[1].strip())
            # Report the REAL outcome: a silent REFUSAL of the writer gate must
            # not be reported as "web-learn: <insight>" (measured 2026-09-22).
            if not store_if_trainable(f"What did you learn about {topic}?",
                                      f"Key insight: {insight}"):
                return f"web-learn: not buffered ({len(insight)} chars gated)"
            return f"web-learn: {insight[:80]}"
        return "no insight extracted"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def _strip_reasoning_trace(text):
    """Drop the answer's own reasoning-trace tail so the row is trainable.

    2026-09-22: the 2B model appends "Self-critique: ..." / "[GOOD]" /
    "[NEEDS_IMPROVEMENT] ..." to its answers. Those strings are junk markers in
    buffer_store, so the whole row was refused. The substance is the ANSWER; the
    critique is scaffolding. Cut at the first marker so the real prose survives.
    """
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    cut = len(t)
    for mk in ("self-critique", "self critique", "[good]", "[needs_improvement]",
               "[needs improvement]", "analyze user input", "thinking process"):
        i = low.find(mk)
        if i != -1:
            cut = min(cut, i)
    return t[:cut].strip(" \n\t-—:")

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
        # self-critique — kept for the status signal, NOT written to the buffer:
        # it is the learner's own reasoning trace, not world knowledge.
        critique = chat([
            {"role": "user", "content":
             f"Question: {q}\nAnswer: {answer}\n\n"
             "Critique this answer: is it accurate? complete? what's missing? "
             "Reply with [GOOD] or [NEEDS_IMPROVEMENT]: <specific issue>."}],
            max_tokens=100)
        # Buffer the ANSWER alone (trace stripped). Report honestly: if the
        # writer still refuses it, say so instead of claiming "good".
        clean = _strip_reasoning_trace(answer)
        stored = store_if_trainable(q, clean)
        status = "good" if "[GOOD]" in critique else "needs-improvement"
        if not stored:
            return (f"self-test: {status} on '{q[:40]}' — not buffered "
                    f"(answer untrainable, {len(clean)} chars)")
        return f"self-test: {status} on '{q[:50]}'"
    except Exception as e:
        return f"error: {str(e)[:100]}"

def world_explore():
    """Find new cause-effect pairs from system logs and recent errors."""
    # Known-benign patterns that are NOT real errors — filtering these out
    # stops the world model from being polluted with false "system errors".
    BENIGN = (
        "llama.cpp", "llama-server", "localhost:8080", "WinError 10061",
        "Verbindung konnte nicht hergestellt", "Nicht verfügbar",
        "kein API-Key gefunden", "OPENROUTER_API_KEY", "OPENAI_API_KEY",
        # autopilot/self-rewriter trial status lines: waiting trials are
        # progress reports, not errors (64 false edges in one night)
        "[autopilot]", "self_rewriter", "trial fb69", "trial self_rewriter",
        "Trials:", "wartend", "wartet",
        # documentation/help lines that merely contain the word "error"
        # (measured 2026-09-10: ~90% of cron-output 'error' hits were these)
        "run the active learning loop", "run the autonomous swarm",
        "syntaxerror-scan", "echter error-output", "bei problemen",
        "self-healing daemon", "fehlerpfad", "connect_err",
        "trial status", "waiting {'completed'", "waiting {",
        "self-healer.py", "scannt alle .py",
        # cron reports ABOUT our own learners (world_explore counts, trial
        # tables, timeout watchdogs) — the monitor, not the failure
        "active-learn", "active-learn-loop", "world_explore:", "world-explore:",
        "0 completed, 0 error", "completed/error", "— ⏳ waiting",
        "cron job 'online-learning-watchdog'", "idle for 601s",
        "kein error", "button wird nicht gerendert",
        "alle 5 aktionen", "5/5 actions", "aktiv-lern-loop", "tool-server :8081",
    )
    try:
        # REAL failure source: cron scheduler job status (exit codes), not
        # text-mining of report files. Measured 2026-09-10: ~95% of
        # output-line matches were docs/monitor content, not failures.
        jobs_path = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "cron", "jobs.json")
        recent_errors = []
        try:
            data = json.load(open(jobs_path, encoding="utf-8"))
            jobs = data.get("jobs") if isinstance(data, dict) else data
            for j in jobs or []:
                if (j.get("last_status") or "").lower() in ("error", "failed"):
                    err = str(j.get("last_error", ""))[:180] or j.get("name", "?")
                    recent_errors.append(f"{j.get('name')}: {err}")
        except Exception:
            pass  # no jobs.json -> fall through to synthetic patterns
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

# An instruction ECHO is this loop buffering its own prompt back at itself
# instead of an answer. Anchored + imperative, mirroring the rule already in
# internet_learner._INSTRUCTION_OPENER_RE: the bare topic phrase cannot be
# gated because the genuine declarative answers ("The shared underlying
# pattern is a closed-loop feedback system ...") must stay learnable.
_ECHO_OPENER_RE = re.compile(
    r"^\s*\**\s*(?:need\b|task\s*:|goal\s*:|ask\s*:|user\s+asks\s*:|"
    # SIXTH echo shape (live 16.09.26): the model returned the prompt as
    # `Question: Find structural connection between these two situations.`
    # Mirrors buffer_store._ECHO_QUESTION_RE; genuine declaratives survive.
    r"question\s*:\s*(?:find|identify|what|how|why)\b|"
    r"find\s+(?:the\s+)?(?:structural\s+)?connection|"
    r"identify\s+(?:the\s+)?(?:shared\s+)?(?:underlying\s+)?pattern|"
    r"they\s+want\s+me\s+to|"
    # Prompt-echo, third shape (live 16.09.26): the cross_connect loop
    # buffered its OWN numbered prompt back at itself --
    # `Situation 2 learning process: Continuous Learning Loop: error capture
    # + categorization + memory + auto-skill generation + trend.` and the
    # quoted variant `Situation 1: "learning process: ..." German: ...`.
    # Anchored on the NUMBERED PROMPT MARKER + a topic word or colon, so the
    # genuine declarative answers survive: measured 2/2 leaks caught and 0/5
    # real answers killed -- `Situation 1 and situation 2 share a common
    # failure mode ...` and `The shared underlying pattern is ...` both pass.
    r"situation\s*\d\s*(?::|\b(?:learning|system|energy|tool)\b)|"
    r"what\s+(?:is\s+)?(?:the\s+)?(?:shared|structural))",
    re.IGNORECASE)

# Prompt-echo, FOURTH shape (live 16.09.26): cross_connect buffered its own
# `... + Trend\n\nWhat is the shared underlying pattern?` tail and the bare
# 26-char `Shared underlying pattern?` -- both just clear the 25-char floor and
# neither starts with a prompt opener, so the anchored rule above misses them.
# A TAIL rule (the question at the END of the text) catches both while leaving
# the genuine declarative ("The shared underlying pattern is a closed-loop
# feedback system ...") and rhetorical uses ("... pattern behind vLLM's chunked
# prefill?") untouched.
_ECHO_TAIL_RE = re.compile(
    r"(?:what\s+is\s+the\s+)?shared\s+underlying\s+pattern\s*\??\s*$",
    re.IGNORECASE)
# Fifth shape (16.09.26): the numberered `**Identify the Goal:**` extraction
# template of the 2B model. Mirrors buffer_store._ECHO_TEMPLATE_RE.
_ECHO_TEMPLATE_RE = re.compile(
    r"identify\s+the\s+goal\s*:|the\s+insight\s+should\s+be",
    re.IGNORECASE)


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
            # A failed or truncated generation must NOT enter the training
            # buffer (live 16.09.26: 5 empty rows, a 1-char "S" and two stub
            # fragments reached online_buffer.jsonl here, because chat()
            # returns "" on failure and its value was buffered unvalidated).
            _ins = _strip_reasoning_trace(insight)
            if (len(_ins) < 25 or _ECHO_OPENER_RE.match(_ins)
                    or _ECHO_TAIL_RE.search(_ins)
                    or _ECHO_TEMPLATE_RE.search(_ins)):
                return f"cross-connect: discarded stub/echo ({len(_ins)} chars)"
            # Same honesty rule as web_learn/self_test: the writer gate can
            # still refuse this row; report the refusal, don't log a success.
            if not store_if_trainable(f"Structural connection between {t1} and {t2}?", _ins):
                return f"cross-connect: not buffered (gated, {len(_ins)} chars)"
            return f"cross-connect: {_ins[:80]}"
        return "cross-connect: not enough memories"
    except Exception as e:
        return f"error: {str(e)[:100]}"

# ---- Rotation ----
ACTIONS = [web_learn, self_test, world_explore, skill_challenge, cross_connect]

def get_next_action():
    """Round-robin through actions."""
    n = 0
    if os.path.exists(ROTATION_FILE):
        n = int(open(ROTATION_FILE, encoding="utf-8").read().strip() or 0)
    action = ACTIONS[n % len(ACTIONS)]
    with open(ROTATION_FILE, "w", encoding="utf-8") as f:
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
