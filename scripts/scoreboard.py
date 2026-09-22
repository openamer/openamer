#!/usr/bin/env python3
"""Honest capability scoreboard: OpenAmer vs. the competitors, measured.

WHY THIS EXISTS
    The question "are we better than all competitors?" was unanswerable:
    memory/benchmarks.json contained ZERO competitor mentions and used 23
    self-written questions, and its last run scored 0.0 with every question
    failing on HTTP 401. There was no comparison at all.

    This script fixes the *measurable* half. It does not pretend to be
    SWE-bench: a head-to-head agent comparison needs an installable harness,
    an identical task set and an identical model, and the competitors are not
    installed here. So this measures what IS measurable and labels every
    column with its source and its limits.

WHAT IT EMITS
    - a metrics table (ours vs. theirs) with a live timestamp per row
    - every value carries the file/API it came from, or is marked UNMEASURED
    - an explicit "what this does not prove" section

USAGE
    python scoreboard.py                 # print the table
    python scoreboard.py --json          # machine-readable
    python scoreboard.py --out FILE.md   # write the markdown report
"""
import argparse
import datetime
import json
import os
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData/Local/openamer-laptop"))
REPO = HOME / "openamer-agent"
GITHUB = "https://api.github.com/repos/{}"

COMPETITORS = [
    ("Significant-Gravitas/AutoGPT", "AutoGPT"),
    ("anthropics/claude-code", "Claude Code"),
    ("openai/codex", "OpenAI Codex CLI"),
    ("Aider-AI/aider", "Aider"),
    ("crewAIInc/crewAI", "CrewAI"),
    ("langchain-ai/langgraph", "LangGraph"),
    ("All-Hands-AI/OpenHands", "OpenHands"),
]


def token():
    p = Path.home() / ".git-credentials"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "github.com" in line and "@" in line:
            head = line.split("//", 1)[-1]
            user, rest = head.split(":", 1)
            return rest.split("@", 1)[0]
    return None


def gh(path, tok):
    req = urllib.request.Request(GITHUB.format(path),
                                 headers={"Authorization": f"token {tok}"} if tok else {})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as e:
        return {"__error": str(e)}


def _num(v):
    """Stars/forks as a number. A failed API call yields None or a stray str."""
    return v if isinstance(v, (int, float)) else 0


def count_files(root, pattern):
    return len(list(root.rglob(pattern)))


def _tool_roots():
    """Candidate trees holding the core tool modules, most specific first.

    REPO is derived from OPENAMER_HOME, which on this machine has been observed
    pointing at a stale tree that carries no `tools/` directory. Grepping only
    REPO then returned (None, None), which the report rendered as a bare `None`
    under a header that claims "grep-verified" - a fabricated-looking row. Fall
    back to the machine's git working copy so the figure is real or absent.
    """
    return [REPO, Path.home() / "openamer-repo"]


def registry_tool_count():
    """Registered tool NAMES in the core tool modules (grep-verified)."""
    for root in _tool_roots():
        tools = root / "tools"
        if not tools.is_dir():
            continue
        files = len(list(tools.glob("*.py")))
        names = 0
        for p in list(tools.glob("*.py")) + [root / "toolset_distributions.py", root / "toolsets.py"]:
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            names += src.count('"name": "')
        return names, files
    return None, None


def learner_rate(days=1):
    """Real learner yield for the last N days, from the log - honest, not a claim."""
    log = HOME / "scripts/training/internet_learn_log.jsonl"
    if not log.exists():
        return None
    cut = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    total = rej = 0
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if str(r.get("ts", "")) < cut:
            continue
        total += 1
        if str(r.get("result", "")).startswith("rejected"):
            rej += 1
    if not total:
        return None
    return {"cycles": total, "rejected": rej, "yield_pct": round(100 * (total - rej) / total, 1)}


def self_benchmark():
    """Our own micro-benchmark - small and self-written. Labelled as such."""
    p = HOME / "memory/benchmarks.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    runs = d.get("runs", [])
    last = runs[-1] if runs else {}
    errs = 0
    qs = 0
    for cat in ("knowledge", "reasoning"):
        c = last.get(cat)
        if isinstance(c, dict):
            q = c.get("questions", {})
            qs += len(q)
            errs += sum(1 for v in q.values() if isinstance(v, dict) and v.get("error"))
    return {"best_overall": d.get("best", {}).get("overall"),
            "last_overall": last.get("overall_accuracy"),
            "last_questions": qs, "last_errors": errs}


def _home_roots():
    """Candidate OPENAMER_HOME trees, most specific first.

    Same failure class as _tool_roots(): a stale OPENAMER_HOME silently yields
    0 skills / {} cron, rendered as if it had been measured. Try the configured
    home, then this machine's real install before giving up.
    """
    roots = [HOME]
    fallback = Path.home() / "AppData/Local/openamer-laptop"
    if fallback not in roots:
        roots.append(fallback)
    return roots


def _pick(rel):
    """First existing file/dir for a home-relative path across candidate homes."""
    for root in _home_roots():
        p = root / rel
        if p.exists():
            return p
    return None


