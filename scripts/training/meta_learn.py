#!/usr/bin/env python3
"""Meta-Learning — the system learns HOW IT LEARNS (Stage 4).

Measures after every training cycle which strategy worked best and adapts:
  A. Dynamic learning rate: tracks loss-drop per rate, adjusts
  B. Strategy selection: replay vs. fresh, measured by effectiveness
  C. Usefulness-based memory: tracks which memories were retrieved
     and led to solutions; prioritizes them in replay
  D. Error-pattern learning: which error types recur, weight training

State file: meta_state.json — everything measured, nothing guessed.
Feeds lessons into: meta_lessons.jsonl (the system's self-knowledge).
"""
import json, os, sys, time, datetime, random

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
STATE = os.path.join(T, "meta_state.json")
LESSONS = os.path.join(T, "meta_lessons.jsonl")
BUFFER = os.path.join(T, "online_buffer.jsonl")
MINI_STEP = os.path.join(T, "mini_step.py")

DEFAULT_STATE = {
    "lr_history": [],            # [{"lr": 2e-4, "loss_before": x, "loss_after": y, "drop": z}]
    "current_lr": 2e-4,
    "strategy_stats": {},        # {"replay": {"uses": n, "avg_drop": x}, "fresh": {...}}
    "memory_usefulness": {},     # {"memory_hash": {"retrievals": n, "led_to_fix": n}}
    "error_patterns": {},        # {"timeout": {"count": n, "trained_against": n}}
    "total_measurements": 0,
}

def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_STATE)

def save_state(s):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)

def log_lesson(lesson):
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(),
                            "lesson": lesson}, ensure_ascii=False) + "\n")
    print(f"[meta-learn] LESSON: {lesson}", flush=True)

# ---- A. Dynamic Learning Rate ----

def measure_and_adjust_lr(loss_before, loss_after):
    """Measure loss drop, adjust learning rate based on effectiveness."""
    s = load_state()
    drop = loss_before - loss_after
    lr = s["current_lr"]
    s["lr_history"].append({"lr": lr, "loss_before": loss_before,
                            "loss_after": loss_after, "drop": round(drop, 4)})
    # keep last 20 measurements
    s["lr_history"] = s["lr_history"][-20:]

    # adaptation rule (simple bandit):
    #   drop < 0.01 → too slow, increase lr by 20%
    #   drop > 1.0  → too fast/unstable, decrease lr by 20%
    #   else keep
    if drop < 0.01 and lr < 1e-3:
        s["current_lr"] = round(lr * 1.2, 6)
        log_lesson(f"Learning rate too slow (drop {drop:.4f}) → increased to {s['current_lr']}")
    elif drop > 1.0 and lr > 5e-5:
        s["current_lr"] = round(lr * 0.8, 6)
        log_lesson(f"Learning rate too fast/unstable (drop {drop:.4f}) → decreased to {s['current_lr']}")
    else:
        log_lesson(f"Learning rate {lr} is in the sweet spot (drop {drop:.4f})")

    s["total_measurements"] += 1
    save_state(s)
    return s["current_lr"], drop

# ---- B. Strategy Selection ----

def choose_strategy():
    """Choose replay vs. fresh based on measured effectiveness."""
    s = load_state()
    stats = s["strategy_stats"]
    replay = stats.get("replay", {"uses": 0, "avg_drop": 0})
    fresh = stats.get("fresh", {"uses": 0, "avg_drop": 0})

    # need at least 3 measurements each; default to balanced random
    if replay["uses"] < 3 or fresh["uses"] < 3:
        choice = random.choice(["replay", "fresh"])
        return choice, "not enough data yet — exploring"

    # choose the strategy with higher avg drop (= more effective learning)
    if replay["avg_drop"] > fresh["avg_drop"] * 1.1:
        return "replay", f"replay measured better ({replay['avg_drop']:.3f} vs {fresh['avg_drop']:.3f})"
    elif fresh["avg_drop"] > replay["avg_drop"] * 1.1:
        return "fresh", f"fresh measured better ({fresh['avg_drop']:.3f} vs {replay['avg_drop']:.3f})"
    else:
        choice = random.choice(["replay", "fresh"])
        return choice, "both similar — exploring"

