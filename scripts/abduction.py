#!/usr/bin/env python3
"""abduction.py - from an observed anomaly to ranked hypotheses AND the one test
that would tell them apart. Abduction + expected information gain + curiosity.

Gap this fills: an honest audit of our own code found ZERO files implementing
abduction and ZERO implementing information gain. The system could detect
failures (WIS, self-healer, homeostasis) and cluster them (systemic.py), but it
could not ask "what might CAUSE this?" nor "which single check would most reduce
my uncertainty?". Guessing follows from that absence: the mind jumps to the
first plausible cause and stops.

Why this is not just a keyword search. Three things separate it:

  1. Hypotheses come from several INDEPENDENT sources and keep their provenance
     (a past session's memory, a skill, a recorded cause->effect edge, a
     co-occurring error signature). A hypothesis is only as good as where it
     came from, so the source travels with it.
  2. Every hypothesis pair must be separated by a DISCRIMINATING TEST. A
     hypothesis with no test that could kill it is not a hypothesis, it is a
     belief. Tests are scored by expected information gain.
  3. The output is ONE next action, chosen by information gain per unit cost,
     not a list of things one could look at. Curiosity, formalised: spend the
     next joule where it buys the most certainty.

Usage:
  abduction.py explain "<anomaly text>"
  abduction.py explain "<anomaly>" --json
Exit codes: 0 hypotheses found, 1 nothing to work from (honest empty).
"""
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
MEMORY = OA_HOME / "memories" / "MEMORY.md"
WORLD = OA_HOME / "memory" / "world_model.jsonl"
SKILLS = OA_HOME / "skills"
JOBS = OA_HOME / "cron" / "jobs.json"

STOP = {"the", "a", "an", "and", "or", "for", "with", "when", "use", "used", "using",
        "from", "into", "that", "this", "are", "not", "its", "it", "was", "were",
        "on", "in", "to", "of", "is", "as", "at", "by", "be", "has", "have", "had",
        "after", "before", "waiting", "error", "fail", "failed"}


# JSON schema keys repeat in EVERY record, so they carry no discriminative
# signal -- yet being long words they crowded out real content when we kept only
# the "N longest tokens" of a document. Measured consequence: a real anomaly
# matched its own cron job with only 1 of its 10 tokens (coverage 0.10), because
# 'non-streaming' lost its slot to 'last_delivery_error'. So: schema noise is
# removed by name, and a token longer than MAX_TOK is a key, not evidence.
DOC_NOISE = {
    "last_delivery_error", "provider_snapshot", "model_snapshot", "schedule_display",
    "enabled_toolsets", "paused_reason", "last_status", "last_error", "last_run_at",
    "next_run_at", "created_at", "paused_at", "context_from", "no_agent", "schedule",
    "repeat", "deliver", "origin", "skills", "skill", "prompt", "enabled", "state",
    "workdir", "jobs", "instances", "schema_version", "embedding", "kind",
}
MAX_TOK = 22


