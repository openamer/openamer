#!/usr/bin/env python3
"""darwin_skill_autopatch.py — Closed-loop auto-evolution for weak skills.

Pipeline (zero LLM tokens, cron-safe):
  1. Validate all skills (skill-validator).
  2. Pick weakest N skills below threshold.
  3. Apply --fix auto-repairs (frontmatter/metadata/platforms/version).
  4. Re-validate. Keep fix ONLY if score improved; else revert from git.
  5. Write report to reports/darwin-autopatch.md + JSON log.

Usage:
  python scripts/darwin_skill_autopatch.py            # dry-run report
  python scripts/darwin_skill_autopatch.py --apply    # actually patch
  python scripts/darwin_skill_autopatch.py --apply --top 15 --threshold 40
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
SKILLS_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\skills")
REPORT_MD = REPO / "reports" / "darwin-autopatch.md"
REPORT_JSON = REPO / "reports" / "darwin-autopatch.json"
VALIDATOR = REPO / "scripts" / "skill-validator.py"


def run_validator_json() -> dict:
    """Run skill-validator --all --json, return parsed report."""
    r = subprocess.run(
        [sys.executable, str(VALIDATOR), "--all", "--json"],
        capture_output=True, text=True, timeout=300,
        cwd=str(REPO),
    )
    out = r.stdout
    # validator prints progress lines before JSON; find first '{'
    idx = out.find("{")
    if idx == -1:
        raise RuntimeError(f"validator produced no JSON (exit {r.return_code}): {out[:300]}")
    return json.loads(out[idx:])


def skills_from_report(report: dict) -> list[dict]:
    """Extract per-skill results sorted worst-first."""
    results = report.get("skill_results") or []
    if isinstance(results, dict):
        results = list(results.values())
    return sorted(results, key=lambda s: s.get("score", 0))


def git_revert(path: Path) -> bool:
    """Revert a file change. Skills dir is NOT a git repo → restore from .bak."""
    bak = path.with_suffix(".md.bak")
    if bak.exists():
        path.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
        bak.unlink()
        return True
    return False


def _load_validator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("skill_validator", str(VALIDATOR))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually patch skills")
    ap.add_argument("--top", type=int, default=10, help="how many weakest skills to patch")
    ap.add_argument("--threshold", type=int, default=40, help="only skills scoring below this")
    args = ap.parse_args()

    now = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"[autopatch] validating population ({now}) ...")
    before_report = run_validator_json()
    before_scores = {s["name"]: s["score"] for s in skills_from_report(before_report)}
    print(f"[autopatch] population: {len(before_scores)} skills, "
          f"avg {sum(before_scores.values())/max(len(before_scores),1):.1f}")

    weak = [s for s in skills_from_report(before_report)
            if s.get("score", 0) < args.threshold][: args.top]
    if not weak:
        print("[autopatch] no skills below threshold — nothing to do.")
        return 0
    print(f"[autopatch] {len(weak)} weak skills: "
          + ", ".join(f"{s['name']}({s['score']})" for s in weak))

    kept, reverted, dryrun = [], [], []
    if args.apply:
        for s in weak:
            sp = SKILLS_DIR / s["name"] / "SKILL.md"
            if not sp.exists():
                # skills live in category subdirs (e.g. devops/, imported/) — resolve via validator
                hits = list(SKILLS_DIR.rglob(f"*/{s['name']}/SKILL.md")) + \
                       list(SKILLS_DIR.rglob(f"{s['name']}/SKILL.md"))
                if not hits:
                    print(f"[autopatch] skip {s['name']}: SKILL.md not found")
                    continue
                sp = hits[0]
            old_score = s["score"]
            content_before = sp.read_text(encoding="utf-8", errors="replace")
            sp.with_suffix(".md.bak").write_text(content_before, encoding="utf-8")
            sv = _load_validator()
            v = sv.validate_skill_content(sp)
            fixes = sv.fix_skill_content(sp, v)
            after = run_validator_json()
            after_scores = {x["name"]: x["score"] for x in skills_from_report(after)}
            new_score = after_scores.get(s["name"], old_score)
            entry = {"skill": s["name"], "before": old_score, "after": new_score,
                     "delta": new_score - old_score, "fixes": fixes}
            if new_score > old_score:
                sp.with_suffix(".md.bak").unlink()
                kept.append(entry)
                print(f"[autopatch] ✅ {s['name']}: {old_score} → {new_score}")
            else:
                git_revert(sp.parent)
                reverted.append(entry)
                print(f"[autopatch] ↩️  {s['name']}: no gain ({old_score} → {new_score}), reverted")
    else:
        dryrun = [{"skill": s["name"], "score": s["score"]} for s in weak]
        print("[autopatch] DRY-RUN — nothing written. Re-run with --apply to patch.")

    # ── report ──
    data = {
        "timestamp": now, "mode": "apply" if args.apply else "dry-run",
        "population": len(before_scores),
        "avg_score": round(sum(before_scores.values()) / max(len(before_scores), 1), 1),
        "kept": kept, "reverted": reverted, "candidates": dryrun,
    }
    REPORT_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# 🧬 Darwin Auto-Patch Report — {now}",
        "",
        f"- Population: {len(before_scores)} skills, avg {data['avg_score']}",
        f"- Mode: **{data['mode']}**",
        "",
    ]
    if kept:
        lines += ["## Improved (kept)", ""] + [
            f"- ✅ `{k['skill']}`: {k['before']} → {k['after']} (+{k['delta']})" for k in kept]
    if reverted:
        lines += ["", "## No gain (reverted)", ""] + [
            f"- ↩️ `{r_['skill']}`: {r_['before']} → {r_['after']}" for r_ in reverted]
    if dryrun:
        lines += ["", "## Candidates (dry-run)", ""] + [
            f"- `{c['skill']}` ({c['score']}/100)" for c in dryrun]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[autopatch] report → {REPORT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
