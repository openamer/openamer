# Wedge-first launch copy — layout, checklist, worked example

Companion to Phase 1b in SKILL.md. Use when rewriting a scattered feature list
into one repeated idea across every outward post.

## Canonical file layout

```
docs/positioning.md          # the ONE wedge sentence + who it is for (source of truth)
docs/launch/hn-show.md       # Show HN: title (≤80 ch), URL, first comment
docs/launch/reddit.md        # one tailored post per sub (r/LocalLLaMA, r/selfhosted, …)
docs/launch/producthunt.md   # tagline (≤60 ch), short + long description, maker first comment
docs/launch/devto.md         # technical article on how the wedge is implemented
```

Leave any superseded draft (e.g. `docs/show-hn-entwurf.md`) as a short pointer to
the new canonical file with a do-not-post warning — do not silently delete it.

## Non-negotiables

- **Wedge used verbatim as the opening line of every post.** Only title + body
  tone adapt. The sentence itself never changes between platforms.
- **Every technical claim verified against the repo** — grep for the real module
  and quote its path (`tools/computer_use/cua_backend.py`, `agent/win_sandbox.py`).
- **No invented numbers.** Verified figures get a date (e.g. "as of 2026-09-14:
  OpenRouter cli-agent #38/50, ide-extension #7/9"). Unverifiable numbers become
  `[VERIFY: …]` inline or are dropped. Stars stated honestly, never inflated.
- **Honest edge stated, not hidden.** Name what is *not* enforced (network egress
  not OS-isolated on native Windows; filesystem boundary is policy not ACL).
- **Commit only the launch files.** The working tree is usually dirty with
  unrelated files — `git add docs/launch/ docs/<pointer>.md` explicitly; never
  `git add -A` / `git add .`.

## Per-platform recipe

| Platform | Hard limit | Tone rule |
|---|---|---|
| Show HN | title ≤ 80 chars | no adjectives, no emoji; mechanism + limits; first comment invites the 2 questions you expect |
| r/LocalLLaMA | — | technical: local models, hardware, cost, "does it run locally" |
| r/selfhosted | descriptive title | what you run, where data lives, no phone-home; answer that first |
| Product Hunt | tagline ≤ 60 chars | tagline derived directly from the wedge; short + long description + maker comment |
| Dev.to | — | article on *how the wedge is implemented*, not a pitch |

HN/PH title "two title" trick: put the primary in a fenced block and a fallback
in parentheses so the poster can swap if one is too long.

## Worked example (OpenAmer, 2026-09-14)

Wedge:

> OpenAmer drives your Windows desktop in the background — without taking your
> mouse.

Why this one cleared the bar (the three tests a claim must pass):

1. **True and demonstrable today** — `tools/computer_use/cua_backend.py` routes
   background input; the real OS cursor never moves.
2. **No competitor can copy the sentence truthfully** — documented in
   `docs/security/windows-sandbox.md` (Claude Code OS sandbox unsupported on
   native Windows; Codex ships a single unelevated fallback; Cline/Roo/Aider are
   IDE-panel tools with no desktop control).
3. **Picturable in ten seconds** — "it clicks buttons in the app you already have
   open while you keep typing in another window."

PH tagline (54 chars, derived from wedge):
`Drives your Windows desktop without taking your mouse`

Supporting detail (the "depth under the wedge", NOT a second pitch): admin-free
kernel job-object sandbox (`agent/win_sandbox.py`) as proof the control is safe;
self-improving skill loop; runs on CPU <1 kWh/day for 0 €.

## Verification checklist

- [ ] Wedge sentence copied verbatim as the opening of all four posts
- [ ] Every mechanism claim points at a real file confirmed in the repo
- [ ] No unverified number presented as fact (`[VERIFY: …]` or omitted)
- [ ] Honest limits stated in the HN / technical posts
- [ ] Files written under `docs/launch/`; old draft turned into a pointer
- [ ] Only launch files staged; committed; pushed
- [ ] `git rev-parse HEAD` == `git ls-remote origin refs/heads/main`