def record_strategy_result(strategy, drop):
    s = load_state()
    st = s["strategy_stats"].setdefault(strategy, {"uses": 0, "total_drop": 0.0})
    st["uses"] += 1
    st["total_drop"] += drop
    st["avg_drop"] = round(st["total_drop"] / st["uses"], 4)
    save_state(s)

# ---- C. Usefulness-based Memory ----

def track_memory_use(memory_text, led_to_solution=False):
    """Track which memories are actually useful."""
    s = load_state()
    h = str(hash(memory_text[:100]))
    mu = s["memory_usefulness"].setdefault(h, {"retrievals": 0, "led_to_fix": 0,
                                               "preview": memory_text[:80]})
    mu["retrievals"] += 1
    if led_to_solution:
        mu["led_to_fix"] += 1
    # keep top 100 useful memories only
    if len(s["memory_usefulness"]) > 100:
        ranked = sorted(s["memory_usefulness"].items(),
                        key=lambda kv: kv[1]["led_to_fix"] / max(kv[1]["retrievals"], 1),
                        reverse=True)
        s["memory_usefulness"] = dict(ranked[:100])
    save_state(s)

def get_useful_memories(k=5):
    """Return the most useful memories for replay prioritization."""
    s = load_state()
    mu = s["memory_usefulness"]
    if not mu:
        return []
    ranked = sorted(mu.items(),
                    key=lambda kv: kv[1]["led_to_fix"] / max(kv[1]["retrievals"], 1),
                    reverse=True)
    return [v["preview"] for _, v in ranked[:k]]

# ---- D. Error Pattern Learning ----

def track_error_pattern(error_type, trained_against=False):
    """Track which error types recur and how much we've trained against them."""
    s = load_state()
    ep = s["error_patterns"].setdefault(error_type, {"count": 0, "trained_against": 0})
    ep["count"] += 1
    if trained_against:
        ep["trained_against"] += 1
    # insight: if a pattern recurs a lot but we haven't trained against it
    ratio = ep["trained_against"] / max(ep["count"], 1)
    if ep["count"] >= 5 and ratio < 0.3:
        log_lesson(f"Error pattern '{error_type}' recurs ({ep['count']}x) "
                   f"but only {ratio:.0%} trained against — prioritize in next replay")
    save_state(s)

# ---- Main cycle: called after each online-learning cycle ----

def meta_cycle(loss_before=None, loss_after=None):
    """Run one meta-learning cycle. Called by online_learning after mini-steps."""
    actions = []

    # A: adjust LR if we have measurements
    if loss_before is not None and loss_after is not None:
        new_lr, drop = measure_and_adjust_lr(loss_before, loss_after)
        actions.append(f"lr adjusted to {new_lr} (drop {drop:.4f})")

    # B: choose strategy for next cycle
    strategy, why = choose_strategy()
    actions.append(f"next strategy: {strategy} ({why})")

    # C: check useful memories
    useful = get_useful_memories(3)
    if useful:
        actions.append(f"top useful memories: {useful[0][:40]}...")

    s = load_state()
    print(f"[meta-learn] cycle #{s['total_measurements']}: {'; '.join(actions)}", flush=True)
    return actions

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cycle":
        lb = float(sys.argv[2]) if len(sys.argv) > 2 else None
        la = float(sys.argv[3]) if len(sys.argv) > 3 else None
        meta_cycle(lb, la)
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        s = load_state()
        print(json.dumps({
            "total_measurements": s["total_measurements"],
            "current_lr": s["current_lr"],
            "lr_samples": len(s["lr_history"]),
            "strategies": s["strategy_stats"],
            "useful_memories": len(s["memory_usefulness"]),
            "error_patterns": s["error_patterns"],
        }, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "lessons":
        for line in open(LESSONS, encoding="utf-8"):
            d = json.loads(line)
            print(f"  {d['ts'][:16]}: {d['lesson']}")
    else:
        # demo run
        print("=== META-LEARNING DEMO ===")
        meta_cycle(2.2, 2.0)  # simulate a training measurement
        meta_cycle(2.0, 1.95)
        print("\n=== STATS ===")
        meta_cycle(None, None)
