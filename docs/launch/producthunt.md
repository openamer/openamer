# Product Hunt — OpenAmer

PH conventions: the **tagline** is hard-capped at 60 characters and is the whole
first impression. The **description** is the short pitch. The **first comment**
is where makers actually talk. All three derive from the one wedge.

## Tagline (<= 60 chars)

```
Drives your Windows desktop without taking your mouse
```

(54 chars — derived directly from the wedge sentence.)

## Short description

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

It works the apps on your machine that have no API — an ERP client, an old
internal tool, a desktop app that never grew a scripting interface — by
clicking and typing *inside* them while you keep working in another window. Your
real cursor never moves; the agent gets a tinted overlay cursor of its own.

## Longer description (for the body / gallery text)

Most agents stop at the browser or the terminal. OpenAmer drives the desktop:
it acts in the window you already have open, in the background, without stealing
focus.

- **Background desktop control.** Routed through cua-driver so input reaches the
  target window without raising it or grabbing your mouse. The agent reports
  per-action whether the effect landed and re-reads the screen before escalating
  — no blind retries.
- **A real safety boundary, admin-free.** A native Windows sandbox on a kernel
  job object: process-tree teardown on close, a concurrent-process cap, memory
  ceilings, no clipboard/cross-process handles, no breakaway. Opt-in, off by
  default.
- **It gets better without us shipping.** Skills built from sessions, then
  evolved by mutation/crossover/fitness selection; a workflow immune system
  re-finds UI elements when a site redesigns overnight.
- **Runs on CPU, <1 kWh/day, 0 EUR.** Leave it on. Local state, local memory,
  local credentials — Windows-native, no WSL.

Honest scope: network egress is not OS-isolated on native Windows without admin,
and the write boundary is enforced by our tools rather than an ACL. Early
project — verified placement 2026-09-14: OpenRouter cli-agent #38/50,
ide-extension #7/9.

## First comment (maker comment)

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

Hi Product Hunt! Maker here.

The origin story is a boring, specific frustration: a Windows machine full of
apps I couldn't script. An ERP client, an old internal tool, a desktop app with
no API. I tried to automate it, hit the wall "this thing has no API", and gave
up — enough times that I built the thing that doesn't give up at that wall.

So OpenAmer works the app you already have open, in the background. You keep
typing in another window; the agent clicks and types in the target window with
its own tinted cursor, and your real mouse never moves.

Two questions I expect, answered up front:

1. **"How is this different from a browser agent?"** A browser agent drives a
   browser. OpenAmer drives the desktop app that has no API — that's the wall
   nobody else's sentence clears.
2. **"Is it safe to let it click things unattended?"** That's exactly why it
   ships a native, admin-free Windows sandbox (kernel job object): it kills the
   whole process tree on close, caps concurrent processes, caps memory, and
   blocks clipboard/cross-process handles. It's opt-in and off by default. I'm
   honest about what it does *not* enforce, too — network egress isn't
   OS-isolated on native Windows, and the write boundary is policy, not ACL.

It also learns from every session and can run on CPU at under 1 kWh/day for
0 EUR, so you can leave it on. It's early — no inflated numbers from me; the
verified signal is marketplace placement (OpenRouter cli-agent #38/50,
ide-extension #7/9, as of 2026-09-14).

Would love your feedback — especially from anyone automating a Windows app with
no API. What's the app that made you give up?

Repo: https://github.com/openamer/openamer