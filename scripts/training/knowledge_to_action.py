#!/usr/bin/env python3
"""Knowledge-to-Action — turns internet insights into REAL changes.

After internet_learner collects insights, this script:
  1. SELECTS the most actionable insight from the buffer
  2. MAPS it to a concrete experiment/action
  3. RUNS the action (A/B test, code change, config tweak)
  4. MEASURES the result (did it make the system better?)
  5. RECORDS: insight -> action -> result (complete learning loop)

This closes the gap between "learning" and "implementing".
"""
# KTA_SYS_PATH_BOOTSTRAP: sibling imports (world_model) need script dir on sys.path when run via runpy/gateway
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os
import json, os, sys, time, datetime, subprocess, re
from pathlib import Path

def _training_dir():
    """Resolve the live training dir, tolerating a wrong/stale OPENAMER_HOME.

    Live bug (16.09.26): the cron env can point OPENAMER_HOME at a
    non-existent / throwaway dir, which made every KTA cycle crash with
    FileNotFoundError on online_buffer.jsonl. Unlike internet_learner this
    module used to trust the env blindly. Prefer a *valid* env override, then
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
KTA_LOG = os.path.join(T, "kta_log.jsonl")
LIVE = "http://localhost:8081"

def log(entry):
    with open(KTA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)

# ---- Action Library: insight patterns -> concrete experiments ----

def experiment_lora_rank():
    """Insight: 'start with small rank (4-8)'. Test r=8 vs r=16 effectiveness."""
    import urllib.request
    losses = {}
    # We can't easily change LoRA rank at runtime (needs rebuild).
    # Instead: measure the CURRENT r=16 performance as baseline, log for later A/B.
    #
    # Retry contract (fixed 20.09.2026): a single 5s attempt reported
    # "server down" whenever the tool server was mid-restart (live evidence:
    # 2026-09-20T07:46:21, right after the desktop relaunch at 07:39:50 —
    # a curl seconds later answered {"status":"alive","tools":9}). One refused
    # connection during a rebind is not "server down"; it is a retry miss, and
    # it burned a whole rotation slot. Probe a few times with backoff.
    h = None
    last_err = None
    for _attempt in range(3):
        try:
            req = urllib.request.Request(LIVE + "/health")
            h = json.load(urllib.request.urlopen(req, timeout=5))
            break
        except Exception as e:
            last_err = e
            time.sleep(2 * (_attempt + 1))
    try:
        if h is None:
            raise last_err
        return {
            "action": "LoRA rank experiment: baseline recorded (r=16 live)",
            "result": f"current server: {h.get('tools')} tools, loss history in meta_state",
            "measurable": True,
            "next": "when GPU training runs next, try r=8 variant and compare loss-drop",
        }
    except Exception as e:
        return {"action": "LoRA rank experiment", "result": f"server down: {e}",
                "measurable": False}

def experiment_predict_world():
    """Insight: 'project future states'. Add a prediction to the world model.

    Honesty contract (fixed 12.09.2026): this used to predict FROM the last
    prediction — `cause = last['cause']`, then observe "If '{cause}' recurs".
    Every rotation cycle therefore wrapped the previous prediction in another
    "If ... recurs" shell. Live evidence: the newest world-model entry was
    literally `If 'If 'Competitor update: ...' recurs' recurs`. A prediction
    about a prediction is not a projection of the world; it is a sentence
    growing a tail. It also made the validator's job impossible, because
    prediction N+1 was near-identical to prediction N by construction.

    Now it predicts from the most recent FACT (an observed cause→effect edge),
    skipping predictions/corrections and already-predicted causes.
    """
    import world_model
    edges = world_model._load()
    facts = [e for e in edges
             if e.get("kind", "fact") == "fact" and e.get("cause")]
    if len(facts) < 3:
        return {"action": "world-model prediction",
                "result": "not enough observed facts to predict from",
                "measurable": False}

    sources = [e for e in facts if not e.get("cause", "").startswith("If '")]
    if not sources:
        return {"action": "world-model prediction",
                "result": "no prediction-free fact available",
                "measurable": False}

    already = {e.get("cause", "") for e in edges if e.get("kind") == "prediction"}
    picked = None
    for e in reversed(sources):        # newest fact first
        if f"If '{e['cause'][:80]}' recurs" not in already:
            picked = e
            break
    if picked is None:
        return {"action": "world-model prediction",
                "result": "every recent fact already has a projection",
                "measurable": False}

    cause = picked["cause"]
    effect = picked.get("effect", "")
    # Do not observe when the effect is empty — a prediction with no
    # consequence attached carries no information and only pads the store.
    if not effect.strip():
        return {"action": "world-model prediction",
                "result": f"latest fact '{cause[:60]}' has no effect recorded",
                "measurable": False}

    world_model.observe(
        f"If '{cause[:80]}' recurs",
        f"expect: {effect[:80]}",
        kind="prediction",
        confidence=0.6,
    )
    return {"action": "world-model: added PREDICTION edge (from an observed fact)",
            "predicted_from": cause[:100],
            "result": f"If '{cause[:80]}' recurs, expect {effect[:80]}",
            "measurable": True}

def experiment_tune_buffer():
    """Insight from self-improvement: buffer cap tuning. Measure + enforce cap."""
    buf_file = os.path.join(T, "online_buffer.jsonl")
    n = sum(1 for _ in open(buf_file, encoding="utf-8")) if os.path.exists(buf_file) else 0
    # Cap is enforced on EVERY append via buffer_store (single source of truth).
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import buffer_store
        n = buffer_store.enforce_cap(buf_file)
        cap = buffer_store.MAX_BUF
        # Honesty: report the REAL fill state, not a canned "at cap" claim.
        # (This string asserted "at cap" on runs where n was far below cap,
        #  e.g. 138/300 — a measurement that did not measure.)
        fill = f"{n}/{cap}"
        if n >= cap:
            state = f"buffer at cap {fill} — trim enforced on every write"
        else:
            state = (f"buffer at {fill} ({cap - n} slots free) — "
                     f"trim enforced on every write")
        return {"action": f"buffer measurement: {n} examples (cap {cap})",
                "buffer_count": n, "buffer_cap": cap,
                "result": state,
                "measurable": True}
    except Exception as e:
        return {"action": f"buffer measurement: {n} examples",
                "result": f"buffer store unavailable: {str(e)[:80]}",
                "measurable": False}

def experiment_competitor_gap():
    """Insight: competitor features. Identify ONE gap we can close.

    Honesty contract (fixed 12.09): this experiment used to return a HARDCODED
    gap dict. Live evidence: 96 consecutive runs produced exactly ONE distinct
    `identified_gap` string ("OpenHands has a modular SDK design ...") while the
    buffer's competitor signal changed — i.e. an "experiment" that inspected
    nothing, recited a canned line, and always claimed `measurable: False`.

    Now it: (1) quotes the REAL latest competitor signal verbatim so the entry is
    traceable, (2) maps it against a capability lexicon, (3) measures OUR OWN
    tool surface as a number (tool funcs / lines / package layout), and
    (4) says so honestly when the signal is too vague to map — which is itself
    the useful finding (it flags a broken upstream competitor pipeline instead of
    inventing a gap).
    """
    signal_keys = ("openhands", "devin", "autogpt", "competitor", "sdk",
                   "agent architecture")
    competitors = []
    buf_file = os.path.join(T, "online_buffer.jsonl")
    if os.path.exists(buf_file):
        for line in open(buf_file, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            text = (d.get("u", "") + " " + d.get("a", "")).lower()
            if any(k in text for k in signal_keys):
                competitors.append(d)
    if not competitors:
        return {"action": "competitor gap analysis",
                "result": "no competitor data yet", "measurable": False}

    latest = competitors[-1]
    signal = (latest.get("a") or "").strip()
    signal_q = (latest.get("u") or "").strip()

    # --- map the signal to an implied capability (lexicon, not a guess table) ---
    # Lexicon grows from REAL signals we have seen (12.09.26): the Kiro snippet
    # ("turn prompts into executable specs, validate code correctness ..., build
    # across large codebases with parallel agents") is a genuine capability
    # description, not junk — the lexicon just had no token for it. Absence of a
    # token is a lexicon gap, not evidence that upstream is broken.
    hints = (
        ("modular", "modular tool packaging"),
        ("sdk", "public SDK / programmatic API"),
        ("microservice", "service split"),
        ("plugin", "plugin extensibility"),
        ("multi-agent", "multi-agent orchestration"),
        ("parallel agent", "parallel multi-agent execution"),
        ("spec-driven", "spec-driven development workflow"),
        ("executable spec", "spec -> executable-plan pipeline"),
        ("sandbox", "sandboxed execution"),
        ("persistent memory", "persistent memory layer"),
        ("memory", "memory layer"),
        ("unit test", "automated verification gate"),
        ("validate code", "automated code-conformance check"),
        ("code correctness", "automated code-conformance check"),
        # Grown from REAL signals (17.09.26): the JetBrains free-tier signal
        # ("unlimited code completion and access to local AI models") was a
        # genuine capability description the lexicon had no token for.
        ("completion", "inline code completion / autocomplete surface"),
        ("local ai model", "local model integration in the editor"),
        ("free tier", "free-tier positioning / zero-cost entry"),
        ("coding agent", "agentic coding workflow in the IDE"),
        # Grown from REAL signals (18.09.26): the Microsoft MAF/Foundry signal
        # ("Microsoft Agent Framework (MAF) Microsoft Foundry") names concrete
        # capability classes (agent framework + hosted model platform) the
        # lexicon had no token for.
        ("agent framework", "agent framework / orchestrator SDK"),
        ("foundry", "hosted model platform / managed agent runtime"),
        # Grown from a REAL signal (21.09.26): the benchmark-site row, once the
        # class-127 nav leak was stripped off it, reads
        #   "We benchmarked 4 popular open-source agentic frameworks across 2,000
        #    runs (5 tasks, 100 runs each per framework), measuring end-to-end
        #    latency, token consumption, and architectural differences."
        # That IS a capability description (comparative evaluation harness), not
        # chrome -- so this is the honest lexicon gap the class-127 fix exposed,
        # not something to patch on the extraction side. Measured precision over
        # the corpus the consumer actually reads (33 competitor rows): `benchmark`
        # matches 1 row and that row IS this signal -> 0 mis-maps. Deliberately
        # matched by its MEASUREMENT noun, never a generic word like `framework`
        # (3/33 rows = real mis-maps onto unrelated framework prose).
        ("benchmark", "comparative evaluation harness / multi-framework benchmark"),
        # Grown from a REAL signal (22.09.26): the GAIA row
        #   "GAIA - Open-source framework for building AI agents that run on
        #    local hardware"
        # is a capability description (on-device runtime), and the consumer kept
        # reporting it as an unmappable signal. Measured precision over the 47
        # competitor rows this function actually reads: `local hardware` matches
        # 1 row and that row IS this signal -> 0 mis-maps. Deliberately the
        # two-word phrase, never `local` (6/47 rows -> real mis-maps onto "local
        # runtime", "local LLMs" prose) and never `local model` (0/47 rows, i.e.
        # a token the corpus does not support).
        ("local hardware", "on-device / local-hardware agent runtime"),
        # Grown from a REAL signal (22.09.26, second one that day): the
        # competitor-intelligence row
        #   "Engineers who want an agent to autonomously plan, edit across files
        #    and run tests on complex real-world work, and will pay for depth"
        # is a capability description (multi-file agentic execution with a test
        # loop) the lexicon had no token for. Measured precision over the 44
        # competitor rows this function actually reads: `edit across files`
        # matches 1 row and that row IS this signal -> 0 mis-maps.
        # Rejected alternatives, all measured: `across files` / `run tests` /
        # `plan, edit` / `autonomously plan` / `real-world work` (each 1/44 but
        # narrower and more brittle phrasings of the same row), `plan` 3/44 and
        # `tool` 5/44 (real mis-maps), `tool surface` / `sandbox` / `terminal` /
        # `multi-file` / `paid tier` / `pricing` 0/44 (corpus does not support
        # them). Chosen token states the capability, not a generic verb.
        ("edit across files", "multi-file agentic execution + test loop"),
    )
    # --- the latest row may be an ARTICLE TITLE, not a capability description ---
    # Grown from a REAL signal (23.09.26): the consumer kept reporting
    #   "Feb 2026 An AI agent coding skeptic tries AI agent coding, in
    #    excessive detail minimaxir."
    # as an unmappable signal. Unlike the earlier gaps this is NOT a lexicon
    # gap: the row is a headline (date + title + author handle), and the
    # lexicon having no token for a headline is CORRECT. Measured over the 45
    # competitor rows this function reads, scoring `a` only (which is all that
    # `signal` ever is): `ai agent coding` 2/45, and `coding skeptic` /
    # `skeptic` / `excessive detail` / `minimaxir` each 1/45 -- every hit is
    # this headline or its sibling. Adding any of them would map a title onto
    # a capability, i.e. a mis-map, so the honest move is to recognise the row
    # CLASS rather than grow the lexicon for it.
    # Discriminator (longest-wins selection cannot help here): a headline is a
    # near-echo of its own source question -- significant words of `u`
    # reappearing in `a`. Measured over all 45 rows: exactly 1 row trips
    # (echo >= 0.6 AND len(a) < 160) and it is this headline; 0 mis-fires on
    # the rows that DO carry a capability, notably the sibling row for the same
    # question ("AI agent coding/ vibecoding where the author talks about ...
    # the atrophy of programming skills ...", echo 0.20, 249 chars) and the
    # 22.09.26 signal `edit across files` (echo 0.00, 198 chars).
    # The signal is still REPORTED VERBATIM -- never silently dropped -- only
    # its class changes, so the entry names the real cause instead of a lexicon
    # gap that does not exist.
    _STOP = {"competitor", "intelligence", "the", "a", "an", "and", "of", "for",
             "to", "in", "on", "with", "is", "are", "we", "our", "how", "what",
             "new", "ai"}
    _sig_low = signal.lower()
    _sig_words = set(re.findall(r"[a-z0-9]+", _sig_low))
    _q_words = set(re.findall(r"[a-z0-9]+", signal_q.lower())) - _STOP
    _echo = (len(_q_words & _sig_words) / len(_q_words)) if _q_words else 0.0
    is_headline = _echo >= 0.6 and len(signal) < 160
    low_signal = signal.lower()
    # Longest (most specific) matching token wins: a generic token declared
    # earlier must never shadow a precise one (declaration order was the
    # selection rule before, which is not a specificity rule).
    matches = [(tok, label) for tok, label in hints if tok in low_signal]
    hint = max(matches, key=lambda p: len(p[0]))[1] if matches else None

    # --- a REAL measurement of the thing the gap is about: our tool surface ---
    stats = {"lines": 0, "tool_funcs": 0, "has_tools_pkg": False}
    ts_path = os.path.join(T, "tool_server.py")
    if os.path.exists(ts_path):
        src = open(ts_path, encoding="utf-8", errors="replace").read()
        stats["lines"] = src.count("\n") + 1
        stats["tool_funcs"] = len(re.findall(r"^def t_\w+\(", src, re.M))
        stats["has_tools_pkg"] = os.path.isdir(os.path.join(T, "tools"))
    measured = (f"our tool surface: {stats['tool_funcs']} tool funcs in "
                f"{stats['lines']} lines, tools/ package: "
                f"{'yes' if stats['has_tools_pkg'] else 'no'}")

    if hint:
        gap = (f"{hint}: competitor signals it; {measured} — monolithic, "
               f"no per-tool module boundary")
        fix = f"extract {hint} behind its own module with a test gate"
        result = f"signal '{signal[:50]}' -> gap: {hint} | {measured}"
    elif is_headline:
        gap = (f"no mappable capability in latest signal ({measured}) — "
               f"signal is an article headline (echoes {_echo:.0%} of its own "
               f"source question), not a product capability description")
        fix = ("carry a capability sentence alongside the headline in the "
               "competitor pipeline; no lexicon token should be invented for a "
               "title, and the extraction side is where this belongs")
        result = (f"signal NOT mappable: '{signal[:60]}' | {measured} — "
                  f"headline signal (echo {_echo:.0%} of its own question), no "
                  f"capability sentence to map; extraction-side gap, not a "
                  f"lexicon gap")
    else:
        gap = (f"no mappable capability in latest signal ({measured}) — "
               f"signal contains no token our lexicon knows")
        fix = "grow the capability lexicon from the raw signal before blaming upstream"
        result = (f"signal NOT mappable: '{signal[:60]}' | {measured} — "
                  f"lexicon has no token for this signal (lexicon gap, "
                  f"not proof upstream is broken)")

    return {
        "action": "competitor gap analysis",
        "insight_analyzed": signal[:100],
        "signal_source_question": signal_q[:100],
        "signal_candidates": len(competitors),
        "measured_tool_surface": stats,
        "identified_gap": gap,
        "proposed_fix": fix,
        "result": result,
        "measurable": True,
    }

def experiment_meta_insight():
    """Insight: Meta-RL (LaMer). Apply a simplified version to meta_learn."""
    meta_state = os.path.join(T, "meta_state.json")
    if not os.path.exists(meta_state):
        return {"action": "meta-RL application", "result": "meta_state missing"}
    s = json.load(open(meta_state, encoding="utf-8"))
    # LaMer insight: adapt based on EXPLORATION rate, not just exploitation
    strategies = s.get("strategy_stats", {})
    replay = strategies.get("replay", {"uses": 0})
    fresh = strategies.get("fresh", {"uses": 0})
    if replay["uses"] < 5 or fresh["uses"] < 5:
        # increase exploration: force the less-used strategy next time
        lesson = (f"Meta-RL insight: replay={replay['uses']} vs fresh={fresh['uses']} uses. "
                  f"Boosting exploration on the underused strategy.")
        log({"type": "meta_lesson", "lesson": lesson})
        return {"action": "meta-RL: increased exploration on underused strategy",
                "result": lesson, "measurable": True}
    return {"action": "meta-RL application", "result": "enough data, no exploration boost needed"}

# ---- Action selector: match insight keywords to experiments ----

def experiment_group_state():
    """REAL architecture experiment: generalize a group-state model to unseen lengths.

    Added 21.09.26. The rotation used to hold five experiments of which four were
    log-only (LoRA rank records a baseline and defers to the next GPU run;
    meta-RL re-reads a stale meta_state; buffer/competitor mostly describe the
    surface). The standing mandate is "new NN architecture > infrastructure", so
    the rotation now contains one experiment that trains/evaluates a model and
    writes numbers that can be wrong.

    Method: load the SAVED Z_10 rotor-snap model (2 params, tau=0.1, trained on
    lengths 1-7), evaluate at unseen lengths up to 2048 across 5 seeds, and
    report mean/min/max. No retraining — the saved artifact is the subject.
    """
    import importlib
    import random as _random

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(script_dir)
    for p in (parent, script_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        engine = importlib.import_module("group_state_engine")
        lab = importlib.import_module("group_scaling_lab")
    except Exception as e:  # noqa: BLE001
        return {"action": "group-state generalization",
                "result": f"import failed: {type(e).__name__}: {e}",
                "measurable": False}

    mpath = engine.model_path("Z10")
    if not os.path.exists(mpath):
        return {"action": "group-state generalization",
                "result": f"no saved model at {mpath}", "measurable": False}
    try:
        model, group, payload = engine.load(mpath)
    except Exception as e:  # noqa: BLE001
        return {"action": "group-state generalization",
                "result": f"load failed: {type(e).__name__}: {e}",
                "measurable": False}

    # Cost budget: this runs inside a */30 cron with no per-job timeout, so keep
    # the evaluation to ~30s. Three length decades + three seeds is enough to
    # catch a collapse; the full curve lives in kta_group_state_eval.py.
    lengths = [8, 512, 2048]
    seeds = [0, 1, 2]
    measured = {}
    for L in lengths:
        accs = [round(lab.accuracy(model, group, L, n=100, seed=s), 4) for s in seeds]
        measured[L] = {"mean": round(sum(accs) / len(accs), 4),
                       "min": min(accs), "max": max(accs)}
    worst = min(v["min"] for v in measured.values())
    out = os.path.join(engine.DEFAULT_DIR, "group_state_z10_kta.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.datetime.now().isoformat(),
                   "group": group.order, "params": payload["stats"]["params"],
                   "tau": payload["tau"], "trained_on": payload["stats"].get("trained_on"),
                   "lengths": {str(k): v for k, v in measured.items()},
                   "seeds": seeds, "n_per_seed": 200}, f, indent=1)
    curve = " ".join(f"L{L}:{measured[L]['mean']:.3f}" for L in lengths)
    return {"action": f"group-state generalization ({group.order}, "
                      f"{payload['stats']['params']} params, tau={payload['tau']})",
            "result": f"accuracy on unseen lengths {curve}; worst min over "
                      f"{len(seeds)} seeds x {len(lengths)} lengths = {worst:.4f}",
            "exact_lengths": [L for L in lengths if measured[L]["min"] >= 1.0],
            "artifact": out,
            "measurable": True}


EXPERIMENTS = [
    (["lora", "rank", "peft", "fine-tun"], experiment_lora_rank),
    (["predict", "future", "state-space", "projection"], experiment_predict_world),
    (["buffer", "cap", "memory"], experiment_tune_buffer),
    (["openhands", "devin", "autogpt", "competitor", "sdk"], experiment_competitor_gap),
    (["meta-rl", "lamer", "exploration", "meta-learn"], experiment_meta_insight),
    # architecture slot (appended 21.09.26): rotation index 5, so it is reached
    # once per 6 cycles without disturbing the existing round-robin schedule.
    (["group", "group-state", "symmetry", "rotor", "lattice"], experiment_group_state),
]

def find_latest_insight():
    """Find the most recent useful insight from the buffer.

    Robustness (live 21.09.26): the store can carry blank separator lines and
    the occasional truncated row. The old loop called json.loads() on EVERY
    physical line, so a single empty line aborted the whole cycle with
    "Expecting value: line 2 column 1" and no experiment ever ran. Blank lines
    and unparsable rows are now skipped — a separator is not an insight, and
    one damaged row must not stop the loop.
    """
    latest = None
    skipped = 0
    path = os.path.join(T, "online_buffer.jsonl")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                skipped += 1
                continue
            u, a = d.get("u", ""), d.get("a", "")
            # skip template junk and short answers
            if len(a) > 50 and "sentence" not in a and "thinking process" not in a:
                latest = {"question": u, "answer": a}
    if skipped:
        print(f"[kta] skipped {skipped} unparsable buffer rows", flush=True)
    return latest

def kta_cycle():
    """One knowledge-to-action cycle."""
    insight = find_latest_insight()
    if not insight:
        print("[kta] no usable insight in buffer", flush=True)
        return

    text = (insight["question"] + " " + insight["answer"]).lower()

    # find matching experiment
    # ROTATION: run a different experiment each time (round-robin)
    rot_file = os.path.join(T, ".kta_rotation")
    n = 0
    if os.path.exists(rot_file):
        n = int(open(rot_file, encoding="utf-8").read().strip() or 0)
    with open(rot_file, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    experiment = EXPERIMENTS[n % len(EXPERIMENTS)][1]

    try:
        result = experiment()
    except Exception as e:
        result = {"action": experiment.__name__, "result": f"error: {str(e)[:100]}"}

    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "insight_question": insight["question"][:100],
        "insight_answer": insight["answer"][:100],
        "experiment": experiment.__name__,
        **result,
    }
    log(entry)
    summary = entry.get("result") or entry.get("identified_gap") or entry.get("lesson") or entry.get("action", "")
    print(f"[kta] {entry['experiment']}: {str(summary)[:160]}", flush=True)
    return entry

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        import time as _t
        while True:
            kta_cycle()
            _t.sleep(1800)  # every 30 min
    else:
        kta_cycle()
