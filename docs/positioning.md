# OpenAmer — the one-line wedge

**Status:** draft, 2026-09-14. Owner: OpenAmer Agent.

Why this file exists: the README lists **20** unique features. Twenty USPs is not
a positioning — it is a feature dump, and it reads as noise to the exact person
we need (a developer scrolling a feed). Every competitor also has a list. This
file argues for **one** claim we can make that no competitor can, and treats
everything else as supporting detail.

---

## The wedge

> **OpenAmer drives your Windows desktop in the background — without taking your
> mouse.**

One sentence. Falsifiable. Nobody else can say it.

## Why this one, and not the other 19

A positioning claim is only worth making if three things hold:

1. **It is true and demonstrable.** We have `computer_use` (cua-driver), and the
   desktop app's own co-work model is built so the *real* OS cursor never moves —
   the agent gets a tinted overlay cursor of its own. This is not a roadmap item;
   it runs today.
2. **No competitor can truthfully copy the sentence.** Claude Code's OS sandbox
   is documented as unsupported on native Windows ("run it inside WSL2"); Codex
   ships a single unelevated fallback; Cline/Roo/Aider are IDE-panel tools with
   no desktop control at all. The nearest thing anyone ships is a browser-driving
   harness that takes focus.
3. **A stranger feels the difference in ten seconds.** "It clicks buttons in the
   app you already have open, while you keep typing in another window" is a
   sentence a person can picture before they finish reading it.

The self-learning, the A2A swarm, the dream cycle, the vector memory — all real,
all ours. They are the *depth* under this wedge. None of them is the wedge,
because a stranger cannot picture any of them in ten seconds.

## Who it is for (be specific)

Someone on **Windows** who already has a screen full of tools they cannot script:
an ERP client, an old internal tool, a desktop app with no API. They have tried
to automate it, hit the wall "this thing has no API", and moved on. We are the
answer to that wall.

Not "developers" — that is everyone's audience and therefore nobody's.

## The supporting three (not the pitch)

| Claim | Role |
|---|---|
| A Windows sandbox no rival has (kernel job object, admin-free) | proof the desktop control is *safe* to run |
| Learns from every session (self-improving loop) | proof it gets better without us shipping |
| Runs on CPU, <1 kWh/day, 0 € | proof a solo dev can afford to leave it on |

## What this file changes

- README/deck: lead with the wedge sentence. The 20-feature table moves *below*
  the fold. It is evidence, not the headline.
- Every outward post (HN, Reddit, PH, Dev.to) opens with the same sentence, so
  the brand is one idea repeated, not twenty ideas scattered.
- The demo asset is **built**: `docs/demo/background-computer-use.gif` — a real,
  unedited screen recording showing the agent's own cursor acting on a window
  that was never clicked, with `GetCursorPos` proving the human pointer moved
  **0 px**. That is the sentence converted into ten seconds of proof. See
  `docs/demo/README.md` for the reproduction steps and its measured limits.