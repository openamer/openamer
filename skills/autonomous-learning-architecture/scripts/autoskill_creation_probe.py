#!/usr/bin/env python3
"""Read-only probe: disambiguate `auto_skill_creation.py`'s "Total: 0 new skills".

Why this exists
---------------
`scripts/training/auto_skill_creation.py` prints a bare counter:

    Total: 0 new skills created

That number is ambiguous. 0 can mean any of five very different things:

  * every scanned insight is already known        -> healthy, nothing novel
  * the inputs are empty / too short / unreadable -> the pipeline is starved
  * the buffer rows exist but none match the
    keyword filter (trending/best practice/...)   -> upstream produces, filter eats it
  * rows are page chrome the junk gate rejected   -> upstream gate, not this script
  * the scan window moved past the good rows      -> silent regression

Never report "0 new skills" as "nothing was learned" without running this.
It replicates the production scan + dedupe logic WITHOUT writing anything,
so it is safe to run on every cycle, and prints the breakdown so the 0 is
readable.

It mirrors auto_skill_creation.py exactly:
  * kta_log.jsonl      -> last 10 lines, needs insight_question + len(answer) > 40
                          (production also appends " GAP: <gap>" to the answer)
  * online_buffer.jsonl-> last 30 lines, `u` must match a keyword AND len(a) > 80
  * name             -> "auto-" + slugify(question)
  * gates            -> the REAL functions (clean_text / is_usable_text /
                        is_domain_relevant) imported from the production module
                        when reachable, length-only fallback otherwise
  * dedupe           -> slug match against skills/auto-generated/ dirs AND the
                         registry's recorded names (name is the primary guard;
                         answer text drifts run-to-run, so text alone is unsafe)

Residual gap, stated honestly: production's `dedupe_check` ALSO rejects a
near-identical *description*. This probe counts name collisions only, so
"candidate-new" is an UPPER bound -- a reported new candidate may still be
dropped by the text path.

Usage
-----
    python skills/autonomous-learning-architecture/scripts/autoskill_creation_probe.py

Exit code is always 0 -- this is an observation tool, not a gate. Read stdout.

Companion proof that nothing was written:
    # the drafts live in the INSTALL, not in a repo checkout:
    ls <install>/skills/auto-generated | wc -l
    grep -o '"count": [0-9]*' <training>/auto_skills.json   # must equal the above
    git -C <install> status --porcelain -- skills/auto-generated   # only if it IS a repo
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

BUFFER_KEYWORDS = ("trending", "best practice", "research", "competitor", "breakthrough")
KTA_MIN_ANSWER = 40
BUF_MIN_ANSWER = 80
KTA_TAIL = 10
BUF_TAIL = 30


def training_dir() -> str:
    """Same canonical resolver as the production script (tolerates stale OPENAMER_HOME)."""
    cands = []
    env = os.environ.get("OPENAMER_HOME")
    if env:
        cands.append(os.path.join(env, "scripts", "training"))
    home = Path.home()
    cands.append(str(home / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training"))
    cands.append(str(Path(__file__).resolve().parent.parent / "training"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return str(home / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training")


def drafts_dir(training: str) -> str:
    """Where the drafts ACTUALLY live -- the trap this probe used to fall into.

    Production writes into the skills dir of the install it runs in. On this
    machine that is `<install>/skills/auto-generated/` (85 dirs measured
    21.09.26), NOT `~/openamer-repo/skills/auto-generated`: the repo checkout
    is a different tree and need not even exist. Resolving the wrong one leaves
    `on_disk` empty, so every already-known skill is reported WOULD-BE-NEW and
    the verdict reads as a dedupe bug that is not there.
    """
    cands = [
        str(Path(training).resolve().parent.parent / "skills" / "auto-generated"),
        str(Path.home() / "AppData" / "Local" / "openamer-laptop" / "skills" / "auto-generated"),
        str(Path.home() / "openamer-repo" / "skills" / "auto-generated"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[1]


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    return "-".join(text.split()[:4])[:40]


def load_production(training: str):
    """Import the real module so the probe uses the REAL gates, not a copy.

    A hand-copied gate is a second implementation that drifts. If the import
    fails (path/name change), the probe degrades to a length-only floor and
    SAYS SO on stdout -- never silently pretends to have applied the gates.
    """
    try:
        if training not in sys.path:
            sys.path.insert(0, training)
        import auto_skill_creation as A  # noqa: N813
        return A
    except Exception:
        return None


def _gate(mod, name):
    fn = getattr(mod, name, None) if mod else None
    return fn if callable(fn) else None


def registry_names(training: str):
    """Recorded skill names plus the declared count, from auto_skills.json."""
    try:
        reg = json.load(open(os.path.join(training, "auto_skills.json"), encoding="utf-8"))
    except Exception:
        return set(), None
    created = reg.get("created", [])
    if isinstance(created, dict):
        created = list(created.values())
    names = {e["name"] for e in (created or []) if isinstance(e, dict) and e.get("name")}
    return names, reg.get("count")


def collect_candidates(training: str):
    """The exact rows the production script would scan, plus the filter rejects."""
    rows, keyword_filtered = [], 0

    kta = os.path.join(training, "kta_log.jsonl")
    if os.path.exists(kta):
        for line in open(kta, encoding="utf-8").readlines()[-KTA_TAIL:]:
            try:
                d = json.loads(line)
            except Exception:
                continue
            rows.append(("kta", d.get("insight_question", ""), d.get("insight_answer", "")))

    buf = os.path.join(training, "online_buffer.jsonl")
    if os.path.exists(buf):
        for line in open(buf, encoding="utf-8").readlines()[-BUF_TAIL:]:
            try:
                d = json.loads(line)
            except Exception:
                continue
            u, a = d.get("u", ""), d.get("a", "")
            if not any(k in u.lower() for k in BUFFER_KEYWORDS):
                keyword_filtered += 1     # never reaches the scanner at all
                continue
            rows.append(("buf", u, a))

    return rows, keyword_filtered


def main() -> None:
    training = training_dir()
    auto_dir = drafts_dir(training)
    A = load_production(training)

    on_disk = set(os.listdir(auto_dir)) if os.path.isdir(auto_dir) else set()
    in_registry, declared = registry_names(training)
    known = on_disk | in_registry

    rows, keyword_filtered = collect_candidates(training)
    print(f"training dir : {training}")
    print(f"drafts dir   : {auto_dir}")
    print(f"gates        : {'production module imported' if A else 'FALLBACK length-only (import failed)'}")
    print(f"scanned rows : {len(rows)}  (kta tail {KTA_TAIL} + buffer tail {BUF_TAIL})")
    print(f"keyword-drop : {keyword_filtered}  (buffer rows with no trending/best practice/... token)")
    print()

    clean = _gate(A, "clean_text")
    usable = _gate(A, "is_usable_text")
    domain = _gate(A, "is_domain_relevant")
    slug = _gate(A, "slugify") or slugify

    too_short = unusable = off_domain = known_hits = new = 0
    seen = set()
    for src, q, a in rows:
        floor = KTA_MIN_ANSWER if src == "kta" else BUF_MIN_ANSWER
        if not q or len(a) <= floor:
            too_short += 1
            continue
        text = clean(a) if clean else a
        if usable and not usable(text):
            unusable += 1
            continue
        if src == "buf" and domain and not domain(text):
            off_domain += 1
            continue
        name = "auto-" + slug(q)
        if name in known:
            known_hits += 1
        elif name in seen:
            known_hits += 1            # duplicate question inside the scan window
        else:
            seen.add(name)
            new += 1
            print(f"  WOULD-BE-NEW [{src}]: {name}  <- {(q or '')[:70]}")

    print()
    print(f"dedupe-known    : {known_hits}")
    print(f"empty/too-short : {too_short}")
    print(f"gate-rejected   : {unusable} unreadable + {off_domain} off-domain")
    print(f"candidate-new   : {new}   (upper bound: production also rejects near-identical text)")
    print(f"drafts on disk  : {len(on_disk)}   names in registry: {len(in_registry)}"
          f"   declared count: {declared}")
    if declared is not None and declared != len(on_disk):
        print(f"  WARN: declared count ({declared}) != draft dirs on disk ({len(on_disk)})"
              " -> registry drift, inspect auto_skills.json")
    elif declared is None:
        # Never let an unparsed key read as "counts agree". This machine's
        # auto_skills.json carries the count under a key this probe may not
        # name (`"count"` seen 21.09.26) -- say so instead of staying silent.
        print(f"  NOTE: no \"count\" key recovered from auto_skills.json -- cannot compare "
              f"against {len(on_disk)} draft dirs on disk (registry may use another key).")
    print()

    if new:
        print(f"VERDICT: {new} genuine candidate(s) exist but the script created none -- "
              "investigate dedupe_check / is_usable_text / is_domain_relevant.")
    elif known_hits:
        print("VERDICT: 0 is GENUINE -- inputs were read, all candidates already known.")
    elif not rows and keyword_filtered:
        print("VERDICT: 0 is FILTERED -- the buffer has rows, none carry a trigger keyword "
              "(trending/best practice/research/competitor/breakthrough). Upstream IS producing; "
              "the keyword filter, not the learner, decides this cycle.")
    elif not rows:
        print("VERDICT: 0 is STARVED -- no rows scanned. Upstream (internet_learner / "
              "knowledge_to_action) produced nothing; fix upstream, not this script.")
    else:
        print("VERDICT: 0 with only too-short/unreadable/off-domain rows -- check the "
              "learners' junk gate, not the dedupe path.")

    # Freshness of the two inputs tells you whether the pipeline is even running.
    for p in (os.path.join(training, "kta_log.jsonl"),
              os.path.join(training, "online_buffer.jsonl")):
        if os.path.exists(p):
            m = datetime.datetime.fromtimestamp(os.path.getmtime(p))
            print(f"  {os.path.basename(p):22s} mtime {m.isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
