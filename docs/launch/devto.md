# How I made an agent click your desktop without stealing focus

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

That sentence is the whole product. This post is about how it is actually
implemented: the background-input mechanism behind cua-driver, and the kernel
job-object sandbox that makes letting an agent click buttons unattended
responsible rather than reckless.

## The problem: automation stops at "this app has no API"

Every agent I tried stopped at one of two places: the browser, or the terminal.
But the software that hurts most to automate is neither. It's the ERP client, the
old internal tool, the desktop app that never grew a scripting interface. You
open it, you hit the wall *"this thing has no API"*, and you move on.

The obvious fix — screen-scrape and replay mouse and keyboard events — is what
everyone tries and everyone abandons, because it takes over your machine. The
agent grabs the cursor, steals focus, and you can't do anything else while it
runs. That is not automation; that's a hostile takeover of your desktop.

So the design constraint was single and non-negotiable: **the agent has to act
in the background, and the real OS cursor must never move.**

## Mechanism 1: background input via cua-driver

The agent drives the host through cua-driver (`tools/computer_use/cua_backend.py`).
The important design decision is that **background delivery is the default path**,
not a fallback. Actions are routed to the target window *without raising it and
without stealing keyboard or mouse focus*. You keep typing in your editor; the
agent clicks a button in the app behind it.

Two details make this work rather than merely sound good:

**A separate visual cursor.** The agent session owns a tinted overlay cursor that
glides to wherever it acts. It is UI feedback *for you* — a cue showing where the
agent is working. The **real** OS cursor is never moved or warped. This is the
concrete meaning of "without taking your mouse": the pointer under your hand
stays yours.

**Honest effect reporting, so the agent never blind-retries.** Background input
can fail silently — some toolkits (raw-input canvases, DirectInput games, heavily
custom controls) don't accept synthetic events addressed purely by element. So
each action returns a structured effect status:

- `confirmed` + `verified: true` — the driver read the result back. Done.
- `unverifiable` — input was delivered but the driver can't confirm it. The agent
  re-captures the screen and checks *itself* before deciding.
- `suspected_noop` / `background_unavailable` — the action did not land. The
  driver returns an escalation recommendation; the agent re-addresses by pixel
  coordinate, or escalates to foreground delivery as a *reaction to a real
  signal*, never as a prediction.

The rule that keeps this from becoming guesswork: **do not silently retry the
same rung expecting a different result, and do not conclude "this app can't be
driven" — climb the ladder.** Background first, then pixel coordinate, then
foreground. That's the entire reliability story, and it's deterministic.

## Mechanism 2: an admin-free Windows sandbox (kernel job object)

If you're going to let an agent click things while you're not watching, "it's
fine" is not a boundary. OpenAmer ships a native Windows containment layer
(`agent/win_sandbox.py`) built on a **Windows Job Object** — and the whole point
is that it needs **no administrator rights**, so it works on a stock Windows
laptop.

What the OS itself enforces:

| Guarantee | Mechanism |
|---|---|
| Whole process tree dies when the sandbox closes — no orphaned daemons | `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` |
| Hard cap on concurrent processes — blocks fork bombs | `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` |
| Per-process and per-job memory ceilings | `JOB_OBJECT_LIMIT_PROCESS_MEMORY`, `JOB_OBJECT_LIMIT_JOB_MEMORY` |
| No clipboard access, no handles into other processes, no global/system-parameter/desktop changes | `JOB_OBJECT_UILIMIT_*` |
| Children cannot escape the job | breakaway is deliberately never set |

A couple of these are the whole reason I chose the job object over "just wrap it
in a container." Containers need a runtime and often elevation; a job object is a
kernel primitive available to an ordinary user, and it kills the entire tree at
once — which is exactly what you want when the thing being contained is an agent
that spawned a browser, which spawned a node process, which is still holding a
lock.

## Being honest about the edges

A security boundary is only useful if its edge is stated plainly. The module's
`describe_enforcement()` exists so no status surface can advertise more than the
platform delivers. Two things are **not** enforced:

- **Network egress is not OS-isolated on native Windows.** Per-process egress
  blocking needs Windows Filtering Platform rules, which need admin. So the
  honest report is `partial`, never `enforced`.
- **The filesystem boundary is policy, not an ACL.** It constrains the paths our
  own tools write and resolves junctions/symlinks first, but a command calling
  raw Win32 file APIs isn't intercepted.

The sandbox is **opt-in and off by default**; with it disabled, the spawn path is
byte-identical to before. Default off is a deliberate choice — a containment layer
that surprises you is worse than one you switch on knowingly.

## What this adds up to

The wedge is one sentence, but it's backed by two mechanisms: background input
routing (so the agent never takes your mouse) and a real, admin-free OS boundary
(so you can trust it while it works). The rest of the stack — self-improving
skills, a workflow immune system, running on CPU at <1 kWh/day for 0 EUR — is
depth underneath that, not a second pitch.

If you're automating a Windows app that has no API, that's the exact wall this was
built for.

Repo: https://github.com/openamer/openamer

---

*Verified claims: cua-driver integration (`tools/computer_use/cua_backend.py`),
Windows job-object sandbox (`agent/win_sandbox.py`, `docs/security/windows-sandbox.md`).
Traction as of 2026-09-14: OpenRouter cli-agent #38/50, ide-extension #7/9.*