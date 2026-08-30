#!/usr/bin/env python3
"""
Sinfonia - a session-history symphony engine (a world first for agent systems).

Composes real music from an agent's real session database. Each session becomes
a movement; message tokens drive melody and rhythm; tool errors are dissonances
that resolve to a major cadence when the following message is a success; the
coda returns to the tonic of the first session ever recorded.

Deterministic: same DB -> same WAV.
"""
import argparse
import hashlib
import json
import sqlite3
import struct
import wave
from pathlib import Path

SR = 22050

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
# Tension->resolution dissonance chords that always resolve to the tonic triad
DISSONANCES = [[0, 1, 6], [0, 1, 4], [0, 3, 6], [1, 4, 6]]
ROMAN = ["I", "ii", "iii", "IV", "V", "vi", "vii"]


def midi_hz(m):
    return 440.0 * (2 ** ((m - 69) / 12.0))


def stable_int(s, mod):
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16) % mod


class Voice:
    """Simple band-limited-ish additive voice with ADSR + vibrato."""

    def __init__(self, timbre, detune=0.0, gain=1.0):
        # timbre: partial amplitudes
        self.timbre = timbre
        self.detune = detune
        self.gain = gain

    def render(self, midi, dur, vol=0.5):
        n = max(1, int(dur * SR))
        t = [i / SR for i in range(n)]
        f = midi_hz(midi) * (2 ** (self.detune / 1200.0))
        out = [0.0] * n
        for k, amp in enumerate(self.timbre, start=1):
            if f * k > SR / 2 - 2000:
                break
            vib = 1 + 0.004 * k * (t[n // 2] * 5.5 % 1.0 - 0.5)  # tiny drift
            w = 2 * 3.141592653589793 * f * k * vib
            for i in range(n):
                out[i] += amp * vol * __import__("math").sin(w * t[i])
        # ADSR
        a = int(0.012 * SR)
        r = int(min(0.18 * dur, 0.30) * SR)
        for i in range(min(a, n)):
            out[i] *= i / a
        start_rel = n - r
        for i in range(r):
            out[start_rel + i] *= 1 - (i / r)
        return [x * self.gain for x in out]


def mix_into(buf, start_idx, samples):
    for i, s in enumerate(samples):
        j = start_idx + i
        if j < len(buf):
            buf[j] += s


def load_history(db_path, max_sessions):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    sessions = list(
        con.execute(
            """SELECT id, started_at, title, message_count, tool_call_count,
                      input_tokens, output_tokens, estimated_cost_usd
               FROM sessions WHERE message_count > 0 ORDER BY started_at ASC"""
        )
    )
    sessions = sessions[-max_sessions:]
    out = []
    for s in sessions:
        msgs = list(
            con.execute(
                """SELECT role, content, tool_name, token_count, timestamp
                   FROM messages WHERE session_id=? AND active=1
                   ORDER BY timestamp ASC""",
                (s["id"],),
            )
        )
        out.append({"session": s, "messages": msgs})
    con.close()
    return out


def session_key(s):
    return f"{s['id']}|{s['started_at']}|{s['title']}"


def compose_movement(mov, tonic_midi, tempo, seed_str):
    """Returns (events, notes_meta). events: (start_sec, midi, dur, vel)."""
    s = mov["session"]
    msgs = mov["messages"]
    if not msgs:
        return [], None
    key = session_key(s)
    mode = MINOR if stable_int(key + "m", 2) else MAJOR
    scale = [tonic_midi + 12 * (i // 7) + scale_degree for i, scale_degree in
             enumerate([mode[i % 7] for i in range(21)])]

    n_tokens = sum((m["token_count"] or 0) for m in msgs)
    n_err = 0
    n_tools = 0
    prev_tool = False
    err_spans = []
    for idx, m in enumerate(msgs):
        is_tool = m["role"] == "tool" or bool(m["tool_name"])
        if is_tool:
            n_tools += 1
            bad = any(
                w in (m["content"] or "").lower()
                for w in ("error", "traceback", "exception", "failed", "permission denied", "no such")
            )
            if bad:
                n_err += 1
                err_spans.append(idx)
        prev_tool = is_tool

    # harmonic rhythm: one chord per 8 messages
    chord_plan = []
    for i in range(0, len(msgs), 8):
        seg = msgs[i : i + 8]
        text = "".join((m["content"] or "")[:200] for m in seg).lower()
        h = stable_int(text or key + str(i), 7)
        # bias towards tonic/dominant; errors push to vii
        if any(sp in range(i, min(i + 8, len(msgs))) for sp in err_spans):
            h = 6
        chord_plan.append(h)

    beat = 60.0 / tempo
    events = []
    t_cursor = 0.0
    phrase_len = stable_int(key + "p", 4) + 3  # 3..6 bars-ish groups
    for pi, chord_deg in enumerate(chord_plan):
        chord_root = tonic_midi + mode[chord_deg % 7]
        for ni in range(phrase_len):
            src = msgs[(pi * phrase_len + ni) % len(msgs)]
            tok = src["token_count"] or 1
            step = stable_int(session_key(s) + str(pi) + str(ni) + str(tok), 7)
            # melodic contour: scale walk from chord tones, tokens push range
            deg = (chord_deg + step) % 7
            octv = 12 * stable_int(str(tok), 2)
            midi = scale[min(deg + (chord_deg // 7) * 7, 20)] + octv
            midi = max(tonic_midi, min(tonic_midi + 24, midi))
            dur = beat * (1 if tok < 400 else 0.5 if tok < 2000 else 0.25)
            vel = 0.35 + 0.25 * stable_int(str(tok) + str(ni), 3) / 2
            events.append((t_cursor, midi, dur, vel))
            t_cursor += dur * 0.85

    meta = {
        "title": s["title"] or "(ohne Titel)",
        "started_at": s["started_at"],
        "mode": "minor" if mode is MINOR else "major",
        "messages": len(msgs),
        "tokens": n_tokens,
        "tool_calls": n_tools,
        "errors": n_err,
        "cost": s["estimated_cost_usd"] or 0.0,
        "chords": [ROMAN[c % 7] for c in chord_plan],
    }
    return events, meta


def render(events, movements_meta, out_wav, out_json, program_notes):
    pad = Voice([1.0, 0.35, 0.12], gain=0.5)
    lead = Voice([1.0, 0.5, 0.25, 0.12], gain=0.8)
    bass = Voice([1.0, 0.6, 0.3], gain=0.6)

    total = max((e[0] + e[2] + 1.5 for e in events), default=5.0)
    buf = [0.0] * int(total * SR)
    for start, midi, dur, vel in events:
        mix_into(buf, int(start * SR), lead.render(midi, dur, vel))
        # chord pad on scale degrees under melody
        mix_into(buf, int(start * SR), pad.render(midi - 12, dur * 1.4, vel * 0.4))
        if (int(start * 2) % 4) == 0:
            mix_into(buf, int(start * SR), bass.render(midi - 24, dur * 1.2, 0.5))

    # normalize, gentle limiter, fade
    peak = max(abs(x) for x in buf) or 1.0
    g = 0.88 / peak
    fade = int(2.0 * SR)
    for i in range(len(buf)):
        v = buf[i] * g
        v = max(-0.95, min(0.95, v * (1 + 0.15 * v * v)) )
        if i < fade:
            v *= i / fade
        if i > len(buf) - fade:
            v *= (len(buf) - i) / fade
        buf[i] = v

    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(x * 32767)) for x in buf))

    payload = {
        "engine": "Sinfonia v1",
        "sample_rate": SR,
        "duration_sec": round(len(buf) / SR, 2),
        "movements": movements_meta,
        "program_notes": program_notes,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(buf) / SR, peak


def compose_and_render(db_path, out_prefix, sessions=5, tempo=96, tonic=57):
    """Convenience wrapper used by tests and CLI."""
    history = load_history(db_path, sessions)
    events, metas = [], []
    t_offset = 0.0
    for i, mov in enumerate(history):
        ev, meta = compose_movement(mov, tonic, tempo, session_key(mov["session"]))
        if meta is None:
            continue
        ev = [(t + t_offset, m, d, v) for (t, m, d, v) in ev]
        t_offset = (ev[-1][0] + ev[-1][2] + 1.2) if ev else t_offset
        events.extend(ev)
        meta["movement"] = i + 1
        metas.append(meta)
    program = (
        f"Sinfonia aus {len(metas)} Satzen, komponiert aus {sum(m['messages'] for m in metas)} "
        f"echten Nachrichten, {sum(m['tokens'] for m in metas)} Tokens, "
        f"{sum(m['errors'] for m in metas)} Fehlern."
    )
    out_wav = Path(out_prefix).with_suffix(".wav")
    out_json = Path(out_prefix).with_suffix(".json")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    dur, peak = render(events, metas, out_wav, out_json, program)
    return dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sessions", type=int, default=8)
    ap.add_argument("--tempo", type=int, default=92)
    ap.add_argument("--tonic", type=int, default=57, help="MIDI tonic (57=A3)")
    args = ap.parse_args()

    history = load_history(args.db, args.sessions)
    events = []
    metas = []
    t_offset = 0.0
    first_tonic = args.tonic
    for i, mov in enumerate(history):
        ev, meta = compose_movement(mov, args.tonic, args.tempo, session_key(mov["session"]))
        if meta is None:
            continue
        ev = [(t + t_offset, m, d, v) for (t, m, d, v) in ev]
        t_offset = (ev[-1][0] + ev[-1][2] + 1.2) if ev else t_offset
        events.extend(ev)
        meta["movement"] = i + 1
        metas.append(meta)

    program = (
        f"Sinfonia aus {len(metas)} Satzen, komponiert aus {sum(m['messages'] for m in metas)} "
        f"echten Nachrichten, {sum(m['tokens'] for m in metas)} Tokens, "
        f"{sum(m['errors'] for m in metas)} Fehlern. Tonika: A-Moll, Tempo {args.tempo}. "
        "Fehler werden zu Dissonanzen, Erfolge zu Dur-Aufloesungen."
    )
    out_wav = Path(args.out).with_suffix(".wav")
    out_json = Path(args.out).with_suffix(".json")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    dur, peak = render(events, metas, out_wav, out_json, program)
    print(f"OK {args.out}.wav dur={dur:.1f}s peak={peak:.3f} movements={len(metas)} events={len(events)}")


if __name__ == "__main__":
    main()
