# Reddit launch posts — OpenAmer

Two separate posts, tailored to each subreddit's tone and rules. Do **not** post
the same text to both. Both open with the agreed wedge sentence, used verbatim.

---

## r/LocalLLaMA

Tone: technical, skeptical of hype, cares about local models / hardware / cost
and about "can I run this on my own box". Lead with the mechanism and the local
run economics, not the marketing. No link-dump; the community penalises drive-by
promotion, so the body must stand on its own and invite technical discussion.

**Title**

```
An agent that drives my Windows desktop in the background — runs on CPU, <1 kWh/day, 0 EUR
```

**Body**

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

I wanted an agent that could work the apps on my machine that have no API — an
old ERP client, a desktop tool that never grew a scripting interface. The part
that made it click for me: it drives the app while I keep typing in another
window. The real cursor never moves; the agent has its own tinted overlay
cursor, so you can watch it act without it fighting you for the mouse.

Two things this community usually asks:

**Does it run locally?** Yes, and cheaply. Tool orchestration can run on a local
2B-class model, with a free-cloud reasoning chain for deeper work. On CPU it
bills out at <1 kWh/day, i.e. 0 EUR/day — it's built to be left on 24/7 on a
laptop, not rented. Local state, local memory, local credentials.

**How is the desktop control implemented?** Through cua-driver
(`tools/computer_use/cua_backend.py`). Background input delivery is the default
— actions are routed to the target window without raising it or stealing focus.
The driver returns a per-action effect status (confirmed / unverifiable /
suspected no-op) and the agent re-reads the screen and escalates only on a real
signal.

**Safety, because unattended clicking deserves it.** There's a native Windows
sandbox built on a kernel job object (`agent/win_sandbox.py`), admin-free:
process-tree kill on close, a hard cap on concurrent processes (fork-bomb
block), memory ceilings, no clipboard or cross-process handles, no breakaway.
It's opt-in and off by default. Honest limits: network egress is *not*
OS-isolated on native Windows without admin, and the filesystem boundary is
policy-level, not ACL-level.

It also self-improves — it builds skills from sessions and evolves the skill
population with mutation/crossover/fitness selection. [VERIFY: number of skills
in the current population] skills in the population right now.

Early project. Verified placement as of 2026-09-14: OpenRouter cli-agent
#38/50, ide-extension #7/9. Happy to go deep on the cua-driver input routing or
the job-object containment if anyone wants.

---

## r/selfhosted

Tone: cares about self-hosting, running on your own hardware, no phone-home, no
hosted tier, deployment and resource footprint. **Read the sub rules first**;
r/selfhosted requires a descriptive title, dislikes pure self-promotion, and
wants the "what do I run and where does my data live" answered up front.

**Title**

```
OpenAmer: a self-hosted agent that drives your Windows desktop in the background (no cloud tier, no phone-home)
```

**Body**

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

Everything runs on your hardware. No hosted tier, no phone-home, no VM
required. State, memory, skills, and credentials stay on your machine —
Windows-native, no WSL needed.

**What you actually run:** the agent core (CLI, messaging gateway, TUI, or the
Electron desktop app). Tool orchestration can run on a local model; on CPU it
draws under 1 kWh/day, so it's happy on a box you already leave on. It can be
left running as a background service on a stock Windows laptop — no
administrator rights required for the sandbox it uses.

**The interesting self-hosted bit:** it can drive desktop apps that have no API
by working them in the background — clicking and typing in a window while you
keep using your machine. Your real cursor never moves. It does this via
cua-driver, with background input delivery as the default path.

**Isolation, honestly scoped.** A native Windows sandbox on a kernel job object
(`agent/win_sandbox.py`) gives you process-tree teardown on close, a concurrent-
process cap, memory ceilings, and a no-clipboard/no-breakaway boundary — all
without admin. Opt-in, default off. It does *not* OS-isolate network egress on
native Windows (that needs admin), and the write boundary is enforced by our
tools, not by an ACL. I'd rather scope that correctly than claim a stronger
boundary than ships.

It's early. Verified placement 2026-09-14: OpenRouter cli-agent #38/50,
ide-extension #7/9. Questions about the deployment model welcome.

Repo: https://github.com/openamer/openamer