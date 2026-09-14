# Desktop Evidence Ledger — what no other agent has

Every other agent that drives a desktop tells you **what it did**. This one
shows you **what changed on screen**, with the before/after frames and a
measured pixel delta to back it.

```
$ python scripts/desktop_ledger.py report

| when (UTC)                | action                                          | verdict             | pixels changed |
|---------------------------|-------------------------------------------------|---------------------|----------------|
| 2026-09-14T20:37:38+00:00 | click on a non-interactive header area          | `NO-VISIBLE-EFFECT` | 0.0%           |
| 2026-09-14T20:34:16+00:00 | background type into a window never clicked     | `effective`         | 0.626%         |

## ⚠️ 1 action(s) with NO visible effect
```

Both rows above are real, from a live run on this machine (2026-09-14).

## The failure this catches — and why nothing else catches it

Desktop automation's signature silent failure is: **the action reports
`ok: true` and nothing on screen changes.**

- a background click posted to a window that ignored it,
- a keystroke routed to the wrong window,
- a button that was never there,
- a "Save" that saved nothing.

A success/failure log cannot see any of these — they *are* successes as far as
the driver is concerned. Only the pixels can see it. That is why the ledger
records a **measured delta**, not a status.

## What gets stored per action

| field | why |
|---|---|
| `before.sha256`, `after.sha256` | the evidence's identity; `verify()` re-hashes them |
| `before/after` **copies** | a `%TEMP%` screenshot proves nothing tomorrow — the copies survive |
| `change.pct_changed` | how much of the frame moved (0.626 % = one text line) |
| `change.bbox` | **where** it moved — a localised change reads very differently from a repaint |
| `change.tolerance` | the noise floor (8/channel), so AA and caret-blink don't fake a change |
| `verdict` | one word an audit can act on |

## Verdicts

| verdict | meaning |
|---|---|
| `effective` | pixels changed — it visibly did something |
| `NO-VISIBLE-EFFECT` | reported ok, nothing moved — **inspect before trusting** |
| `informational` | declared a no-op on purpose (`--expect-no-effect`) |
| `unpaired` | one frame only; no delta is claimed |

## Honest limits

- **It measures the screen, not intent.** A change in the measured region can
  come from any source (a clock ticking, another window overlapping). It proves
  *that* the pixels moved, not *why*.
- **A blinking caret is a real change.** An action that only moved the caret
  reports `effective` — correct, but not a sign the app did the thing.
- **Without Pillow/numpy it degrades to `sha256-only`** and says so; it never
  invents a percentage.
- **The region must be chosen by the caller.** Recording the whole desktop
  works, but records everything on screen — prefer the window rect from
  `scripts/demo_window_rect.py`.

## Reproduce

```bash
python scripts/demo_target.py &                       # a controlled window
python scripts/demo_window_rect.py                    # DPI-aware region (even dims)
ffmpeg -y -v error -f gdigrab -framerate 1 \
  -offset_x X -offset_y Y -video_size WxH -i desktop -frames:v 1 "C:/tmp/before.png"
# ... perform the desktop action ...
ffmpeg -y -v error -f gdigrab -framerate 1 \
  -offset_x X -offset_y Y -video_size WxH -i desktop -frames:v 1 "C:/tmp/after.png"
python scripts/desktop_ledger.py record \
  --action "click Save" --before "C:/tmp/before.png" --after "C:/tmp/after.png"
python scripts/desktop_ledger.py verify
```

Tests: `python -m pytest tests/scripts/test_desktop_ledger.py -q` (14 tests,
including the two load-bearing ones — the silent failure is flagged, and the
evidence survives deletion of the source frames).