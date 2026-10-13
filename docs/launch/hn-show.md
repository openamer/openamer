# Show HN — OpenAmer

Launch copy for Hacker News. Style rules for HN: no marketing adjectives, no
"revolutionary", no emoji, no bold-everything. State what it does, how it works,
and what is honest about its limits. The opening line is the agreed wedge and is
used verbatim.

## Title (<= 80 chars)

```
Show HN: OpenAmer – drives your Windows desktop without taking your mouse
```

(74 chars. Alternative if preferred: `Show HN: OpenAmer – a Windows agent that works in the background`.)

## URL

```
https://github.com/openamer/openamer
```

## First comment (body)

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

Hi HN. OpenAmer is an open-source agent that controls the desktop you already
have open: it clicks, types, and scrolls inside a native Windows app while you
keep working in another window. Your real cursor never moves — the agent gets a
tinted overlay cursor of its own, so you can see where it is acting.

**Why this is the one thing I'm pitching.** The motivation is narrow: a Windows
machine full of tools that have no API. An ERP client, an old internal tool, a
desktop app that never grew a scripting interface. You tried to automate it, hit
"this thing has no API", and moved on. That wall is the target.

**How the background input works.** The agent drives the host through
cua-driver (`tools/computer_use/cua_backend.py`). Input is routed to the target
window without raising it or stealing focus: background delivery is the default
path, and the driver reports per-action whether the effect was confirmed,
unverifiable, or a suspected no-op — the agent re-reads the screen and escalates
(addressing by pixel coordinate, or foreground delivery) only when it gets that
signal. It does not silently retry the same rung. The overlay cursor you see on
screen is UI feedback for you — the real OS cursor is untouched.

**The safety boundary, stated honestly.** Running something that clicks buttons
unattended is only responsible if it is contained. OpenAmer ships a native
Windows sandbox built on a kernel job object (`agent/win_sandbox.py`), and it
needs no administrator rights:

- whole process tree dies when the sandbox closes (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) — no orphaned daemons
- hard cap on concurrent processes (`JOB_OBJECT_LIMIT_ACTIVE_PROCESS`) — blocks fork bombs
- per-process and per-job memory ceilings
- no clipboard access, no handles into other processes, no global/desktop changes (`JOB_OBJECT_UILIMIT_*`)
- children cannot break out of the job (breakaway is deliberately never set)

Two things are *not* enforced, and I would rather say so than overclaim: network
egress is not OS-isolated on native Windows (that needs admin-only WFP rules —
`describe_enforcement()` reports it as `partial`, never as enforced), and the
filesystem boundary constrains what our own tools write, not raw Win32 calls.
It is opt-in and off by default.

**The rest of the stack is depth under that wedge, not the pitch.** It learns
from sessions and evolves a skill population (mutation + crossover +
fitness selection). A workflow immune system re-finds UI elements when a site
redesigns overnight and patches its own selectors. It can run on CPU at
<1 kWh/day for 0 EUR, so a solo dev can leave it on.

**Honest traction.** This is early. No inflated star count from me — the honest
signal I'll cite is marketplace placement, verified 2026-09-14: OpenRouter
cli-agent rank #38/50, ide-extension rank #7/9. Everything claimed above is
shipped and has test evidence in the repo; where I don't have a verified number
I've left it out rather than guessed.

I'm here to answer questions — especially "why not just use Playwright" (answer:
it drives a browser, not the app you can't script) and "how do you keep it from
wrecking my session" (answer: the job object above, plus an approval gate).

Repo: https://github.com/openamer/openamer
Docs: https://github.com/openamer/openamer/tree/main/website/docs