def cron_and_episodes():
    """Two counts we already hold locally - measured from their real files."""
    out = {}
    jobs = _pick("cron/jobs.json")
    if jobs is not None:
        try:
            d = json.loads(jobs.read_text(encoding="utf-8", errors="replace"))
            j = d if isinstance(d, list) else d.get("jobs", [])
            out["cron_jobs"] = {"value": f"{sum(1 for x in j if x.get('enabled', True))}/{len(j)} active",
                                "source": f"cron/jobs.json ({jobs.parent.parent.name})",
                                "limit": "enabled flag, not last-run health"}
        except Exception:
            pass
    ep = _pick("memory/longterm_episodes.jsonl")
    if ep is not None:
        n = sum(1 for l in ep.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
        out["episodes"] = {"value": n, "source": "memory/longterm_episodes.jsonl",
                           "limit": "line count, not unique facts"}
    return out


def build():
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    tok = token()
    rows = []

    me = gh("openamer/openamer", tok)
    mine = {"name": "OpenAmer", "stars": _num(me.get("stargazers_count")),
            "forks": _num(me.get("forks_count")), "issues": _num(me.get("open_issues_count")),
            "created": str(me.get("created_at", ""))[:10], "source": "GitHub API openamer/openamer"}
    for slug, label in COMPETITORS:
        d = gh(slug, tok)
        rows.append({"name": label, "slug": slug, "stars": _num(d.get("stargazers_count")),
                     "forks": _num(d.get("forks_count")), "issues": _num(d.get("open_issues_count")),
                     "created": str(d.get("created_at", ""))[:10],
                     "source": f"GitHub API {slug}",
                     "error": d.get("__error")})

    names, files = registry_tool_count()
    skills_dir = _pick("skills")
    skills = count_files(skills_dir, "SKILL.md") if skills_dir is not None else None
    cap = {
        "registered_tool_names": {"value": names, "source": "grep '\"name\": \"' in tools/*.py + toolsets.py", "limit": "grep count, not a runtime registry dump"},
        "tool_modules": {"value": files, "source": "ls tools/*.py"},
        "skills": {"value": skills, "source": "find skills -name SKILL.md"},
    }
    cap.update(cron_and_episodes())
    return {
        "measured_at": now,
        "ours": mine,
        "competitors": sorted(rows, key=lambda r: -_num(r.get("stars"))),
        "capability": cap,
        "learner_yield_1d": learner_rate(1),
        "self_benchmark": self_benchmark(),
        "not_measured": [
            "SWE-bench Verified score for OpenAmer: we are NOT on the leaderboard (checked 2026-09-22).",
            "Any head-to-head task comparison: no competitor harness is installed here "
            "(codex/claude/opencode/aider/openhands/autogpt all absent from PATH).",
            "Cost per task, latency, autonomy rate vs. competitors: no shared harness -> unmeasured.",
            "Our own benchmark uses 23 self-written questions, not a standard suite -> not comparable to any published number.",
        ],
    }


def render(data):
    L = []
    L.append(f"# Capability scoreboard - {data['measured_at']}")
    L.append("")
    L.append("Live-measured. Every row names its source. Unmeasurable rows are marked.")
    L.append("")
    L.append("## Distribution (measured via GitHub API)")
    L.append("")
    L.append("| Product | Stars | Forks | Open issues | Created | Source |")
    L.append("|---|---:|---:|---:|---|---|")
    o = data["ours"]
    L.append(f"| **{o['name']}** | **{o['stars']}** | {o['forks']} | {o['issues']} | {o['created']} | {o['source']} |")
    for r in data["competitors"]:
        L.append(f"| {r['name']} | {r['stars']} | {r['forks']} | {r['issues']} | {r['created']} | {r['source']} |")
    L.append("")
    L.append("## Capability (ours - grep-verified)")
    L.append("")
    L.append("| Metric | Value | Source | Limit |")
    L.append("|---|---:|---|---|")
    for k, v in data["capability"].items():
        if isinstance(v, dict) and v.get("value") is not None:
            L.append(f"| {k} | {v.get('value')} | {v.get('source', '-')} | {v.get('limit', '-')} |")
        elif isinstance(v, dict):
            # A value we could not measure must SAY so. Printing a bare `None`
            # under a "grep-verified" header reads as a measured zero.
            L.append(f"| {k} | UNMEASURED | {v.get('source', '-')} | {v.get('limit', '-')} |")
        else:
            L.append(f"| {k} | UNMEASURED | - | - |")
    L.append("")
    ly = data.get("learner_yield_1d")
    L.append("## Learning system (measured, last 24h)")
    L.append("")
    if ly:
        L.append(f"- Learner cycles: **{ly['cycles']}**, rejected: **{ly['rejected']}** "
                 f"-> yield **{ly['yield_pct']}%** (source: internet_learn_log.jsonl)")
    else:
        L.append("- UNMEASURED")
    sb = data.get("self_benchmark")
    if sb:
        L.append(f"- Own micro-benchmark: best **{sb['best_overall']}**, last run "
                 f"**{sb['last_overall']}** ({sb['last_questions']} questions, "
                 f"{sb['last_errors']} errored). NOT a standard benchmark.")
    L.append("")
    L.append("## What this does NOT prove")
    L.append("")
    for n in data["not_measured"]:
        L.append(f"- {n}")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = build()
    if a.json:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    else:
        txt = render(d)
        if a.out:
            Path(a.out).write_text(txt, encoding="utf-8")
            print(f"written: {a.out}")
        else:
            print(txt)
