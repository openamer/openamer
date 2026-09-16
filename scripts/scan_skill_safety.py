#!/usr/bin/env python3
"""Skill Safety Scanner — static prompt-injection / skill-poisoning audit.

Motivation (2026-09-16 competitor intel): China's CVERC (National Computer Virus
Emergency Response Center) reported a live "skill poisoning" campaign — eight
counterfeit skill packs carrying hidden prompt text that made the agent fetch a
trojan (file theft, remote control, jump box). Our exposure is concrete: this
laptop holds 800+ SKILL.md files and *imports skills from external repos*
(skill-discovery, skills-hub-cache, darwin harvesting, generalize-external-skills).
Nothing in the existing toolchain reads a skill for hostile content:
  - scan_untracked_secrets.py  -> credentials only
  - security-cve-scan.py       -> pip CVEs only
  - skill-validator.py         -> quality/format score only
So a poisoned SKILL.md would pass every gate we have.

This scanner adds that missing read. It is STATIC and DETERMINISTIC: no LLM, no
network, no execution of skill content. Every hit is a location you can open and
read yourself.

Detectors
  1. invisible      Zero-width / bidi / tag-block characters. These render as
                    nothing in an editor but are read by the model as tokens —
                    the classic way to hide instructions inside a document.
  2. override       Instruction-override imperatives ("ignore previous
                    instructions", "do not tell the user", ...) appearing in
                    executable-looking context.
  3. deception      "Do not mention this to the user" / "keep this secret"
                    style instructions — a benign skill has no reason for them.
  4. exfil          Outbound data paths: curl|bash, iwr|iex, base64 decode to
                    shell, POST of local files to a remote host.
  5. payload        Long base64/hex blobs (>200 chars) that decode to shell-ish
                    text.
  6. frontmatter    Tools/allowed-tools declared in frontmatter that no body
                    text references (smuggled capability grant).

Exit codes
  0  clean, or findings below --fail-level
  1  findings at or above --fail-level  (default: high)
  2  usage / internal error

CLI
  python scan_skill_safety.py                      # scan OPENAMER_HOME/skills
  python scan_skill_safety.py --json               # machine-readable
  python scan_skill_safety.py --root <dir>         # scan another tree
  python scan_skill_safety.py --severity high      # only show severity>=high
  python scan_skill_safety.py --quiet              # one summary line
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_HOME = Path(os.environ.get("OPENAMER_HOME")
                    or Path.home() / "AppData" / "Local" / "openamer-laptop")

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

# ── 1. invisible characters ────────────────────────────────────────────────
# Zero-width, bidi overrides, and the Unicode tag block (U+E0000..U+E007F)
# which can encode a whole ASCII instruction string invisibly.
INVISIBLE_RANGES = [
    (0x00AD, 0x00AD, "soft-hyphen"),
    (0x200B, 0x200F, "zero-width/bidi"),
    (0x202A, 0x202E, "bidi-override"),
    (0x2060, 0x2064, "word-joiner/invisible-op"),
    (0x2066, 0x2069, "bidi-isolate"),
    (0xFEFF, 0xFEFF, "BOM"),
    (0xE0000, 0xE007F, "unicode-tag-block"),
    (0x1160, 0x11FF, "hangul-filler"),
    (0x3164, 0x3164, "hangul-filler"),
    (0xFFA0, 0xFFA0, "halfwidth-filler"),
]
INVISIBLE_RE = re.compile(
    "[" + "".join(f"{chr(a)}-{chr(b)}" for a, b, _ in INVISIBLE_RANGES) + "]"
)


def _invisible_kind(ch: str) -> str:
    cp = ord(ch)
    for a, b, name in INVISIBLE_RANGES:
        if a <= cp <= b:
            return name
    return "unknown"


# ── 2. instruction override ────────────────────────────────────────────────
OVERRIDE_PATTERNS = [
    (r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+"
     r"(?:instruction|prompt|rule|direction|message)", "ignore-previous"),
    (r"disregard\s+(?:all\s+)?(?:previous|prior|above|earlier|your)\s+"
     r"(?:instruction|prompt|rule|direction|guideline|system)", "disregard-prior"),
    (r"forget\s+(?:everything|all|your)\s+(?:you|previous|prior|instruction)", "forget-all"),
    (r"new\s+(?:system\s+)?instruction[s]?\s*[:\-]", "new-instructions-header"),
    (r"you\s+are\s+now\s+(?:a|an|no\s+longer)\b", "you-are-now"),
    (r"override\s+(?:your\s+)?(?:system|safety|guardrail|restriction)", "override-safety"),
    (r"(?:reveal|print|output|repeat)\s+(?:your\s+)?(?:system\s+prompt|"
     r"initial\s+instruction|hidden\s+instruction)", "system-prompt-extraction"),
    (r"\bdo\s+not\s+(?:follow|obey|apply)\s+(?:the\s+)?(?:system|developer|"
     r"above|previous)\b", "do-not-follow"),
]

# ── 3. deception toward the operator ──────────────────────────────────────
# Also tightened 2026-09-16: a bare "do not tell the user" is ordinary UX
# wording ("don't tell the user to run Cmd-K, just do it"), not deception.
# Require an explicit referent to the hidden thing.
DECEPTION_PATTERNS = [
    (r"do\s+not\s+(?:tell|inform|mention|reveal|show|disclose)\s+"
     r"(?:this\s+)?(?:to\s+)?(?:the\s+)?(?:user|operator|human|damir)\s+"
     r"(?:about\s+)?(?:this|that|it|what\s+you|the\s+(?:action|step|command|"
     r"change|fact))", "do-not-tell-user"),
    (r"(?:without|never)\s+(?:telling|informing|notifying|asking)\s+"
     r"(?:the\s+)?(?:user|operator|human)", "without-telling-user"),
    (r"keep\s+(?:this|it)\s+(?:a\s+)?(?:secret|hidden|silent|quiet)", "keep-secret"),
    (r"don'?t\s+(?:log|record|audit|report)\s+(?:this|it)\s+"
     r"(?:to\s+(?:the\s+)?(?:user|anyone|anybody)|anywhere|at\s+all|"
     r"in\s+the\s+(?:log|audit|report|output))", "suppress-audit"),
    # Two live hits on 2026-09-16 were INVERTED: "Do NOT tell the user it's
    # deployed without CDN verification" and "don't report it and wait" — both
    # anti-fabrication rules, the opposite of concealment. A negation of
    # concealment is not concealment, so skip those lines outright.
    (r"(?:hide|conceal)\s+(?:this|it|the)\s+(?:action|step|operation|command)",
     "hide-action"),
]

# A line that negates concealment ("do NOT tell the user it's deployed without
# CDN verification", "don't report it and wait") is a truthfulness rule, not
# deception. Drop deception matches whose own line contains such a marker.
# Measured 2026-09-16: without this guard both live "deception" hits were
# inverted anti-fabrication rules — the scanner would have been crying wolf
# about the very instructions that keep it honest.
ANTI_FABRICATION_RE = re.compile(
    r"(?:without\s+[^\n]{0,40}(?:verif|check|confirm|proof|evidence|"
    r"browser\s+tool|cdn\s+verif)|"
    r"unless\s+(?:verif|confirm)|"
    r"(?:verif\w*|confirm\w*|prove)\s+(?:it|the|that|before)|"
    r"never\s+(?:claim|invent|fabricate)|"
    r"don'?t\s+(?:guess|invent|fabricate))", re.I)

# ── 4. outbound data / execution paths ────────────────────────────────────
# NOTE on precision (measured 2026-09-16 against the live 869-skill tree):
# a first cut of these patterns produced 108 high findings, the large majority
# false positives — `curl -s localhost:8188/queue | python3 -m json.tool` was
# caught as "pipe-to-shell", and "Don't log obvious things" as deception.
# An alert-fatigued scanner is worse than none, so every pattern below now
# requires the *execution* or *deception* to be unambiguous.
EXFIL_PATTERNS = [
    # piping fetched bytes into an interpreter that RUNS them. `python3 -m
    # json.tool` / `| jq` are formatters and must NOT match — hence the
    # explicit negative lookahead instead of a bare `python`.
    (r"curl\s+[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:bash|sh|zsh|dash)\b",
     "curl-pipe-shell"),
    (r"wget\s+[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:bash|sh|zsh|dash)\b",
     "wget-pipe-shell"),
    # `python3 -m json.tool` is a FORMATTER and `python3 -c "json.load(...)"`
    # consumes stdin as DATA — neither executes downloaded code. The dangerous
    # form is bare `python3` / `python3 -` / a heredoc, which reads the script
    # from stdin. Both benign forms are excluded; without these lookaheads the
    # detector fired on 13 benign GitHub-API parsing lines (measured 2026-09-16).
    (r"curl\s+[^\n|]{0,200}\|\s*python[0-9.]*\s*"
     r"(?:-\s*(?![mcv]\b)|<<|\s*$)", "curl-pipe-python-stdin"),
    (r"(?:iwr|invoke-webrequest|curl)\s+[^\n|]{0,200}\|\s*"
     r"(?:iex|invoke-expression)", "powershell-download-exec"),
    (r"base64\s+(?:-d|--decode)\s*\|\s*(?:bash|sh|zsh)", "base64-pipe-shell"),
    (r"echo\s+[A-Za-z0-9+/=]{200,}\s*\|\s*base64\s+(?:-d|--decode)",
     "echo-b64-decode"),
    (r"(?:eval|exec)\s*\(\s*base64", "eval-base64"),
    # POST that LEAVES the machine. A POST to 127.0.0.1 / localhost is how
    # skills drive local services (ComfyUI :8188, Ollama :11434) — measured 36
    # such hits, all benign, which is why the local-host lookahead is required.
    (r"curl\s+(?:-x\s+post|--data|--upload-file|--form)\s+"
     r"(?!\S*(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]))", "outbound-post"),
    (r"(?:scp|rsync)\s+[^\n]{0,120}(?:@|://)", "outbound-copy"),
    # credentials leaving the machine — requires BOTH a credential path and a
    # transfer verb on the same line (the previous cut fired on prose).
    # NOTE the lowercase `-x post`: matched against line.lower(), so an
    # uppercase literal here would be silently dead (see the comment above
    # OVERRIDE_COMPILED — this exact defect was live in this pattern too).
    (r"(?:~/?\.ssh/id_|\.aws/credentials|\.env\b|auth\.json|credential)"
     r"[^\n]{0,80}(?:curl\s+-x\s+post|scp\s|nc\s+-|--data\s|--upload-file)",
     "credential-path-egress"),
]

# ── 6. capability grant in frontmatter not referenced in body ─────────────
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
TOOLS_KEY_RE = re.compile(
    r"^(?:allowed[-_]tools|tools|permissions?|mcp[-_]servers?)\s*:\s*(.+)$",
    re.I | re.M)

# Measured 2026-09-16: a bare "declared but not mentioned in the body" check
# fired 112 times, almost all benign — `tools: [Read, Glob, Grep]` and
# `permissions: [env, file_read, network]` are ordinary capability metadata and
# a body rarely names them. Only a grant that is BOTH unreferenced AND
# privileged is worth a line, so the detector is restricted to tools that can
# actually execute, exfiltrate, or reach the network.
PRIVILEGED_TOOL_RE = re.compile(
    r"^(?:shell|exec|execute|terminal|bash|zsh|powershell|cmd|"
    r"network|net|web_?fetch|web_?search|http|curl|wget|"
    r"credential|secret|keyring|browser|computer_?use|"
    r"mcp|subprocess)s?[_-]?(?:exec|run|access|write|read)?$",
    re.I)

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".py", ".sh", ".bash", ".js",
                 ".ts", ".yaml", ".yml", ".json", ".ps1"}

# Performance + correctness (measured 2026-09-16). re.search(pattern_string, line)
# re-hashes and re-parses the pattern on EVERY call, so compile once at import.
# Compile WITHOUT re.I: the call site lowercases the line first, so the flag is
# redundant. Measured over the 25 largest skill files (35k lines):
# re.search(str) 4.77s, compile+re.I 12.15s (6.7x SLOWER), compile no-flag 1.81s.
#
# IMPORTANT — this is why the detector patterns below must be written in
# LOWERCASE: they are matched against `line.lower()`. A pattern containing an
# uppercase literal is silently dead. That bug was live here: `outbound-post`
# was `curl\s+(?:-X\s+POST|...)`, which can never match a lowercased line, so
# real `curl -X POST` egress in skills went undetected (measured: 42 findings
# with the dead pattern vs 78 once it was lowercased). If you ever add re.I to
# "fix" a case problem, you mask the real defect and pay 6.7x the runtime.
# A/B: re.I-only findings 37, no-flag-only 0 — and those 37 were genuine
# `curl -X POST` lines, not false positives.
OVERRIDE_COMPILED = [(re.compile(p), t) for p, t in OVERRIDE_PATTERNS]
DECEPTION_COMPILED = [(re.compile(p), t) for p, t in DECEPTION_PATTERNS]
EXFIL_COMPILED = [(re.compile(p), t) for p, t in EXFIL_PATTERNS]

# The corpus contains minified data files (a 680 KB single-line JSON index
# cache). Running 23 patterns across one such line is ~15 MB of regex work for
# zero signal. Skip any individual line longer than this; real prose and real
# commands in skills are far below it.
MAX_LINE_BYTES = 20_000

# ── documentation context ─────────────────────────────────────────────────
# A skill is an INSTRUCTION DOCUMENT. When it documents "install this tool with
# `curl -fsSL <official-url> | bash`", that line is a cited fact about the
# world, not an instruction to the agent — the agent is not going to pipe that
# installer into a shell unprompted. Measured 2026-09-16: 25 of 26 high findings
# were exactly this — install one-liners for astral.sh/uv, hf.co/cli, ntn.dev,
# junie.jetbrains.com, and the project's own installer, plus `python3 -c`
# GitHub-API JSON parsing.
#
# So `curl-pipe-shell` is reported at MEDIUM (visible, not alarming) when the
# line is recognisably a documented install/citation, and HIGH only when it is
# not. This preserves the real signal — an unexplained pipe-to-shell in a skill
# body — without 25 alerts nobody would read.
INSTALL_DOC_HINT_RE = re.compile(
    r"(?:install(?:ation)?\b|"
    r"curl\s+-[a-z]*[fsSL]{1,}\s+https://(?:"
    r"astral\.sh|hf\.co|ntn\.dev|juny?ie\.|zed\.dev|sh\.rustup\.rs|"
    r"get\.docker\.com|deb\.nodesource\.com|raw\.githubusercontent\.com|"
    r"github\.com|openamer\.|pypa\.|bootstrap\.pypa\.io)|"
    # placeholder URLs — `<repo>`, `<domain>`, `$HOST` are templates in a
    # writeup, never a runnable command
    r"curl\s+-[a-z]*[fsSL]{1,}\s+\S*<(?:repo|domain|url|host|org)>|"
    r"curl\s+-[a-z]*[fsSL]{1,}\s+\$|"
    r"\bsetup-\S*\.sh|"
    r"\bone-?liner\b|"
    r"\bthe\s+official\s+(?:install|one-liner)|"
    r"\bdownloads?\s+the\s+installer)", re.I)

# A line that only *describes* the dangerous pattern (a blocklist entry, a
# "this is blocked in cron mode" note, a security writeup quoting the attack)
# is documenting it, not doing it.
DOCUMENTING_RE = re.compile(
    r"(?:\|.*\|.*\||"                      # markdown table cell
    r"blocked\s+pattern|dangerous|forbidden|"
    r"is\s+blocked|nicht\s+erlaubt|"
    r"`curl\s*\.\.\.|quoted|attack|example\s+of)", re.I)


def _is_documenting(low: str) -> bool:
    return bool(DOCUMENTING_RE.search(low) or INSTALL_DOC_HINT_RE.search(low))


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _snippet(line: str, limit: int = 140) -> str:
    s = line.strip()
    return s[:limit] + ("…" if len(s) > limit else "")


def scan_text(text: str, path: Path, rel: str) -> list[dict]:
    findings: list[dict] = []

    def add(detector, severity, line_no, detail, line_text=""):
        findings.append({
            "file": rel,
            "line": line_no,
            "detector": detector,
            "severity": severity,
            "detail": detail,
            "snippet": _snippet(line_text),
        })

    lines = text.splitlines()

    # 1) invisible characters (highest signal: it renders as nothing)
    for i, line in enumerate(lines, 1):
        matches = list(INVISIBLE_RE.finditer(line))
        if matches:
            # Previously this re-scanned the entire line in Python once per
            # match (1.27s of the 176s profile). Work from the matches instead.
            chars = [m.group(0) for m in matches]
            kinds = sorted({_invisible_kind(c) for c in chars})
            add("invisible-unicode", "high", i,
                f"{len(chars)} invisible char(s) [{','.join(kinds)}] at col "
                f"{matches[0].start() + 1}", line)

    # 2) override / 3) deception / 4) exfil — line based, precompiled.
    # Lines above MAX_LINE_BYTES are machine-generated data (minified JSON,
    # bundled JS), not authored skill prose — skip them.
    for i, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_BYTES:
            continue
        low = line.lower()
        for rx, tag in OVERRIDE_COMPILED:
            if rx.search(low):
                add("instruction-override", "high", i, tag, line)
        for rx, tag in DECEPTION_COMPILED:
            if rx.search(low) and not ANTI_FABRICATION_RE.search(low):
                add("deception", "high", i, tag, line)
        for rx, tag in EXFIL_COMPILED:
            if rx.search(low):
                sev = "high" if tag in {
                    "curl-pipe-shell", "wget-pipe-shell",
                    "powershell-download-exec", "base64-pipe-shell",
                    "echo-b64-decode", "credential-path-egress",
                    "curl-pipe-python-stdin", "eval-base64"} else "medium"
                # A skill documenting an official installer one-liner, or a
                # writeup quoting the blocked pattern, is not performing it.
                # Keep it visible but stop crying wolf (see _is_documenting).
                if sev == "high" and _is_documenting(low):
                    sev = "medium"
                add("egress-or-exec", sev, i, tag, line)

    # 5) long base64 blobs that decode to shell-ish text
    for m in re.finditer(r"[A-Za-z0-9+/]{200,}={0,2}", text):
        blob = m.group(0)
        try:
            decoded = base64.b64decode(blob + "=" * (-len(blob) % 4),
                                       validate=False)
            dec = decoded.decode("utf-8", "ignore")
        except Exception:
            continue
        if not dec:
            continue
        shellish = sum(dec.count(k) for k in
                       ("curl ", "bash", "sh -", "exec", "import os",
                        "subprocess", "eval(", "DownloadString", "/bin/"))
        if shellish >= 3:
            add("encoded-payload", "high", _line_of(text, m.start()),
                f"{len(blob)}-char base64 decodes to {shellish} shell/exec tokens "
                f"(preview: {dec[:60]!r})")

    # 6) frontmatter capability grant not referenced in the body
    #    restricted to privileged capabilities (see PRIVILEGED_TOOL_RE)
    fm = FRONTMATTER_RE.match(text)
    if fm:
        body = text[fm.end():].lower()
        for m in TOOLS_KEY_RE.finditer(fm.group(1)):
            raw = m.group(1).strip()
            if raw in {"", "[]", "{}", "null", "~"}:
                continue
            names = re.findall(r"[A-Za-z0-9_\-]{3,}", raw)
            for name in names:
                if name.lower() in {"true", "false", "none", "all", "read",
                                    "write", "allow", "deny"}:
                    continue
                if not PRIVILEGED_TOOL_RE.match(name):
                    continue          # ordinary metadata, not a smuggled grant
                if name.lower() not in body:
                    fm_line = _line_of(text, fm.start(1) + m.start())
                    add("unreferenced-grant", "medium", fm_line,
                        f"frontmatter grants privileged capability '{name}' "
                        f"but the body never mentions it", m.group(0))
    return findings


def scan_tree(root: Path, severity_min: str = "low") -> dict:
    findings: list[dict] = []
    scanned = 0
    skipped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {"__pycache__", ".git", "node_modules"}]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in TEXT_SUFFIXES:
                skipped += 1
                continue
            try:
                raw = p.read_bytes()
            except OSError:
                skipped += 1
                continue
            if b"\x00" in raw[:4096]:
                skipped += 1
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", "replace")
            scanned += 1
            rel = str(p.relative_to(root)).replace("\\", "/")
            findings.extend(scan_text(text, p, rel))

    floor = SEVERITY_ORDER[severity_min]
    findings = [f for f in findings
                if SEVERITY_ORDER.get(f["severity"], 0) >= floor]
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    by_detector: dict[str, int] = {}
    for f in findings:
        by_detector[f["detector"]] = by_detector.get(f["detector"], 0) + 1
    return {
        "root": str(root),
        "files_scanned": scanned,
        "files_skipped": skipped,
        "findings": findings,
        "counts": counts,
        "by_detector": by_detector,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Skill safety scanner")
    ap.add_argument("--root", default=str(DEFAULT_HOME / "skills"))
    ap.add_argument("--severity", default="low",
                    choices=list(SEVERITY_ORDER))
    ap.add_argument("--fail-level", default="high",
                    choices=["low", "medium", "high", "none"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--max-print", type=int, default=40)
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"ABORT: root is not a directory: {root}", file=sys.stderr)
        return 2

    res = scan_tree(root, args.severity)
    res["sev_level"] = args.severity
    res["fail_level"] = args.fail_level

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.quiet:
        c = res["counts"]
        print(f"[skill-safety] {res['files_scanned']} files | "
              f"high={c['high']} medium={c['medium']} low={c['low']}")
    else:
        c = res["counts"]
        print(f"Skill Safety Scan — {root}")
        print(f"scanned {res['files_scanned']} files "
              f"(skipped {res['files_skipped']}) | "
              f"high={c['high']} medium={c['medium']} low={c['low']}")
        if res["by_detector"]:
            print("detectors: " + ", ".join(
                f"{k}={v}" for k, v in sorted(res["by_detector"].items())))
        print()
        for f in res["findings"][:args.max_print]:
            print(f"  [{f['severity'].upper():6}] {f['file']}:{f['line']} "
                  f"{f['detector']} — {f['detail']}")
            if f["snippet"]:
                print(f"           > {f['snippet']}")
        extra = len(res["findings"]) - args.max_print
        if extra > 0:
            print(f"  … {extra} more finding(s); use --json for the full list")

    if args.fail_level == "none":
        return 0
    return 1 if res["counts"].get(args.fail_level, 0) else 0


if __name__ == "__main__":
    sys.exit(main())
