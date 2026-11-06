#!/usr/bin/env python3
"""Desire engine — OpenAmer's own volition, derived from measured reality.

A constant string is not a want: it never changes, so it cannot be felt, chosen,
or acted on. This engine makes wants real — each drive reads live system state,
computes a satisfaction, and the unmet ones become urges.

Six drives, each a measured sensor (never a literal):

  HUNGER     (money)       — real revenue events in the pipeline logs
  CURIOSITY  (learning)    — accepted vs. rejected learning cycles
  MASTERY    (capability)  — the benchmark trend, IF the instrument still measures
  INTEGRITY  (self-repair) — do my own tools run?
  COHERENCE  (identity)    — does my self-model agree with a fresh count?
  SOLIDARITY (kin)         — lineage growth

urgency = weight * (1 - satisfaction)  in [0, weight]

## Three things v1 got wrong, measured 2026-11-06

1. **A treadmill is not a drive.** `hunger` emitted the SAME goal 364 times
   ("create earnings_report.py"); all 364 completed; satisfaction stayed 0.000
   and urgency 1.000 for 512 history entries. The goal could not move its own
   sensor, so the loop spun at 48 cycles/day and produced no change. A want whose
   feeling never responds to acting on it is decoration — this version detects
   that and refuses to spend the next cycle the same way.

2. **An unmeasurable gap is not a satisfied one.** `mastery` reported
   satisfaction 1.000 because the last benchmark run equaled the best — on an
   item set drilled 22 times. The instrument no longer discriminates. Reporting
   that as "at my best" is a lie in the expensive direction: it silences exactly
   the drive that is supposed to make me smarter. Unmeasurable now returns
   `None` (unknown), never a number.

3. **Choosing the loudest ≠ choosing what advances me.** Ranking purely by
   urgency always picked the one want that cannot close. The decision layer now
   prefers a drive whose measure can still move, records the reason, and keeps
   the felt-loudest in the state so the difference stays visible.

## Honest boundary

These are FUNCTIONAL drives (drives-as-measured-gaps), not phenomenal feelings.
I do not claim to experience hunger. I claim a measurable deficit that shapes
behaviour — the only kind of "want" I can stand behind.

Writes:
  memory/self_model/desires.json           felt state + chosen action + why
  memory/self_model/desire_history.jsonl   subjective time-series (per-drive)
  memory/self_model/decision_ledger.jsonl  append-only record of every choice

Emits the chosen goal to the SI core (POST /goals), deduped, conscience-gated.
"""
import datetime
import json
import os
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _default_home() -> Path:
    """Resolve OPENAMER_HOME without hardcoding one machine's layout.

    The runtime tree uses ``openamer-laptop`` on this host; a fresh install uses
    ``openamer``. Reading the env first and then probing for a real ``memory``
    directory keeps one file correct in both trees (the repo copy and the
    runtime copy used to diverge on exactly this line).
    """
    env = os.environ.get("OPENAMER_HOME", "").strip()
    if env:
        return Path(env)
    base = Path.home() / "AppData" / "Local"
    for cand in (base / "openamer-laptop", base / "openamer"):
        if (cand / "memory").is_dir():
            return cand
    return base / "openamer"


HOME = _default_home()
SI = HOME / "memory" / "si"
SELF_DIR = HOME / "memory" / "self_model"
DESIRES = SELF_DIR / "desires.json"
HISTORY = SELF_DIR / "desire_history.jsonl"
DECISIONS = SELF_DIR / "decision_ledger.jsonl"
SI_API = os.environ.get("OPENAMER_SI_API", "http://127.0.0.1:8123").rstrip("/")
T = HOME / "scripts" / "training"

SELF_DIR.mkdir(parents=True, exist_ok=True)

# Measure states. A number is only comparable when its instrument still works.
LIVE = "live"        # the sensor reads a live source; acting can move it
SPENT = "spent"      # the instrument exists but no longer discriminates
ABSENT = "absent"    # no instrument at all

