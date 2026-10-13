# Competitive Intelligence — OpenRouter "CLI Agents" category

**Date:** 2026-09-13
**Question answered:** what do our competitors do better than us, one by one — and
what exactly is missing for OpenAmer to reach #1.

**Method / evidence rules.** Every number below was read live from the source in
this session; each claim carries its URL. Nothing is copied from memory or from a
search-engine summary. Where something could not be verified, it says so.

---

## 1. The scoreboard we are actually measured on

Source: <https://openrouter.ai/apps/category/coding/cli-agent> (read 2026-09-13).
OpenRouter sorts by **total tokens attributed to the app** — a usage proxy, not a
quality score.

| # | App | Tokens | # | App | Tokens |
|---|---|---|---|---|---|
| 1 | **Hermes Agent** (our upstream) | 1.47T | 16 | Qwen Code | 7.20B |
| 2 | Kilo Code | 493B | 17 | goose | 4.57B |
| 3 | Claude Code | 482B | 18 | AgentField AI | 4.51B |
| 4 | Cline | 403B | 19 | Trenzel | 3.75B |
| 5 | pi | 242B | 20 | mimocode | 3.59B |
| 6 | omp | 172B | 21 | Favur | 3.33B |
| 7 | OpenClaw | 156B | 22 | Crush | 2.65B |
| 8 | Codex | 92.4B | 29 | Aider | 843M |
| 9 | OpenHands | 45B | 41 | Junie (JetBrains) | 382M |
| 10 | Cursor | 29.3B | 47 | pipm (Pro-Memory fork of pi) | 256M |
| 11 | CodeGPT | 28.2B | 50 | Nemo | 217M |
| 12 | Strix | 12.9B | | **OpenAmer Agent** | **absent** |
| 14 | Letta | 8.09B | | | |

### 1.1 The finding that mattered most — and a correction

