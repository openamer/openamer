#!/usr/bin/env python3
"""
DREAM CYCLE - Nightly sleep-consolidation for OpenAmer.

Like human sleep: replays the day's sessions (REM), extracts recurring
patterns/error-motifs (pattern-matching across days), compresses them into
insights + intentions, writes dreams.json (real content, not skeleton),
and emits a morning "dream report" for the agent to act on.

No other agent framework has a true REM-style cross-session dream phase.
"""
import json, sqlite3, re, sys, os, collections, datetime, pathlib

# Markers only a real OpenAmer home carries. A scratch dir that merely exists
# (e.g. a stray OPENAMER_HOME=/c/tmp/oa-home) must never be adopted as the
# install: the dream would then replay an EMPTY state.db and print a
# "clear night" report for a day full of real episodes.
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth):
    """True when *pth* looks like a real OpenAmer home, not a scratch dir.

    A marker only counts when it carries real content: file markers
    (``config.yaml``/``.env``) must be non-empty, and directory markers
    (``cron``/``memories``/``openamer-agent``) must hold at least one
    NON-EMPTY file. ``any(p.iterdir())`` was not enough -- the live scratch
    tree ``OPENAMER_HOME=C:/Users/damir/_vaultfinal`` carries
    ``cron/executions.db`` at 0 bytes plus an empty ``memories/``, so a
    0-byte file proved "install" and it was adopted over the real 189-skill
    install.
    """
    try:
        for m in _HOME_MARKERS:
            p = pth / m
            if p.is_file():
                if p.stat().st_size > 0:
                    return True
            elif p.is_dir():
                for child in p.iterdir():
                    if child.is_file() and child.stat().st_size > 0:
                        return True
        return False
    except OSError:
        return False


def _resolve_home():
    """Resolve OPENAMER_HOME robustly across shells.

    The cron ticker runs this script through git-bash, which exports
    OPENAMER_HOME in MSYS form (/c/tmp/oa-home). Native Windows Python treats
    that as a RELATIVE path and expands it to a phantom C:\\c\\tmp\\oa-home
    tree, so the dream replayed 0 messages while the real state.db held
    hundreds -- a green "clear night" report for a day that was never read.
    Normalise MSYS drive forms and only accept a candidate that is a real
    install root.
    """
    local = pathlib.Path.home() / "AppData" / "Local"
    candidates = [local / "openamer-laptop", local / "openamer"]
    default = next((c for c in candidates if (c / "skills").is_dir()),
                   candidates[0])

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default

    cand = None
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    # MSYS / Git-bash drive form: /c/Users/... -> C:/Users/...
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = pathlib.Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = pathlib.Path(raw)
        if p.is_absolute():
            cand = p

    if cand is not None and cand.exists() and _is_install_root(cand):
        return cand
    if cand is not None and cand.exists():
        print(f"[dream] WARNING: OPENAMER_HOME={cand} exists but is not an "
              f"OpenAmer install root (no {'/'.join(_HOME_MARKERS)}); "
              f"falling back to {default}.", file=sys.stderr)
    return default


BASE = _resolve_home()
STATE_DB = BASE / "state.db"
DREAMS = BASE / "dreams.json"
REPORTS = BASE / "reports"
REPORTS.mkdir(exist_ok=True)

# error-motif lexicon (grows via memory; today: curated seeds)
MOTIFS = {
    "timeout": r"timeout|timed out|ETIMEDOUT",
    "permission": r"permission denied|EACCES|Zugriff verweigert",
    "path-bug": r"No such file|ENOENT|not found.*(path|file)",
    "auth": r"401|403|unauthorized|token invalid|login failed",
    "build": r"build failed|compile error|SyntaxError|ModuleNotFound",
    "api-rate": r"429|rate limit|quota exceeded",
    "memory": r"MemoryError|out of memory|OOM",
}

def today():
    return datetime.date.today().isoformat()

def fetch_day_messages(day):
    con = sqlite3.connect(str(STATE_DB))
    rows = con.execute(
        "SELECT role, content FROM messages WHERE date(timestamp, 'unixepoch') = ? AND role IN ('user','assistant')",
        (day,)
    ).fetchall()
    con.close()
    return rows

def extract_error_snippets(text):
    """REM-style replay: pull short fragments around failures."""
    frags = []
    for m in re.finditer(r"(error|Error|ERROR|Exception|failed|Failed)[^\n]{0,120}", text or ""):
        frags.append(m.group(0).strip()[:150])
    return frags

def detect_motifs(frags):
    hits = collections.Counter()
    for f in frags:
        for name, pat in MOTIFS.items():
            if re.search(pat, f, re.I):
                hits[name] += 1
    return dict(hits)

def cross_day_recurrence(dreams, motif):
    """How many past days saw this motif? Recurrence = true 'nightmare'."""
    return sum(1 for d in dreams if motif in d.get("_motifs", {}))

def dream(day=None):
    day = day or today()
    dreams = json.loads(DREAMS.read_text(encoding="utf-8")) if DREAMS.exists() else []
    msgs = fetch_day_messages(day)
    all_frags = []
    for role, content in msgs:
        all_frags += extract_error_snippets(content)

    motifs = detect_motifs(all_frags)

    # insights: motifs seen today, annotated with recurrence
    insights = []
    for motif, count in sorted(motifs.items(), key=lambda x: -x[1]):
        rec = cross_day_recurrence([d for d in dreams if d["date"] < day], motif)
        insights.append({
            "motif": motif,
            "occurrences": count,
            "recurrence_days": rec,
            "nightmare": rec >= 3,   # 3+ days = recurring nightmare -> fix at root
        })

    # intentions: top recurring motifs become tomorrow's intentions
    intentions = [
        {"action": f"Fix recurring motif '{i['motif']}' at root (Skill/repo patch)"}
        for i in insights if i["nightmare"]
    ]
    if not intentions and insights:
        intentions = [{"action": f"Review motif '{insights[0]['motif']}' if it recurs"}]

    entry = {
        "date": day,
        "replayed_messages": len(msgs),
        "fragments": len(all_frags),
        "_motifs": motifs,
        "insights": insights,
        "intentions": intentions,
    }

    # upsert
    dreams = [d for d in dreams if d["date"] != day] + [entry]
    dreams.sort(key=lambda d: d["date"])
    for d in dreams:
        d.pop("_motifs", None)  # internal field not persisted
    # re-add _motifs for recurrence calc (keep in-memory only)
    dreams_persist = [ {k: v for k, v in d.items()} for d in dreams ]

    DREAMS.write_text(json.dumps(dreams_persist, indent=2, ensure_ascii=False), encoding="utf-8")

    # morning report
    rep = REPORTS / f"dream-{day}.md"
    lines = [f"# Dream Report {day}", "",
             f"- Replayed {len(msgs)} messages, {len(all_frags)} error fragments", ""]
    lines.append("## Insights")
    for i in insights:
        tag = " ⚠️ NIGHTMARE (recurring)" if i["nightmare"] else ""
        lines.append(f"- `{i['motif']}`: {i['occurrences']}x today, seen on {i['recurrence_days']} prior days{tag}")
    if not insights:
        lines.append("- Clear night, no error motifs.")
    lines.append("")
    lines.append("## Intentions for today")
    for it in intentions:
        lines.append(f"- {it['action']}")
    rep.write_text("\n".join(lines), encoding="utf-8")
    return str(rep)

if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv) > 1 else None
    print("REPORT:" + dream(day))
