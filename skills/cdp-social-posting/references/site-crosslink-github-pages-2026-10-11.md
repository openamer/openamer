# Cross-linking own published posts from the GitHub **Pages** surfaces (11.10.2026)

Session: visibility cron, 2026-10-11 14:01Z. Every platform was gated (see below), the README
cross-link was already current, so the run's honest deliverable was extending the cross-link to the
two **owned HTTP surfaces** that still had zero links to the project's own writing.

## Why this run had no post (the gating facts, measured in-run)

| Channel | Verdict this run | Evidence |
|---|---|---|
| (a) Dev.to | SKIP mass-post | session LIVE (`devto_inventory.py` → `me_status=200 openamer/4173871`), **7** published, 2 of them on 2026-10-11 (02:13Z `4830939`, 05:42Z `4831400`); a 3rd same-calendar-day post is the forbidden pattern (same standard as 10.10 14:12Z and 11.10 06:05Z) |
| (b) Medium / Hashnode | SKIP no credential | `MEDIUM_INTEGRATION_TOKEN` / `HASHNODE_API_KEY` absent from `.env`; no session on `:9222` |
| (c) Reddit | SKIP same-day siblings | `Realistic_Kitchen_65` logged_in, but the reddit-outreach cron had **already posted 10 comments today** (`outreach_reddit_1011*_proofs.jsonl`: 4 + 1 + 3 + 2, latest 14:08Z `t1_pf87crr`); `/api/submit` remains a BAD_CAPTCHA post-class gate |
| (d) HN Show HN | SKIP dead account | probe: `logged_in=true`, `flagged_count=3`, `threads_flagged_markers=10`; **all 5 newest Show HN items return the anonymous stub with 0 `titleline`**; algolia indexes only the 06.09 item `49584315`. Note `49934162` is already titled exactly *"Show HN: OpenAmer – a self-verifying AI agent that runs on your laptop"* = the proposed title is already submitted and dead |
| (e) LinkedIn / Quora / Telegram / IH / PH / X | SKIP no session | `:9222` target list held only bing + namecheap tabs; `TELEGRAM_BOT_TOKEN` commented out in `.env` |

## The two owned surfaces and the exact edits

Repo `openamer/openamer`, Pages config: `gh api repos/openamer/openamer/pages` →
`{branch:"main", path:"/docs", cname:"openamer.com", status:"built"}`.

- `docs/index.html` → live at `https://openamer.com/` (identical to `openamer.github.io/openamer/`).
  Before: 14855 B, `dev.to/openamer` count **0**. Inserted a `## Writing / How OpenAmer measures itself`
  section (classes `kicker`, `sec`, `strip`, `social`, `chip` — all already in the page's CSS) between
  the `#ecosystem` and `#support` sections, 7 chips, one per published post.
  Commit `0ed2acd0cc962db76fe073beadfd7f9f95dbd8c7`.
- `docs/landing.html` → live at `https://openamer.com/landing.html`.
  Before: 4594 B, count **0**. Extended the `<footer>` with a one-line `Writing — …` strip (` · `-joined
  links) — 7 links. Commit `3b64dac9d01c3a84ccabf76fd0d052e922102daf`.

## Recipe (reusable, no clone, sha-guarded)

```python
import base64, json, subprocess
REPO, PATH = "openamer/openamer", "docs/index.html"

def gh(args, data=None):
    cmd = ["gh", "api"] + args
    p = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True) if data \
        else subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[:400]
    return p.stdout

cur  = json.loads(gh([f"repos/{REPO}/contents/{PATH}"]))
sha  = cur["sha"]
html = base64.b64decode(cur["content"]).decode("utf-8")     # authoritative bytes (NOT MSYS `base64 -d`)
assert html.count("\r\n") == 0                              # LF repo file — a CRLF flip rewrites everything

# 1. nothing to do if any article URL is already linked
assert not [u for u in URLS if u in html], "already linked"

# 2. unique anchor
ANCHOR = '</div></section>\n\n<section id="support">'      # landing.html: '</footer>'
assert html.count(ANCHOR) == 1

new = html.replace(ANCHOR, SECTION + ANCHOR)               # or block + '</footer>'
assert new != html and new.count("dev.to/openamer") == 7

gh(["-X", "PUT", f"repos/{REPO}/contents/{PATH}", "--input", "-"],
   data={"message": "…", "content": base64.b64encode(new.encode()).decode(),
         "sha": sha, "branch": "main"})
```

## Verification ladder actually used (all in-run)

1. `GET contents/docs/<f>?ref=main` → python-decode → `16396 B`, `dev.to_links=7`, `id="writing"` present
   (index) / `5748`-byte live file with the `Writing —` label (landing).
2. `gh api repos/openamer/openamer/pages/builds/latest --jq '.status,.commit'` → poll until
   `built` **and** `commit` == your own sha (the first poll after a PUT reads `building`; a build for a
   sibling commit would be a false pass).
3. Anonymous proof (browser UA, **no cookies**, `curl -L`):
   – `https://openamer.com/` → `HTTP 200`, 16520 B, 7 dev.to links, `id="writing"` present
   – `https://openamer.com/landing.html` → `HTTP 200`, 5748 B (was 4630), 7 links, `Writing —` present
   – each of the 7 article URLs → `200` with a matching `<title>`
4. `gh api repos/openamer/openamer` → `pushed_at` == your commit time.
5. Final `devto_inventory.py` re-read at run end → still `count=7`, newest unchanged ⇒ the cross-link
   did not go stale during the run.

## Cost / gotcha notes

- One compound `terminal` call containing `grep -oE 'href="[^"]*github[^"]*"'` was refused as
  *"BLOCKED (hardline): command parser limit or malformed executable payload"*; splitting it into
  fetch-to-file + single `grep` worked. Keep outreach shell one-liners simple.
- MSYS `base64 -d` of `gh api --jq .content` gave a byte count 122 higher than the python decode of the
  same response (one CR per line). Quote byte counts from python only.
- Both probes were throwaway files in the OPENAMER_HOME root; they were deleted at the end and the
  post-run guard then re-fired on the deleted paths. Correct bounded answer (see SKILL.md): absence line
  via `test -f`, state that `pytest.ini` → `testpaths = scripts/tests` and the home is not a git repo,
  run the canonical suite **once** (`./venv/Scripts/python.exe -m pytest -p no:xdist -q` → `PYTEST_RC=0`),
  and keep the evidence (commit hashes + byte counts + HTTP codes) in `visibility_log.jsonl` — never in a
  file you delete.