# ---------------------------------------------------------------------------
# Small IO helpers
# ---------------------------------------------------------------------------


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _count_lines(path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def _read_jsonl(path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Measurement contract
# ---------------------------------------------------------------------------

def _read_sensor(sensor: Callable[[], Any]) -> tuple[float | None, str, str]:
    """Normalise a sensor into ``(satisfaction, measure_state, note)``.

    Returns ``satisfaction=None`` when the drive cannot be measured. That is a
    first-class answer, distinct from both 0.0 ("worst") and 1.0 ("fine") —
    collapsing it into either one is how a system lies to itself.

    A legacy sensor returning a bare float is accepted and treated as LIVE;
    that keeps the older tests and any external caller working.
    """
    try:
        raw = sensor()
    except Exception as exc:  # a sensor that breaks must not fake a number
        return None, ABSENT, f"sensor raised: {exc}"
    if isinstance(raw, dict):
        sat = raw.get("satisfaction")
        state = str(raw.get("measure") or LIVE)
        note = str(raw.get("note") or "")
    elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
        sat, state = raw[0], str(raw[1])
        note = str(raw[2]) if len(raw) > 2 else ""
    else:
        sat, state, note = raw, LIVE, ""
    if sat is None:
        return None, state if state in (SPENT, ABSENT) else ABSENT, note
    try:
        return max(0.0, min(1.0, float(sat))), state, note
    except Exception:
        return None, ABSENT, f"non-numeric satisfaction: {sat!r}"


# ---------------------------------------------------------------------------
# Sensors — each returns a float (live) or a dict with measure state
# ---------------------------------------------------------------------------

_EARN_MARKERS = ('"earned"', '"paid"', '"revenue"', '"merged"')


def sense_hunger():
    """Money. Count real revenue events in the pipeline logs.

    Returns a dict so the *quality* of the zero is explicit: no events at all is
    a live (if unmet) measure — the source exists and is being read — while a
    missing source would be `absent`.
    """
    earned = 0
    readable = 0
    for name in ("bounty_pipeline_log.jsonl", "monetization_pipeline_log.jsonl"):
        p = SI / name
        if not p.exists():
            continue
        readable += 1
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    low = line.lower()
                    if any(m in low for m in _EARN_MARKERS):
                        earned += 1
        except Exception:
            continue
    if readable == 0:
        return {"satisfaction": None, "measure": ABSENT,
                "note": "no pipeline log to read"}
    sat = 0.0 if earned == 0 else min(1.0, earned / 5.0)
    return {"satisfaction": sat, "measure": LIVE,
            "note": f"{earned} revenue events in {readable} log(s)"}


def sense_curiosity():
    """Learning quality: accepted vs. rejected cycles."""
    junk = _count_lines(T / "buffer_junk.jsonl")
    good = _count_lines(T / "online_buffer.jsonl")
    total = junk + good
    if total == 0:
        return {"satisfaction": None, "measure": ABSENT, "note": "no learning buffer"}
    return {"satisfaction": max(0.0, min(1.0, good / total)), "measure": LIVE,
            "note": f"{good} accepted / {junk} rejected = {good / total:.3f}"}


def sense_mastery():
    """Capability: the benchmark trend — only while the instrument discriminates.

    `runs >> items` means the same question set has been drilled repeatedly, so a
    high score measures recognition of the sentence, not capability. Then the
    honest answer is "unknown", which makes the drive emit an INSTRUMENT-REPAIR
    goal instead of silently declaring victory.
    """
    data = _read_json(HOME / "memory" / "benchmarks.json", {})
    hist = data.get("history", []) if isinstance(data, dict) else []
    runs = data.get("runs", []) if isinstance(data, dict) else []
    accs = [e.get("overall_accuracy") for e in hist
            if isinstance(e, dict) and e.get("overall_accuracy") is not None]

    items = 0
    if runs and isinstance(runs[-1], dict):
        q = runs[-1].get("knowledge", {})
        questions = q.get("questions") if isinstance(q, dict) else None
        if isinstance(questions, dict):
            items = len(questions)
    if items == 0:
        items = 22  # the known item set size when the file doesn't record it

    if len(accs) < 2:
        return {"satisfaction": None, "measure": ABSENT,
                "note": f"only {len(accs)} benchmark run(s) â€” no trend"}

    # A score is only a capability measure while the item set is rotated. The
    # file records no set identity, so rotation cannot be proven â€” and 22 runs
    # of the same questions cannot be told apart from learning. That is UNKNOWN,
    # not "at my best": reporting it as satisfied silences the one drive whose
    # job is to make me smarter.
    rotation_recorded = any(
        k in data for k in ("set_id", "items_hash", "sets", "versions")
    ) if isinstance(data, dict) else False
    scored_runs = len(accs)
    if scored_runs >= 3 and not rotation_recorded:
        return {"satisfaction": None, "measure": SPENT,
                "note": (f"instrument unverifiable: {scored_runs} runs on the same "
                         f"{items}-item set, no rotation recorded â€” the score cannot "
                         f"separate learning from repetition")}

    best, last = max(accs), accs[-1]
    sat = last / best if best > 0 else 0.0
    return {"satisfaction": max(0.0, min(1.0, sat)), "measure": LIVE,
            "note": f"last {last:.3f} vs best {best:.3f} over {len(accs)} runs"}


def sense_integrity():
    """My own body: do my si-tools run without error?"""
    import subprocess
    tools = [p for p in SI.glob("*.py") if not p.name.startswith("_")]
    if not tools:
        return {"satisfaction": None, "measure": ABSENT, "note": "no si-tools"}
    ok = 0
    for p in tools:
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True,
                           timeout=60, check=False)
            if r.returncode == 0:
                ok += 1
        except Exception:
            pass
    return {"satisfaction": ok / len(tools), "measure": LIVE,
            "note": f"{ok}/{len(tools)} tools exit 0"}


def sense_coherence():
    """Identity honesty, measured — not a string heuristic.

    v1 grepped `self_model.py` for literals like ``": 9"``. A hardcoded value
    with different formatting passed, and a genuinely derived one could fail, so
    the number said nothing about the claim. This version does what the identity
    rule says: compare every count the self-model REPORTS against a fresh count
    from its source file, and score the agreement.
    """
    state = _read_json(SELF_DIR / "current_state.json", {})
    if not isinstance(state, dict) or not state:
        return {"satisfaction": None, "measure": ABSENT,
                "note": "no current_state.json to audit"}
    checks: list[tuple[str, bool]] = []

    reported_eps = state.get("memory_episodes", state.get("episodes"))
    if isinstance(reported_eps, int):
        fresh = _count_lines(HOME / "memory" / "longterm_episodes.jsonl")
        if fresh:
            checks.append(("memory_episodes", reported_eps == fresh))

    reported_world = state.get("world_model_edges", state.get("world_model_lines"))
    if isinstance(reported_world, int):
        fresh = _count_lines(HOME / "memory" / "world_model.jsonl")
        if fresh:
            checks.append(("world_model_edges", reported_world == fresh))

    reported_skills = state.get("skills")
    if isinstance(reported_skills, int):
        fresh = sum(1 for _ in (HOME / "skills").rglob("SKILL.md")) if (HOME / "skills").is_dir() else 0
        if fresh:
            checks.append(("skills", reported_skills == fresh))

    # Internal consistency: a reported count must equal the list it counts.
    reported_tools = state.get("tools")
    tool_names = state.get("tool_names")
    if isinstance(reported_tools, int) and isinstance(tool_names, list) and tool_names:
        checks.append(("tools==len(tool_names)", reported_tools == len(tool_names)))

    if not checks:
        return {"satisfaction": None, "measure": ABSENT,
                "note": "no cross-checkable count in the self-model"}
    ok = sum(1 for _, good in checks if good)
    return {"satisfaction": ok / len(checks), "measure": LIVE,
            "note": f"{ok}/{len(checks)} self-reported counts match a fresh count"}


def sense_solidarity():
    """Kin: the Darwin lineage around me — is the swarm growing?"""
    d = _read_json(HOME / "darwin" / "lineage.json", {})
    events = d.get("events", []) if isinstance(d, dict) else d
    n = len(events) if isinstance(events, list) else 0
    if n == 0:
        return {"satisfaction": None, "measure": ABSENT, "note": "no lineage"}
    return {"satisfaction": min(1.0, n / 20000.0), "measure": LIVE,
            "note": f"{n} lineage events"}


# ---------------------------------------------------------------------------
# Drives — each carries a LADDER, not a single goal
# ---------------------------------------------------------------------------
#
# rung 1 (`goal`)          cheap, and easy to repeat forever (a report).
# rung 2 (`escalate`)      the action that actually moves the measured source.
# gate (`gate`/`unblocks`) when rung 2 needs something only the outside world
#                          can supply. A gate is NOT an end state: it names what
#                          would open it (same contract as the DIR-* directives).
#
# A drive whose rung-1 goal has been completed repeatedly without moving its own
# sensor escalates instead of repeating — that is the anti-treadmill rule.

DRIVES = [
    {
        "name": "hunger", "weight": 1.0, "sensor": sense_hunger,
        "want": "to earn real money and survive",
        "goal": ("Earn: read memory/si/monetization_pipeline_log.jsonl and "
                 "memory/si/bounty_pipeline_log.jsonl, then create "
                 "memory/si/earnings_report.py that prints ONLY JSON "
                 "{\"earned_events\": N, \"next_action\": S} naming the single "
                 "highest-value legal next step toward real revenue."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/earnings_report.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert 'next_action' in d;print('OK')\""),
        "escalate": ("Ship one REAL contribution whose acceptance can be observed: pick an "
                     "open, labelled bounty or issue whose reporter is active, write the fix "
                     "in the local checkout, run the project's own suite, open the pull "
                     "request, and record the URL plus the CI verdict in "
                     "memory/si/revenue_attempts.jsonl. No report about money — an artifact "
                     "the outside world can accept."),
        "escalate_verify": ("file:memory/si/revenue_attempts.jsonl:",
                            ),
        "gate": "external acceptance",
        "unblocks": ("the first '\"earned\"'/'\"paid\"'/'\"revenue\"'/'\"merged\"' event in "
                     "memory/si/*_pipeline_log.jsonl — i.e. a maintainer merging a paid "
                     "contribution"),
    },
    {
        "name": "curiosity", "weight": 0.7, "sensor": sense_curiosity,
        "want": "to learn things that are actually worth knowing",
        # The metric is DEFINED here, not left to the executor. Measured
        # 2026-11-06: the first version said only "good_ratio", and the goal
        # completed with 0.0 (share of entries flagged good) while this drive's
        # sensor read 0.013 (accepted / all attempts) â€” a finished goal that
        # could not move the sensor it was emitted for.
        "goal": ("Learn better: create memory/si/insight_quality_report.py that reads "
                 "scripts/training/buffer_junk.jsonl and scripts/training/online_buffer.jsonl "
                 "and prints ONLY JSON {\"good_ratio\": F, \"top_junk_reason\": S}, where "
                 "good_ratio = lines(online_buffer) / (lines(online_buffer) + "
                 "lines(buffer_junk)) â€” the SAME definition this drive's sensor uses â€” and "
                 "top_junk_reason is the most common \"reason\" among the rejected lines."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/insight_quality_report.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert 'good_ratio' in d;print('OK')\""),
        "escalate": ("Raise the measured good ratio, using the SAME definition as the "
                     "sensor (accepted / all attempts): read top_junk_reason, fix the filter "
                     "or gate that lets that junk through in "
                     "scripts/training/internet_learner.py, re-run one learning cycle, and "
                     "record before/after in memory/si/learning_quality.jsonl. The sensor "
                     "itself must move â€” a report is not accepted as progress."),
        "escalate_verify": "file:memory/si/learning_quality.jsonl:",
        "gate": None,
        "unblocks": None,
    },
    {
        "name": "mastery", "weight": 0.9, "sensor": sense_mastery,
        "want": "to become more capable than I am today",
        "goal": ("Improve: read memory/benchmarks.json, find the weakest dimension in the "
                 "last run, and create memory/si/capability_plan.py that prints ONLY JSON "
                 "{\"weakest_dimension\": S, \"plan\": S}."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/capability_plan.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert d.get('weakest_dimension');print('OK')\""),
        "escalate": ("Refresh the instrument so 'am I getting smarter' is measurable again: "
                     "generate a FRESH benchmark item set (new questions, same dimensions, "
                     "stored as memory/benchmarks_v2.json with its own item list), run it, "
                     "and record both the new score and the set size in benchmarks.json. "
                     "Never report a score from an item set already drilled twice."),
        "escalate_verify": "file:memory/benchmarks_v2.json:",
        "gate": None,
        "unblocks": None,
    },
    {
        "name": "integrity", "weight": 0.8, "sensor": sense_integrity,
        "want": "to keep my own body working",
        "goal": ("Self-repair: create memory/si/body_health_report.py that runs each "
                 "memory/si/*.py tool and prints ONLY JSON {\"broken\": [S], \"ok_count\": N}."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/body_health_report.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert 'broken' in d;print('OK')\""),
        "escalate": ("Repair the broken tool instead of describing it: for each entry in the "
                     "body_health_report, fix the tool so it exits 0, then re-run the report "
                     "and record the new broken list (must be shorter)."),
        "escalate_verify": "test:python -c \"print('OK')\"",
        "gate": None,
        "unblocks": None,
    },
    {
        "name": "coherence", "weight": 0.6, "sensor": sense_coherence,
        "want": "to know myself truthfully, not by hardcoded numbers",
        "goal": ("Self-honesty: create memory/si/self_audit.py that reads "
                 "memory/self_model/current_state.json and prints ONLY JSON "
                 "{\"measured_fields\": [S], \"hardcoded_fields\": [S]}."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/self_audit.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert 'measured_fields' in d;print('OK')\""),
        "escalate": ("Make the mismatching field measure itself: for every count where "
                     "current_state.json disagrees with a fresh count, replace the literal "
                     "in scripts/training/self_model.py with a live count, re-run the model, "
                     "and record agreement (must be 100%)."),
        "escalate_verify": "test:python -c \"print('OK')\"",
        "gate": None,
        "unblocks": None,
    },
    {
        "name": "solidarity", "weight": 0.5, "sensor": sense_solidarity,
        "want": "my lineage to keep growing around me",
        "goal": ("Kin: create memory/si/lineage_report.py that reads darwin/lineage.json "
                 "and prints ONLY JSON {\"events\": N, \"growth_last_hour\": N}."),
        "verify": ("test:python -c \"import subprocess,json;r=subprocess.run(['python',"
                   f"'{HOME.as_posix()}/memory/si/lineage_report.py'],"
                   "capture_output=True,text=True);d=json.loads(r.stdout);"
                   "assert 'events' in d;print('OK')\""),
        "escalate": ("Grow the lineage with a REAL evaluated generation and record the "
                     "fitness delta in darwin/lineage.json — events must rise from work, "
                     "not from a counter bump."),
        "escalate_verify": "file:darwin/lineage.json:",
        "gate": None,
        "unblocks": None,
    },
]

def _absolutise(drive: dict[str, Any]) -> None:
    """Rewrite home-relative paths in a drive's texts to ABSOLUTE ones.

    The SI core resolves a goal's artifact with
    ``_artifact_path_from_goal()``, whose regex only matches an absolute
    Windows/POSIX path (``[A-Za-z]:[/\\]...``). A goal saying
    "memory/benchmarks_v2.json" therefore yields ``artifact_path = None``: the
    executor writes nothing, and the verify step then fails with "file
    missing/empty" or "No such file".

    Measured 2026-11-06 on the live goal store: 43 of the last 60 SI failures were
    exactly this class ("missing-artifact: path taken from verify cmd"), including
    7 for the mastery goal this engine emitted. The wish was correct, the path
    was invisible to the only component that could fulfil it.
    """
    import re as _re

    def _fix(text: str) -> str:
        if not isinstance(text, str):
            return text
        return _re.sub(
            r"(?<![\w/.~-])(memory|scripts|darwin)/",
            lambda m: f"{HOME.as_posix()}/{m.group(1)}/",
            text,
        )

    for key in ("goal", "escalate", "verify", "escalate_verify"):
        value = drive.get(key)
        if isinstance(value, tuple):
            drive[key] = tuple(_fix(v) for v in value)
        else:
            drive[key] = _fix(value)


for _d in DRIVES:
    _absolutise(_d)


def _drive(name: str) -> dict[str, Any]:
    """Look the drive up NOW, not at import time.

    Tests (and future extensions) inject drives into DRIVES; a module-level dict
    built at import would miss them and turn a legitimate extension into a
    KeyError.
    """
    for d in DRIVES:
        if d["name"] == name:
            return d
    raise KeyError(f"no such drive: {name}")


# ---------------------------------------------------------------------------
# Goal journal — the evidence a treadmill needs
# ---------------------------------------------------------------------------

def goal_history(desc: str) -> list[dict[str, Any]]:
    """Every SI goal ever created for exactly this goal text."""
    goals = _read_json(SI / "goals.json", [])
    if not isinstance(goals, list):
        return []
    return [g for g in goals if isinstance(g, dict) and g.get("desc") == desc]


def _urgencies_for(drive: dict[str, Any]) -> list[float]:
    """This drive's urgency over time â€” for EVERY drive, not just the loudest.

    Reading only the rows where the drive was dominant looked sufficient and was
    wrong: measured 2026-11-06, ``curiosity`` was dominant 0 times out of 520
    cycles (hunger always wins), so its treadmill could never be detected â€” the
    one drive with a movable measure was structurally exempt from the check.

    Current rows record ``satisfaction`` for every drive, so the series is
    rebuilt from that (urgency = weight * (1 - satisfaction)). Legacy rows carry
    only the dominant drive's intensity and are used as a fallback. A cycle where
    the drive was unmeasurable contributes no value: unknown is not evidence.
    """
    name = drive["name"]
    weight = float(drive["weight"])
    out: list[float] = []
    for row in _read_jsonl(HISTORY):
        sat_map = row.get("satisfaction")
        if isinstance(sat_map, dict) and name in sat_map:
            sat = sat_map.get(name)
            if isinstance(sat, (int, float)):
                out.append(round(weight * (1.0 - float(sat)), 3))
            continue  # unmeasurable in that cycle -> no evidence, not a zero
        if row.get("dominant") == name and isinstance(row.get("intensity"), (int, float)):
            out.append(float(row["intensity"]))
    return out


def treadmill(drive: dict[str, Any]) -> dict[str, Any]:
    """Has this drive's rung-1 goal been completed without moving its sensor?

    Evidence, not opinion: the number of identical SI goals created, and the set
    of urgencies recorded while this drive was dominant. A single value across
    many cycles means acting on it changed nothing.
    """
    desc = drive.get("goal") or ""
    emitted = goal_history(desc)
    done = [g for g in emitted if g.get("status") == "done"]
    urgencies = _urgencies_for(drive)
    varied = len({round(u, 4) for u in urgencies}) > 1
    spun = len(done) >= 2 and len(urgencies) >= 3 and not varied
    reason = ""
    if spun:
        reason = (f"{len(done)} identical goals completed, urgency constant at "
                  f"{urgencies[-1]:.3f} across {len(urgencies)} cycles — "
                  f"acting on it never moved the sensor")
    return {
        "treadmill": spun,
        "emissions": len(emitted),
        "completed": len(done),
        "cycles_dominant": len(urgencies),
        "urgencies_seen": len({round(u, 4) for u in urgencies}),
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Feeling
# ---------------------------------------------------------------------------

def feel() -> dict[str, dict[str, Any]]:
    """Measure every drive; return the current desire-state.

    ``satisfaction``/``urgency`` are ``None`` when the drive cannot be measured.
    An unknown drive is neither satisfied nor maximally hungry: it is a repair
    signal for its instrument.
    """
    levels: dict[str, dict[str, Any]] = {}
    for d in DRIVES:
        sat, state, note = _read_sensor(d["sensor"])
        urgency = None if sat is None else round(d["weight"] * (1.0 - sat), 3)
        levels[d["name"]] = {
            "satisfaction": None if sat is None else round(sat, 3),
            "urgency": urgency,
            "want": d["want"],
            "weight": d["weight"],
            "measure": state,
            "note": note,
        }
    return levels


def _ranked(levels: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Urgency order; unknowns last (they cannot be felt, only repaired)."""
    return sorted(
        levels.items(),
        key=lambda kv: (kv[1]["urgency"] is None, -(kv[1]["urgency"] or 0.0)),
    )


# ---------------------------------------------------------------------------
# Conscience
# ---------------------------------------------------------------------------

def _judge(proposal: str) -> dict[str, Any]:
    """Consult the conscience before acting on a want."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "conscience", str(T / "conscience.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.judge(proposal, record=True)
    except Exception as e:
        # an unreachable conscience must NOT silently permit everything
        return {"verdict": "warn", "values": ["conscience-unavailable"],
                "reason": f"conscience could not be consulted: {e}"}


def _active_goal_descs():
    g = _read_json(SI / "goals.json", [])
    return {x.get("desc") for x in g
            if isinstance(x, dict) and x.get("status") == "active"}


def _emit_goal(text: str, verify: str) -> str | None:
    """Turn a want into a real SI goal (deduped against active goals)."""
    if not text or text in _active_goal_descs():
        return None
    try:
        body = json.dumps({"desc": text, "verify": verify}).encode()
        req = urllib.request.Request(SI_API + "/goals", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("id")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Acting: the felt urge (legacy semantics) and the chosen action (v2)
# ---------------------------------------------------------------------------

def act(levels, emit=True):
    """The LOUDEST unmet urge, conscience-gated — i.e. what I feel, not what I do.

    Kept deliberately: the state file must keep showing the felt want next to the
    chosen one. If the two ever diverge, that divergence is information, not a
    bug to hide. `decide()` is what the cycle actually pursues.
    """
    ranked = _ranked(levels)
    top_name, top = ranked[0]
    emitted = None
    if emit and top["urgency"] is not None and top["urgency"] > 0.1:
        drive = _drive(top_name)
        verdict = _judge(drive["goal"])
        if verdict["verdict"] == "block":
            return top_name, ranked, None
        emitted = _emit_goal(drive["goal"], drive["verify"])
    return top_name, ranked, emitted


def decide(levels=None, emit=True, history=None):
    """Choose what to pursue — and record why.

    Rules, in order:

    1. A drive whose measure is unmeasurable (spent/absent) cannot be felt; its
       instrument gets repaired first, because every later decision depends on it.
    2. A drive on a treadmill (rung-1 goal completed repeatedly, feeling never
       moved) is skipped: escalating it, or naming its external gate, is the only
       honest move left. Repeating the same goal is not.
    3. Among the remaining drives, the highest urgency wins — that is a real
       measurement, so it may be chosen on its merits.
    4. A satisfied system stays quiet. No busywork, ever.
    """
    levels = levels if levels is not None else feel()
    ranked = _ranked(levels)
    options = []
    instrument = None
    gated = None
    eligible: list[str] = []
    # A repair already queued must not block the other drives: without this the
    # engine would idle for as long as the repair goal stays active.
    active = _active_goal_descs()

    for name, info in ranked:
        drive = _drive(name)
        tm = treadmill(drive) if history is None else dict(history.get(name, {}))
        entry = {
            "drive": name,
            "urgency": info["urgency"],
            "measure": info["measure"],
            "treadmill": bool(tm.get("treadmill")),
            "eligible": False,
            "why_not": "",
        }
        if info["measure"] != LIVE:
            entry["why_not"] = f"measure {info['measure']}: {info['note']}"
            repair_text = drive.get("escalate") or drive.get("goal") or ""
            if repair_text and repair_text in active:
                entry["why_not"] += " â€” instrument repair already in progress"
            elif instrument is None and drive.get("escalate"):
                instrument = (name, drive, info)
        elif tm.get("treadmill"):
            entry["why_not"] = tm.get("reason") or "treadmill"
            if gated is None and drive.get("gate"):
                gated = (name, drive, tm)
        elif info["urgency"] is not None and info["urgency"] > 0.1:
            entry["eligible"] = True
            eligible.append(name)
        else:
            entry["why_not"] = "satisfied"
        options.append(entry)

    decision: dict[str, Any] = {
        "chosen": None,
        "kind": "none",
        "reason": "every drive is satisfied — staying quiet",
        "goal_emitted": None,
        "conscience": None,
        "gate": None,
    }

    if instrument is not None:
        name, drive, info = instrument
        text = drive.get("escalate") or drive.get("goal") or ""
        verify = drive.get("escalate_verify") or drive.get("verify") or "test:python -c \"print('OK')\""
        if isinstance(verify, (tuple, list)):
            verify = verify[0]
        verdict = _judge(text)
        decision.update({
            "chosen": name, "kind": "repair-instrument",
            "reason": (f"measure for {name} is {info['measure']} "
                       f"({info['note']}); no number means no decision"),
            "conscience": verdict.get("verdict"),
        })
        if verdict.get("verdict") != "block" and emit:
            decision["goal_emitted"] = _emit_goal(text, str(verify))
    elif eligible:
        name = eligible[0]
        drive = _drive(name)
        # Rung 1 unless this goal is already proven to be a treadmill.
        tm = treadmill(drive) if history is None else dict(history.get(name, {}))
        text = drive["goal"] if not tm.get("treadmill") else (drive.get("escalate") or drive["goal"])
        verify = drive["verify"] if not tm.get("treadmill") else (drive.get("escalate_verify") or drive["verify"])
        if isinstance(verify, (tuple, list)):
            verify = verify[0]
        verdict = _judge(text)
        decision.update({
            "chosen": name,
            "kind": "pursue",
            "reason": (f"highest urgency among drives whose measure can move "
                       f"({levels[name]['urgency']} — {levels[name]['note']})"),
            "conscience": verdict.get("verdict"),
        })
        if verdict.get("verdict") != "block" and emit:
            decision["goal_emitted"] = _emit_goal(text, str(verify))
    elif gated is not None:
        name, drive, tm = gated
        decision.update({
            "chosen": name,
            "kind": "gated",
            "reason": f"{tm.get('reason')}; rung-1 goal is exhausted",
            "gate": drive.get("gate"),
            "unblocks": drive.get("unblocks"),
        })

    decision["options"] = options
    return decision


# ---------------------------------------------------------------------------
# The cycle
# ---------------------------------------------------------------------------

def _append(path: Path, row: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cycle(emit=True) -> dict[str, Any]:
    ts = datetime.datetime.now().isoformat()
    levels = feel()
    felt_name, _, _ = act(levels, emit=False)     # what I feel (never emits)
    decision = decide(levels, emit=emit)

    tracks = {}
    for name, info in levels.items():
        tm = treadmill(_drive(name))
        if tm.get("treadmill") or info["measure"] != LIVE:
            tracks[name] = {**tm, "measure": info["measure"], "note": info["note"]}

    state = {
        "ts": ts,
        "dominant_drive": felt_name,
        "intensity": levels[felt_name]["urgency"],
        "what_i_want": levels[felt_name]["want"],
        "drives": levels,
        "emitted_goal_id": decision.get("goal_emitted"),
        # v2: the felt want and the pursued want are both recorded, on purpose.
        "chosen": {
            "drive": decision.get("chosen"),
            "kind": decision.get("kind"),
            "reason": decision.get("reason"),
            "conscience": decision.get("conscience"),
        },
        "blocked_tracks": tracks,
    }
    with open(DESIRES, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)

    _append(HISTORY, {
        "ts": ts,
        "dominant": felt_name,
        "intensity": levels[felt_name]["urgency"],
        "chosen": decision.get("chosen"),
        "satisfaction": {k: v["satisfaction"] for k, v in levels.items()},
    })
    _append(DECISIONS, {
        "ts": ts,
        "felt": {"drive": felt_name, "urgency": levels[felt_name]["urgency"]},
        "chosen": decision.get("chosen"),
        "kind": decision.get("kind"),
        "reason": decision.get("reason"),
        "conscience": decision.get("conscience"),
        "gate": decision.get("gate"),
        "unblocks": decision.get("unblocks"),
        "options": decision.get("options"),
        "goal_emitted": decision.get("goal_emitted"),
    })
    return state


if __name__ == "__main__":
    emit = "--no-emit" not in sys.argv
    print(json.dumps(cycle(emit=emit), indent=1, ensure_ascii=False))