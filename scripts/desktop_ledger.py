#!/usr/bin/env python3
"""Desktop Evidence Ledger — every desktop action, with pixel proof.

No other agent documents what it did on your desktop. This one does.

The claim "the agent clicked Save" is only verifiable if you can see the screen
before and after. This ledger stores both frames, their SHA-256s, and a measured
pixel delta, so any action can be audited afterwards — long after the window is
gone.

Why a delta and not just "it ran":
  Desktop automation has one signature silent failure — the action reports
  ok:true and nothing on screen changed (a background click posted to a window
  that did not act on it, a keystroke routed to the wrong window, a button that
  was never there). Recording only success/failure cannot see that. Recording
  the PIXELS can: an action with no visible effect is flagged NO-VISIBLE-EFFECT
  and is the first thing an audit shows.

Design notes (deliberate):
  * Frames are COPIED into the ledger. A screenshot in %TEMP% proves nothing
    tomorrow; the copy is what makes the evidence survive.
  * If Pillow/numpy are missing the ledger degrades honestly to a SHA-256
    comparison and says so (`method: "sha256-only"`) — it never invents a
    percentage it did not measure.
  * No module-level side effects: import-safe, so it is testable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_HOME = Path(
    os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop")
)
LEDGER_DIR = DEFAULT_HOME / "desktop-ledger"

# Anti-aliasing / cursor-blink noise: a pixel must move by more than this to
# count as a real change. Without it, every frame with a blinking caret would
# look like a change and the flag would be useless.
NOISE_TOLERANCE = 8

DEFAULT_MAX_FRAMES = 400  # rotation: keep the ledger from growing without bound


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_info(path) -> dict:
    """Identity of a frame: content hash plus, when possible, its geometry.

    Carries `name` (the ledger-relative filename) so `verify()` can find the
    stored copy again — the absolute `path` is recorded for humans and may not
    exist any more, which is exactly the point of copying the frame in.
    """
    p = Path(path)
    info = {"path": str(p), "name": p.name,
            "sha256": sha256_file(p), "bytes": p.stat().st_size}
    try:
        from PIL import Image

        with Image.open(p) as im:
            info["width"], info["height"] = im.size
            info["mode"] = im.mode
    except Exception:
        pass  # geometry is a bonus; the hash is the evidence
    return info


def compare(before, after) -> dict:
    """Measured difference between two frames.

    Returns a dict that always carries `changed` and a `method` naming how that
    was established — so a degraded comparison can never be mistaken for a
    measured one.
    """
    before, after = Path(before), Path(after)
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        same = sha256_file(before) == sha256_file(after)
        return {"changed": not same, "method": "sha256-only", "pct_changed": None,
                "note": "Pillow/numpy unavailable — no pixel measurement"}

    a = np.asarray(Image.open(before).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(after).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return {"changed": True, "method": "size-mismatch", "pct_changed": 100.0,
                "note": f"{a.shape} != {b.shape}"}

    delta = np.abs(a - b).max(axis=2)          # strongest channel move per pixel
    mask = delta > NOISE_TOLERANCE
    changed = int(mask.sum())
    total = int(delta.size)
    result = {
        "changed": changed > 0,
        "method": "pixel-diff",
        "pct_changed": round(100.0 * changed / total, 4),
        "mean_delta": round(float(delta.mean()), 4),
        "tolerance": NOISE_TOLERANCE,
    }
    if changed:
        ys, xs = np.nonzero(mask)
        result["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return result


def verdict(change: dict, expect_effect: bool) -> str:
    """A one-word audit result: did the action visibly do anything?"""
    if not expect_effect:
        return "informational"
    return "effective" if change.get("changed") else "NO-VISIBLE-EFFECT"


class Ledger:
    def __init__(self, home=None, max_frames: int = DEFAULT_MAX_FRAMES):
        self.dir = Path(home) / "desktop-ledger" if home else LEDGER_DIR
        self.journal = self.dir / "journal.jsonl"
        self.frames_dir = self.dir / "frames"
        self.max_frames = max_frames
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    # -- writing ----------------------------------------------------------
    def _store_frame(self, src, tag: str, entry_id: str) -> Path:
        src = Path(src)
        dest = self.frames_dir / f"{entry_id}-{tag}{src.suffix or '.png'}"
        shutil.copy2(src, dest)
        return dest

    def record(self, action: str, before=None, after=None, note: str = "",
               actor: str = "openamer", expect_effect: bool = True) -> dict:
        entry_id = uuid.uuid4().hex[:12]
        entry = {
            "id": entry_id,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor,
            "action": action,
            "note": note,
        }
        if before is not None and after is not None:
            stored_before = self._store_frame(before, "before", entry_id)
            stored_after = self._store_frame(after, "after", entry_id)
            entry["before"] = frame_info(stored_before)
            entry["after"] = frame_info(stored_after)
            entry["change"] = compare(stored_before, stored_after)
            entry["verdict"] = verdict(entry["change"], expect_effect)
        elif before is None and after is None:
            entry["verdict"] = "informational"
        else:
            # One frame only: we cannot measure a delta and we do not pretend to.
            single = before if before is not None else after
            entry["frame"] = frame_info(self._store_frame(single, "single", entry_id))
            entry["verdict"] = "unpaired"
        self._append(entry)
        self._rotate()
        return entry

    def _append(self, entry: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.journal, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _rotate(self) -> None:
        """Keep only the newest N frames (evidence is timestamped, not infinite)."""
        frames = sorted(self.frames_dir.glob("*"), key=lambda p: p.stat().st_mtime)
        for old in frames[: max(0, len(frames) - self.max_frames)]:
            try:
                old.unlink()
            except OSError:
                pass

    # -- reading ----------------------------------------------------------
    def entries(self) -> list:
        if not self.journal.exists():
            return []
        out = []
        with open(self.journal, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a torn line must not kill the whole audit
        return out

    def suspicious(self) -> list:
        """Actions that reported success but changed nothing on screen."""
        return [e for e in self.entries() if e.get("verdict") == "NO-VISIBLE-EFFECT"]

    def verify(self) -> dict:
        """Re-hash every stored frame: has the evidence been altered or lost?"""
        report = {"checked": 0, "ok": 0, "modified": [], "missing": []}
        for entry in self.entries():
            for side in ("before", "after", "frame"):
                info = entry.get(side)
                if not info:
                    continue
                report["checked"] += 1
                name = info.get("name") or Path(info.get("path", "")).name
                path = self.frames_dir / name
                if not name or not path.is_file():
                    report["missing"].append(info.get("path"))
                    continue
                if sha256_file(path) == info.get("sha256"):
                    report["ok"] += 1
                else:
                    report["modified"].append(str(path))
        report["intact"] = not report["modified"] and not report["missing"]
        return report

    def report(self, limit: int = 25) -> str:
        entries = self.entries()[-limit:]
        if not entries:
            return "Desktop ledger is empty — no desktop action has been recorded yet."
        lines = [
            "# Desktop Evidence Ledger",
            "",
            f"_{len(self.entries())} actions recorded; showing the newest "
            f"{len(entries)}._",
            "",
            "| when (UTC) | action | verdict | pixels changed |",
            "|---|---|---|---|",
        ]
        for e in reversed(entries):
            change = e.get("change") or {}
            pct = change.get("pct_changed")
            shown = "—" if pct is None else f"{pct}%"
            lines.append(
                f"| {e.get('ts','')} | {e.get('action','')} | `{e.get('verdict','')}` | {shown} |"
            )
        bad = self.suspicious()
        if bad:
            lines += [
                "",
                f"## ⚠️ {len(bad)} action(s) with NO visible effect",
                "",
                "These reported success but changed nothing on screen — the silent",
                "failure mode of desktop automation. Inspect each before trusting it.",
                "",
            ]
            for e in bad[-10:]:
                lines.append(f"- `{e.get('ts','')}` **{e.get('action','')}** — {e.get('note','')}")
        return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Desktop Evidence Ledger")
    ap.add_argument("--home", default=None, help="override ledger home (tests)")
    sub = ap.add_subparsers(dest="cmd")

    rec = sub.add_parser("record", help="record one desktop action")
    rec.add_argument("--action", required=True)
    rec.add_argument("--before")
    rec.add_argument("--after")
    rec.add_argument("--note", default="")
    rec.add_argument("--actor", default="openamer")
    rec.add_argument("--expect-no-effect", action="store_true",
                     help="the action intentionally changes nothing (e.g. a probe)")

    rep = sub.add_parser("report")
    rep.add_argument("-n", type=int, default=25)

    sub.add_parser("suspicious")
    sub.add_parser("verify")

    args = ap.parse_args(argv)
    led = Ledger(home=args.home)

    if args.cmd == "record":
        entry = led.record(args.action, args.before, args.after, args.note,
                           args.actor, expect_effect=not args.expect_no_effect)
        print(json.dumps(entry, ensure_ascii=False, indent=1))
        return 0 if entry["verdict"] != "NO-VISIBLE-EFFECT" else 0
    if args.cmd == "suspicious":
        bad = led.suspicious()
        print(json.dumps(bad, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "verify":
        v = led.verify()
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0 if v["intact"] else 1
    if args.cmd == "report":
        print(led.report(args.n))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())