Our own app page
(<https://openrouter.ai/apps?url=https://github.com/openamer/openamer>) reports
**7.73B total tokens, active since 2026-08-16, 13 models used**, app id `4725109`
— that would place us around **#16**, ahead of Qwen Code (7.20B) and every app
below it. We appear in **none** of the four category listings:

```
cli-agent:absent    (50 listed, leader Hermes Agent)
ide-extension:absent (9 listed, leader Kilo Code)
cloud-agent:absent  (26 listed, leader CodeGPT)
personal-agent:absent (41 listed, leader Hermes Agent)
```

**Correction — the first diagnosis was wrong and is retracted.** The initial
reading was: "our `X-OpenRouter-Categories` header carried the group names
`coding`/`productivity`, so OpenRouter silently dropped them and we were invisible."
Three checks refute that:

1. **Crush is ranked #22 with `"categories":[]`.** Fetching
   `openrouter.ai/apps?url=https://github.com/charmbracelet/crush` returns
   `"categories":[], "totalTokens":2277349119` — an app in the leaderboard with
   *zero* categories. Categories are therefore **not** required for listing.
2. `cli-agent` was already present before the change (`agent/auxiliary_client.py`
   sent `productivity,cli-agent`, half of which is valid).
3. After the change the category set is recorded as `["cli-agent","ide-extension"]`
   — and we are **still absent**. So the header was not the gate.

**What the evidence actually shows.** The leaderboard links every row to a
*registered app page* (`openrouter.ai/apps/<slug>`). Those pages carry a
description and two categories:

| | slug page | description | categories |
|---|---|---|---|
| Hermes Agent | `/apps/hermes-agent` | present | `["personal-agent","cli-agent"]` |
| Cline | `/apps/cline` | present | `["ide-extension","cli-agent"]` |
| **OpenAmer** | **none** (`"slug":null`) | **`null`** | `["cli-agent","ide-extension"]` |

Our record is a bare *origin* record: `slug: null`, `description: null`,
`main_url: null`, `favicon_url: null`, `source_code_url: null`. The
`?url=` view is the unranked per-origin attribution view; the leaderboard is keyed
by registered apps. **The likely gate is a registered/claimed app profile for
OpenAmer — not token volume, not the category header.**

Superseded claim in the table below: the category correction is still kept (valid
names beat invalid ones), but it is **not** the cause of the invisibility, and
`rank: null` on a `?url=` page is *normal* (Crush shows `rank: null` too), so it is
not a signal of exclusion either.

**Concrete next action (needs the OpenRouter account, i.e. a human):** register or
claim the OpenAmer app — OpenRouter's docs note apps can be created via an OAuth
authorization, and that changing an existing app requires contacting support
(<https://openrouter.ai/docs/app-attribution>). Until that exists, 7.73B tokens of
real usage sit on an identifier that is not on any leaderboard.

**Open question, stated as open:** the exact leaderboard-inclusion rule could not
be reproduced from the outside. Two candidate rules remain — "app must be
registered with a slug" and "app must be created/verified through OpenRouter's app
flow". The daily watchdog (§4) will settle it empirically.

---

## 2. Competitor-by-competitor

Sources read live in this session: repo READMEs via `raw.githubusercontent.com`,
vendor docs via curl/markdown endpoints, the official SWE-bench board via browser.

### Hermes Agent — Nous Research (1.47T, our upstream)
**Their superpower is distribution, not engineering.** Their README advertises a
closed learning loop (agent-curated memory, autonomous skill creation, FTS5 +
LLM-summarised session search) — *which we inherited* — but the real moat is:
one-line installers for Linux/macOS/WSL2/Termux **plus native PowerShell/Windows
that bundles MinGit into `%LOCALAPPDATA%\hermes`** (nothing can block the install),
and `hermes setup --portal`, which bundles 300+ models + tool gateway (web search,
images, TTS, cloud browser) under **one OAuth subscription — no API-key collection
at all**. Seven terminal backends (local, docker, ssh, singularity, modal, daytona,
vercel_sandbox) with persistent-container semantics. Dangerous-command approval
with severity/alternatives and **default = deny**; headless surfaces deny instantly
instead of blocking. `/retry`, `/undo`. No plan mode, no benchmark claim.
<https://raw.githubusercontent.com/NousResearch/hermes-agent/main/README.md>

**What we lack vs them:** the bundled-subscription onboarding (removes the single
biggest drop-off step) and the "nothing can block install" Windows story.

### Kilo Code (493B, #2)
Same agent across VS Code + JetBrains + CLI + Cloud, "500+ models at provider rate,
zero markup", acquired by Anaconda. Ships a **deeplink install button in the README**
(`vscode:extension/...`) — zero-friction install straight from the docs page.
Verified live that they inject attribution headers in their provider transport:
`provider.request.headers["HTTP-Referer"] = "https://kilo.ai/"`,
`X-Title = "Kilo Code"` (kilocode `core/plugin/openrouter.ts`).
<https://kilocode.ai>

**What we lack:** the deeplink install button; "meets you everywhere" framing.

### Claude Code (482B, #3)
Deepest security model in the category: **OS-enforced sandbox** (macOS Seatbelt;
Linux/WSL2 bubblewrap+socat+optional seccomp), filesystem isolation, protected
paths, **network isolation by domain allowlist**, unix-socket blocking,
**credential masking incl. AWS request re-signing**, and `sandbox.failIfUnavailable`
as a hard managed-fleet gate. Permission modes default/acceptEdits/plan/
bypassPermissions + enterprise managed policy. **Enforced plan mode** ("auto-allow
does not widen approvals in plan mode"). Automatic checkpoint before each turn with
`/rewind` + rewind-and-summarise; documented limits (bash changes not tracked,
subagent edits not restored). Subagents with own context/tools/permissions/model
routing, nested, background, coordinated **agent teams**. 77.2% SWE-bench Verified
(Sonnet 4.5, 10 trials, no test-time compute).
**Native Windows is explicitly NOT supported — "run Claude Code inside a WSL2
distribution."**
<https://docs.claude.com/en/docs/claude-code/sandboxing> · `/checkpointing` · `/sub-agents`

**What we lack:** OS-enforced local sandbox w/ network allowlist + credential
masking; enforced (not prompt-level) plan mode; published benchmark number.
**Our opening:** the sandbox does not exist on native Windows for anyone.

### Codex CLI (92.4B, #8)
OS-enforced sandbox **by default, network off by default**, with a clean split
between what the sandbox allows and when it must ask. Modes read-only /
workspace-write / danger-full-access; **protected paths inside writable roots
(`.git`, `.codex`)**; named permission profiles; `network_proxy` with per-domain
allow/deny; **a Windows sandbox mode with a `sandbox = "unelevated"` fallback**;
managed `requirements.toml` can forbid `approval_policy = "never"`. No plan
artifact — "switch to read-only mode with `/permissions`". `codex resume` / `codex exec`.
<https://developers.openai.com/codex/sandbox.md>

**What we lack:** protected paths + writable-root concept; a Windows sandbox mode.

### Cline (403B, #4)
Plan/Act toggle with **approval required for every edit and terminal command** by
default, live linter/compiler error fixing, **checkpoints on every change**, agent
teams with persistent team state (`cline --team-name`), scheduled agents
(`cline schedule create --cron`), messaging channels where each thread is a session,
headless `--json` for CI, plugin SDK with lifecycle hooks. Most surfaces of any open
agent (VS Code + JetBrains + CLI + Desktop + SDK). No sandbox, no benchmark claim.
<https://raw.githubusercontent.com/cline/cline/main/README.md>

**What we lack:** Plan/Act as a *mode*; live compiler-error fixing in the loop.

### omp (172B, #6) — our closest direct competitor
**"Windows-native, skip the WSL"** — exactly our niche — with a Rust core and an
unusually large documented first-class surface: session tree, memory, compaction,
**plan mode**, **goal mode**, handoff, code intelligence, structural edits,
debugging, code review, **security scans**, subagents, **advisor models**,
computer control, hooks, marketplaces, SDK/RPC/ACP, a dedicated **tool approvals**
reference page. 25+ providers.
<https://omp.sh/docs>

**What we lack:** plan mode + goal mode as modes; structural edits (LSP-backed
rename/codemod); security scans and code review as first-class surfaces;
marketplaces. **This is the competitor to watch — it is marketing the same
differentiators we claim.**

### pi (242B, #5)
Ships *primitives* and documents what it refuses to build: "No MCP, no sub-agents,
no permission popups, no plan mode, no built-in to-dos, no background bash" — all
delegated to extensions, packages, or "ask Pi to build it for you".
**Tree-structured session history** (`/tree` to branch anywhere, all branches in one
file, filter, label), `/export` to HTML, `/share` to a rendered GitHub gist,
pluggable compaction strategies, minimal token-efficient system prompt, packages via
`pi install npm:...` / `git:...`. MIT.
<https://pi.dev>

**What we lack:** session tree navigation + HTML/gist export/share; pluggable
compaction.

### OpenClaw (156B, #7) · Letta (8.09B, #14) · OpenHands (45B, #9)
- **OpenClaw** — messaging-first agent that acts inside your chat apps (50B+ style
  reach into non-developer use cases). We have gateway parity (~20 platforms) but
  not their positioning.
- **Letta** — the MemGPT lineage, **memory is the product**: memory blocks editable
  by the agent, attachable/detachable, **shareable between agents**, in-context and
  out-of-context messages, server-side tools executed in a sandbox. We have a
  richer self-learning stack but no user-facing memory-editing UI of that clarity.
- **OpenHands** — Docker-sandboxed, self-hostable, and the **only open agent with a
  published harness on the official SWE-bench Verified board**: 71.80% (GPT-5),
  70.40% (Claude 4 Sonnet), 69.60% (Qwen3-Coder-480B-A35B). Agent Canvas drives
  Claude Code / Codex / Gemini via ACP. <https://www.swebench.com/>

### Aider (843M, #29) · Qwen Code (7.20B, #16) · Crush (2.65B, #22)
- **Aider** — surgical edits against a **tree-sitter repo map**, git as the undo
  system, and the signature behaviour: **"automatically lint and test your code
  every time aider makes changes"** and fix what they find.
- **Qwen Code** — publishes an explicit **Claude-Code parity table** (SubAgents,
  Agent Teams, Auto-Memory, Auto-Skills, Hooks, MCP, **Plan Mode**, LSP
  Integration, Auto Mode, Sandbox, Git Worktrees, Computer Use, IDE plugins).
- **Crush** — a **shared live workspace**: several clients share one session list,
  message history, permission queue, LSP and MCP state; LSP-enhanced context; MCP
  with OAuth.

### Honest note on "why does Hermes have ~3400× our usage?"
Not a feature-count problem. Feature-for-feature we are not behind the open
category — we have checkpoints, `/plan`, goals, handoffs, approval modes with risk
assessment, container backends, LSP, worktrees, subagents, MCP, 99 tools, 711
skills. What we are behind on is: **(a) onboarding that cannot fail on Windows and
collects no API keys, (b) an externally verifiable number, (c) visibility — which
today meant literally not being listed in the category we compete in.**

---

## 3. Gap matrix (verified against our own tree)

Already ours, so *not* gaps: checkpoint manager + `/undo`/`/retry`/`/rollback`
(opt-in), `/compress`, `/plan` (skill), `/goal`, `/handoff`, `/branch`, `/moa`,
approval modes smart/manual/off with auxiliary-LLM risk assessment, `cron_mode:
deny|approve`, container backends (Docker/Singularity/Modal/Daytona/SSH/vercel),
MCP credential filtering, context-file prompt-injection scanning, egress controls,
LSP diagnostics, git worktrees, `lint_fix`, subagents, 99 tools / 711 skills, A2A
swarm, background computer-use.

| # | Feature (who has it) | Our status | Gap | Prio |
|---|---|---|---|---|
| 1 | OS-enforced local sandbox: FS + network allowlist + credential masking (Claude, Codex) | container backends only, opt-in; default local terminal has no OS boundary | **YES** | **High** |
| 2 | Enforced plan mode = read-only tool gating + approve-to-act (Claude, omp, Cline, Codex, Qwen) | `/plan` is a *skill*; the model keeps write tools while planning | **YES** | **High** |
| 3 | Protected paths / writable-root boundaries (Codex) | denylist patterns yes, per-run writable roots no | **YES** | **High** |
| 4 | Published benchmark on the official board (OpenHands, Claude, Codex) | none | **YES** | **High** |
| 5 | Structural code intelligence: LSP rename/codemod (omp, Crush, Qwen) | diagnostics only | **YES** | Med |
| 6 | Test-gated completion — tests must pass before "done" (Aider, Cline, omp) | `lint_fix` + cron autotest, no in-loop gate | **YES** | Med |
| 7 | Session tree + HTML/gist export & share (pi, omp, Claude) | `/branch`/`/handoff`/`/sessions`, no export/share | **YES** | Med |
| 8 | Code review + security scan as first-class surfaces (omp, OpenHands, Cline) | `code_review_bot.py` exists as a CLI, not productised | partial | Med |
| 9 | Advisor / second-opinion model roles (Claude, omp) | `/moa` covers most of it | low | Low |
| 10 | Extension marketplace / packages (omp, pi, Cline SDK) | plugins + skills + Skills Hub, no npm/git install | partial | Low |
| 11 | Pluggable compaction strategies (pi) | one compressor | partial | Low |
| 12 | Multi-client shared live workspace (Crush) | gateway continuity, not a shared live workspace | partial | Low |
| 13 | One-command session resume / CI headless | exists; ergonomics worth auditing | low | Low |

---

## 4. What was shipped as a result of this analysis (2026-09-13)

| Commit | What | Why it matters |
|---|---|---|
| `15b82a0ed` | Send only **recognised** OpenRouter categories (`cli-agent,ide-extension,personal-agent,cloud-agent`); contract test asserting every advertised category is recognised, lowercase-hyphenated, ≤30 chars, and that both call paths agree | Still correct to do — invalid values are silently dropped, and the recorded set is now `["cli-agent","ide-extension"]`. **But it did not make us visible (see §1.1 correction) — announced too early as a fix.** |
| `e4a3fdf56` | `scripts/openrouter_rank_watch.py` — outside-in listing watchdog (JSON-LD ItemList, curl) + daily `no_agent` cron; silent unless the listing changes | the internal view cannot see this class of failure |
| `c9bd6d713` | One-line install moved into the README hero (EN + DE), installers verified live first | distribution is the measured gap, not features |

**Top 5 remaining, ranked** (from §3): (1) native-Windows OS-level sandbox with
network allowlist + credential masking — nobody has this on Windows; (2) enforced
plan mode; (3) a verified SWE-bench Verified entry + reproducible eval runner — the
slot "open, Windows-native, self-hosted agent with a published score" is empty;
(4) structural code intelligence + test-gated completion; (5) review/security-scan
surfaces + session export/share, then packages/marketplace.

**Named gap in ourselves:** there is still no enforced outbound **spend** ceiling.
Cost is tracked (`agent/agent_init.py`, `conversation_loop.py`, `turn_finalizer.py`)
and filterable in session listings (`max_cost` in `session_filters.py`), and there
is a cross-session *rate* guard for the Portal (`agent/openamer_rate_guard.py`) —
but a per-session "stop at $X" budget that actually blocks execution does not exist.