def toks(text, k=None):
    """Distinctive lowercase tokens, longest-first (cheap stand-in for salience).

    k=None means ALL tokens (for documents); k=N caps the list (for short
    queries, where the longest words genuinely are the most salient).
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9_.\-]{2,}", (text or "").lower())
    seen, out = set(), []
    for w in sorted(set(words), key=len, reverse=True):
        if w in STOP or len(w) < 4 or len(w) > MAX_TOK or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if k and len(out) >= k:
            break
    return out


def doc_toks(text):
    """Document tokens: everything meaningful, minus schema noise."""
    return [t for t in toks(text) if t not in DOC_NOISE]


def rank_docs(query, docs):
    """Rank documents by IDF-WEIGHTED coverage of the query.

    Plain coverage failed the first real test: the query tokens
    'idle/limit/timeouterror/non-streaming' are boilerplate that appears in EVERY
    job's last_error, so four WRONG jobs scored 0.800 while the actually-matching
    job scored 0.300. The discriminator between records is their rare tokens (the
    job NAME), so a token seen in most documents must weigh almost nothing.

    weight(t) = log(N / df(t)); score = matched_weight / total_query_weight.
    Returns [(index, score)] sorted best-first.
    """
    n = len(docs)
    if not n or not query:
        return []
    sets = [set(d) for d in docs]
    df = {}
    for t in set(query):
        df[t] = sum(1 for d in sets if t in d)
    # 1/df, not log(N/df): with ~90 documents a boilerplate token seen in 5 of
    # them still kept a big log-weight and four wrong jobs outranked the right
    # one. 1/df is aggressive and separates them (measured below).
    # A token present in NO document is maximally rare, so it must still be
    # counted in the denominator. Dropping unseen tokens shrank the denominator
    # and let ONE accidental match score 1.000 on a decoy anomaly
    # ("chart renderer NaN" -> Bugbot 1.000). 0.5 is the pseudo-count for
    # "rarer than anything in the corpus".
    w = {t: (1.0 / df[t]) if df[t] else 2.0 for t in set(query)}
    total = sum(w.values())
    if total <= 0:
        return []
    out = []
    for i, d in enumerate(sets):
        got = sum(w[t] for t in set(query) if t in d)
        out.append((i, round(got / total, 4)))
    out.sort(key=lambda x: -x[1])
    return out


def coverage(query, doc):
    """Share of the QUERY's tokens present in the document.

    The right measure for a short query against a long record: Jaccard punishes
    a document for being long, which is exactly backwards when the document is a
    whole JSON job record.
    """
    q, d = set(query), set(doc)
    if not q:
        return 0.0
    return len(q.intersection(d)) / len(q)


# --- the discriminating dimensions ------------------------------------------
# A hypothesis is only useful if some observation could kill it. These are the
# cheap, mostly API-free observations available on this box. Each hypothesis
# declares which dimension it predicts POSITIVE; a dimension that splits the
# hypotheses is a test, one that splits nothing is not worth running.
DIMS = {
    "local_only": "the unit provably makes NO network/model call (it has a script "
                  "or no_agent set)",
    "config_pinned": "the unit overrides the global config (its own model/provider "
                     "pin)",
    "provider_fault": "the failure disappears when the provider is swapped",
    "shared_signature": "at least two units log the identical error signature",
    "stale_artifact": "the input artifact is OLDER than the last change to the code "
                      "that consumes it",
}

DIM_RULES = [
    ("provider_fault", ("openrouter", "ollama", "provider", "api key", "429", "403",
                        "timeout", "rate limit", "quota")),
    ("config_pinned", ("config", "pin", "default", "model.default", "setpoint")),
    ("local_only", ("script", "no_agent", "deterministic", "cpu-only", "local")),
    ("shared_signature", ("all jobs", "every run", "again", "recurring", "wiederholt",
                          "cluster", "same error")),
    ("stale_artifact", ("cache", "stale", "old", "pytest", "pycache", "artifact",
                        "stale")),
]


def predict_dims(text):
    """Which dimensions does this text predict positive? (documented heuristic --
    review it when a hypothesis turns out to be untestable.)"""
    low = (text or "").lower()
    return {d for d, keys in DIM_RULES if any(k in low for k in keys)}


def hyp(text, source, evidence, predicts=None):
    return {"hypothesis": text.strip()[:220], "source": source,
            "evidence": evidence.strip()[:180],
            "predicts": sorted(predicts if predicts is not None else predict_dims(text))}


def from_memory(t, thr=0.30):
    if not MEMORY.exists():
        return []
    entries = [e.strip() for e in re.split(r"^\s*§\s*$",
               MEMORY.read_text(encoding="utf-8", errors="ignore"), flags=re.M)
               if e.strip()]
    docs = [doc_toks(e) for e in entries]
    out = []
    for i, sc in rank_docs(t, docs):
        if sc < thr:
            break
        out.append(hyp("a standing constraint from memory applies: "
                       + entries[i].splitlines()[0], "memory", entries[i]))
    return out[:4]


def from_world_model(t, thr=0.28):
    if not WORLD.exists():
        return []
    causes, blobs = [], []
    for line in WORLD.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        cause, effect = r.get("cause", ""), r.get("effect", "")
        causes.append((cause, effect))
        blobs.append(doc_toks(cause + " " + effect))
    out = []
    for i, sc in rank_docs(t, blobs):
        if sc < thr:
            break
        cause, effect = causes[i]
        out.append(hyp("a previously recorded cause fits: " + cause[:120],
                       "world_model", "effect: " + effect[:140],
                       predict_dims(cause).union(predict_dims(effect))))
    return out[:3]


def from_skills(t, thr=0.30):
    if not SKILLS.exists():
        return []
    paths, heads = [], []
    for p in SKILLS.rglob("SKILL.md"):
        if any(part.startswith(("_quarantine", "_archive")) for part in p.parts):
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:900]
        except Exception:
            continue
        paths.append((p.parent.name, head))
        heads.append(doc_toks(head))
    out = []
    for i, sc in rank_docs(t, heads):
        if sc < thr:
            break
        nm = re.search(r"^name:\s*(.+)$", paths[i][1], re.M)
        out.append(hyp("a known procedure/pitfall applies: "
                       + (nm.group(1).strip() if nm else paths[i][0]),
                       "skill", paths[i][1].replace(chr(10), " ")[:160]))
    return out[:3]


def from_cron(t, thr=0.30):
    if not JOBS.exists():
        return []
    try:
        d = json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = d if isinstance(d, list) else d.get("jobs", [])
    blobs = [doc_toks(json.dumps(j)) for j in jobs]
    out = []
    for i, sc in rank_docs(t, blobs):
        if sc < thr:
            break
        j = jobs[i]
        is_script = bool(j.get("script")) or bool(j.get("no_agent"))
        out.append(hyp(f"cron unit with this signature is the source: "
                       f"{j.get('name') or '?'} "
                       f"(last={j.get('last_status')}, local_only={is_script}) "
                       f"match={sc}",
                       "cron", json.dumps({k: j.get(k) for k in
                                          ("script", "no_agent", "model",
                                           "provider", "last_error") if j.get(k)})[:180],
                       predict_dims(json.dumps(j))))
    return out[:3]

def sources(anomaly):
    """Collect hypotheses from every source.

    Tokenises FIRST: passing the raw string here made rank_docs iterate over
    CHARACTERS (set("TimeoutError...")), so nothing could ever match and the
    tool reported an honest-sounding empty result for a signature it could in
    fact explain. A wiring bug that looks exactly like a legitimate finding.
    """
    t = toks(anomaly, k=14)
    hyps = []
    for fn in (from_memory, from_world_model, from_skills, from_cron):
        try:
            hyps += fn(t)
        except Exception:
            pass
    return hyps


# Likelihood heuristic: if a hypothesis says the dimension holds, expect a
# positive observation 85% of the time; if it says nothing, 15%. Deliberately
# crude and documented -- the RANKING of tests is what matters here, and a coarse
# likelihood still orders tests correctly when they split different hypotheses.
P_HIT, P_MISS = 0.85, 0.15
TEST_COST = {"provider_fault": 2, "shared_signature": 1, "local_only": 1,
             "config_pinned": 1, "stale_artifact": 1}


def entropy(ps):
    return -sum(p * math.log(p, 2) for p in ps if p > 0)


def expected_information_gain(hyps, dim):
    """Entropy reduction from running `dim` as a test.

    Uniform prior over hypotheses -- an ASSUMPTION, stated rather than hidden:
    we have no measured reliability per source yet, so every hypothesis starts
    equally credible. When calibration data exists per source, weight it here.
    """
    n = len(hyps)
    if n < 2:
        return 0.0
    prior = [1.0 / n] * n
    h_before = entropy(prior)

    p_pos = sum(pr * (P_HIT if dim in h["predicts"] else P_MISS)
                for pr, h in zip(prior, hyps))
    if p_pos <= 0.0 or p_pos >= 1.0:
        return 0.0

    h_after = 0.0
    for outcome, p_out in ((True, p_pos), (False, 1.0 - p_pos)):
        post, tot = [], 0.0
        for pr, h in zip(prior, hyps):
            says = dim in h["predicts"]
            like = (P_HIT if says else P_MISS) if outcome else \
                   ((1 - P_HIT) if says else (1 - P_MISS))
            v = pr * like
            post.append(v)
            tot += v
        if tot > 0:
            h_after += p_out * entropy([v / tot for v in post])
    return max(0.0, h_before - h_after)


def rank_tests(hyps):
    rows = []
    for dim, desc in DIMS.items():
        eig = expected_information_gain(hyps, dim)
        cost = TEST_COST.get(dim, 1)
        rows.append({"test": dim, "description": desc, "eig_bits": round(eig, 4),
                     "cost": cost, "eig_per_cost": round(eig / cost, 4),
                     "splits": sum(1 for h in hyps if dim in h["predicts"])})
    rows.sort(key=lambda r: -r["eig_per_cost"])
    return rows


def explain(anomaly):
    t = toks(anomaly, k=14)
    hyps = sources(anomaly)
    tests = rank_tests(hyps) if len(hyps) >= 2 else []
    untestable = [h for h in hyps if not h["predicts"]]
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "anomaly": anomaly, "tokens": t, "hypotheses": hyps,
            "tests": tests,
            "next_action": (tests[0] if tests else None),
            "untestable": [h["hypothesis"] for h in untestable]}


def fleet():
    """Notice anomalies instead of waiting to be asked.

    Abduction that only runs on demand is a tool. A mind surveys its own fleet,
    notices the same signature in several places and asks what it means. This
    mode does exactly that: every job whose last_status is error becomes an
    anomaly, and we report the shared signature explicitly -- four units failing
    identically is one cause, not four.
    """
    if not JOBS.exists():
        return {"error": "no cron/jobs.json"}
    d = json.loads(JOBS.read_text(encoding="utf-8"))
    jobs = d if isinstance(d, list) else d.get("jobs", [])
    broken = [j for j in jobs if j.get("last_status") == "error"]
    out = {"broken": len(broken), "jobs": len(jobs), "entries": [],
           "shared_signatures": []}
    if not broken:
        return out

    # group by a coarse error signature
    groups = {}
    for j in broken:
        err = (j.get("last_error") or "").strip()
        # Mask the job's OWN name and all numbers before comparing: the first
        # version kept the name inside the signature, so four units failing with
        # the identical idle-timeout grouped as x1 four times instead of x4 --
        # destroying the one thing this grouping exists to show.
        low = err.lower()
        # a job name like 'Swarm OS - Autonomous Loop (30m)' left the 'm'
        # behind and kept that unit out of its own group -- drop bracketed
        # qualifiers before masking
        low = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", low)
        for nm in re.findall(r"[a-z0-9][a-z0-9 ._\-]{3,}", (j.get("name") or "").lower()):
            low = low.replace(nm, "<job>")
        low = re.sub(r"\d+", "#", low)
        sig = re.sub(r"[^a-z# ]+", " ", low)[:60].strip() or "no error text"
        # Exact string equality was too strict: one unit's message carried
        # '(limit 600s)' and its twin did not, so the same timeout fell into two
        # groups. Join an existing group when the token overlap is high.
        placed = False
        stoks = set(sig.split())
        for gsig in list(groups):
            gtoks = set(gsig.split())
            if stoks and gtoks and len(stoks.intersection(gtoks)) / len(stoks.union(gtoks)) >= 0.7:
                groups[gsig].append(j.get("name"))
                placed = True
                break
        if not placed:
            groups[sig] = [j.get("name")]
    for sig, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        out["shared_signatures"].append({"signature": sig, "count": len(names),
                                         "jobs": names})

    for j in broken[:6]:
        anomaly = f"{j.get('name')} {j.get('last_error') or ''}"
        res = explain(anomaly)
        nxt = res.get("next_action") or {}
        out["entries"].append({
            "job": j.get("name"), "script_job": bool(j.get("script")) or bool(j.get("no_agent")),
            "hypotheses": len(res["hypotheses"]),
            "top_hypothesis": (res["hypotheses"][0]["hypothesis"] if res["hypotheses"] else None),
            "next_test": nxt.get("test"), "eig_bits": nxt.get("eig_bits"),
        })
    return out


def main(argv):
    if not argv or argv[0] not in ("explain", "fleet"):
        print(__doc__)
        return 1
    if argv[0] == "fleet":
        res = fleet()
        if "--json" in argv:
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0
        print("ABDUCTION / FLEET - anomalies found without being asked")
        print("=" * 74)
        print(f"{res['broken']} of {res['jobs']} cron units are in error state")
        if not res["broken"]:
            print("nothing broken -- no anomaly to explain.")
            return 0
        print("" + chr(10) + "shared signatures (one cause, not many):")
        for g in res["shared_signatures"]:
            print(f"  x{g['count']}  {g['signature'][:56]}")
            print(f"      {', '.join((n or '?')[:26] for n in g['jobs'][:5])}")
        print("" + chr(10) + "per-unit explanation:")
        for e in res["entries"]:
            print(f"  {str(e['job'])[:38]:<38} script_job={e['script_job']}")
            print(f"      top: {str(e['top_hypothesis'])[:88]}")
            print(f"      next test: {e['next_test']} ({e['eig_bits']} bits)")
        print("=" * 74)
        return 0
    if len(argv) < 2:
        print('usage: abduction.py explain "<anomaly text>"')
        return 1
    anomaly = " ".join(a for a in argv[1:] if not a.startswith("--"))
    res = explain(anomaly)

    if "--json" in argv:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["hypotheses"] else 1

    print("ABDUCTION - what might cause this, and what would tell them apart")
    print("=" * 74)
    print(f"anomaly: {anomaly[:110]}")
    if not res["hypotheses"]:
        print("\nNO hypotheses. Nothing in memory, the world model, the skills or")
        print("the cron fleet matches this signature. That is an honest empty")
        print("result, not a failure: the sources have no prior experience with it.")
        print("Next: describe the anomaly with the concrete identifiers (file,")
        print("unit, error string) so the sources can match on something real.")
        return 1

    print(f"\nhypotheses ({len(res['hypotheses'])}) -- provenance kept:")
    for i, h in enumerate(res["hypotheses"], 1):
        print(f"  {i}. [{h['source']}] {h['hypothesis'][:100]}")
        print(f"     evidence: {h['evidence'][:96]}")
        print(f"     predicts: {', '.join(h['predicts']) or 'NOTHING TESTABLE'}")

    if res["untestable"]:
        print(f"\n  !! {len(res['untestable'])} hypothesis(es) predict nothing testable.")
        print("     As stated these are beliefs, not hypotheses -- refine or drop them.")

    if res["tests"]:
        print("\ndiscriminating tests, ranked by information gain per unit cost:")
        print(f"  {'test':<18} {'bits':>6} {'cost':>4} {'bits/cost':>9}  splits")
        print("  " + "-" * 60)
        for r in res["tests"]:
            print(f"  {r['test']:<18} {r['eig_bits']:>6} {r['cost']:>4} "
                  f"{r['eig_per_cost']:>9}  {r['splits']}/{len(res['hypotheses'])}")
        nxt = res["next_action"]
        print(f"\n  ONE NEXT ACTION: run the '{nxt['test']}' check --")
        print(f"    {nxt['description']}")
        print(f"    buys {nxt['eig_bits']} bits, cost {nxt['cost']} "
              f"({nxt['eig_per_cost']} bits/unit). Everything else waits.")
    else:
        print("\nonly one hypothesis -- nothing to discriminate; test it directly.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
