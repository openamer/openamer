---
name: desktop-evidence-ledger
description: Prove what a desktop action did — pixel-proof ledger.
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [computer-use, evidence, audit, desktop, screenshot, verification]
    category: desktop
    related_skills: [windows-computer-use, computer-use]
---

# Desktop Evidence Ledger

Record every desktop action with a **before/after screenshot and a measured
pixel delta**, so the claim "the agent clicked X" is auditable afterwards.

## When to use

- After any `computer_use` action you want to be able to *prove* later.
- When an action reports `ok: true` but you are not sure it did anything.
- When you need an audit trail of what an autonomous agent did on a desktop.
- Whenever you would otherwise write "it worked" without evidence.

## Why it exists (the failure it catches)

Desktop automation has one signature silent failure: **the action reports
success and nothing on screen changes** — a background click posted to a window
that ignored it, a keystroke routed to the wrong window, a button that was never
there. Recording success/failure cannot see this. Recording the *pixels* can.

## The pattern

```bash
# 1. screenshot BEFORE  (ffmpeg — NOTE: gdigrab needs a WINDOWS path)
ffmpeg -y -v error -f gdigrab -framerate 1 \
  -offset_x X -offset_y Y -video_size WxH -i desktop -frames:v 1 "C:/tmp/before.png"

# 2. do the desktop action (computer_use click/type/key)

# 3. screenshot AFTER
ffmpeg -y -v error -f gdigrab -framerate 1 \
  -offset_x X -offset_y Y -video_size WxH -i desktop -frames:v 1 "C:/tmp/after.png"

# 4. record it
python scripts/desktop_ledger.py record \
  --action "click Save" --before "C:/tmp/before.png" --after "C:/tmp/after.png"
```

The region (`-offset_x/-offset_y/-video_size`) comes from
`scripts/demo_window_rect.py` — it is DPI-aware and snaps to EVEN dimensions,
which `libx264`/`yuv420p` require. Do not compute it by hand.

## Verdicts

| verdict | meaning |
|---|---|
| `effective` | pixels changed — the action visibly did something |
| `NO-VISIBLE-EFFECT` | reported ok, **nothing moved** — inspect before trusting |
| `informational` | you declared the action intentionally changes nothing (`--expect-no-effect`) |
| `unpaired` | only one frame was given; no delta is claimed |

## Commands

```bash
python scripts/desktop_ledger.py report -n 25     # markdown table + flags the bad ones
python scripts/desktop_ledger.py suspicious       # only the NO-VISIBLE-EFFECT entries
python scripts/desktop_ledger.py verify           # re-hash every stored frame -> tamper check
```

## Design facts worth knowing

- **Frames are COPIED into the ledger** (`<home>/desktop-ledger/frames/`). A
  screenshot in `%TEMP%` proves nothing tomorrow; the copy is the evidence.
  `verify()` therefore still passes after the source is deleted.
- **`bbox`** in the change record tells you *where* the screen moved, not just
  that it did — a 0.6 % change confined to one text line reads very differently
  from a full-screen repaint.
- **Tolerance 8** per channel filters anti-aliasing/caret-blink noise. Lower it
  to see smaller changes; raise it to ignore more jitter.
- **Degrades honestly**: without Pillow/numpy the method becomes `sha256-only`
  and `pct_changed` is `None` — never an invented percentage.
- Rotation keeps the newest 400 frames by default (`max_frames`).

## Pitfalls

- **ffmpeg is a Windows binary even under git-bash.** `-i desktop` and the
  output path must be Windows-style (`C:/…`); an MSYS path (`/c/…`) fails with
  "No such file or directory".
- **Same for the Python CLI**: pass `--before`/`--after` as `C:/…`, not `/c/…`,
  or you get `\c\Users\…` and a `FileNotFoundError`.
- **A blinking text caret is a real pixel change.** If an action only moved the
  caret it will report `effective`; that is correct, not a bug. Use
  `--expect-no-effect` when the action is genuinely a no-op probe.
- **Only compare same-sized frames**; a resize is reported as
  `method: size-mismatch`, `changed: true` — meaningful, but not a pixel delta.

## Verification

```bash
python -m pytest tests/scripts/test_desktop_ledger.py -q
python scripts/desktop_ledger.py verify    # exit 0 = evidence intact
```
