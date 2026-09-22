#!/usr/bin/env python3
"""Tests for repair_buffer.py — repairs glued records in online_buffer.jsonl.

Run:  python test_repair_buffer.py

Regression guard for the corruption seen live 15.09.2026: a writer appended a
record WITHOUT a separator, producing `...}"}{"u": ...` on one line. json.loads
then raised "Extra data" and every loader that skips bad lines silently dropped
BOTH records — a real learning vanished with no log entry. These tests prove
detection, repair, backup and idempotence. All work on a TEMP buffer — the real
online_buffer.jsonl is never touched.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repair_buffer as rb


def _glued_buf():
    """Two valid records concatenated with no separator — the live symptom."""
    d = tempfile.mkdtemp(prefix="repairbuf_test_")
    buf = os.path.join(d, "online_buffer.jsonl")
    a = json.dumps({"u": "q1", "a": "first insight with a verb"})
    b = json.dumps({"u": "q2", "a": "second insight"})
    with open(buf, "wb") as f:
        f.write((a + b + "\r\n").encode("utf-8"))
    return buf


def _parse(buf):
    """Records that a loader would actually recover (bad lines dropped)."""
    out = []
    for line in open(buf, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def test_glued_records_lose_both_before_repair():
    """Proves the bug is real: a glued pair yields ZERO recoverable records."""
    assert _parse(_glued_buf()) == []


def test_scan_flags_the_glued_line():
    raw = open(_glued_buf(), "rb", encoding="utf-8").read().decode("utf-8")
    assert rb.scan(raw) == [0]


def test_scan_is_clean_on_wellformed_buffer():
    d = tempfile.mkdtemp(prefix="repairbuf_test_")
    buf = os.path.join(d, "online_buffer.jsonl")
    with open(buf, "wb") as f:
        for i in range(3):
            f.write((json.dumps({"u": f"q{i}", "a": "x"}) + "\r\n").encode("utf-8"))
    assert rb.scan(open(buf, "rb").read().decode("utf-8")) == []


def test_fix_recovers_both_records_and_backs_up():
    buf = _glued_buf()
    sys.argv = ["repair_buffer.py", "--fix"]
    rb.BUF = buf
    assert rb.main() == 0
    assert [r["u"] for r in _parse(buf)] == ["q1", "q2"]
    # a sibling backup must exist so the raw evidence is never destroyed
    d = os.path.dirname(buf)
    assert any(n.startswith("online_buffer.jsonl.bak-") for n in os.listdir(d))


def test_fix_is_idempotent():
    buf = _glued_buf()
    sys.argv = ["repair_buffer.py", "--fix"]
    rb.BUF = buf
    rb.main()
    before = open(buf, "rb").read()
    assert rb.main() == 0  # nothing to repair -> clean exit
    assert open(buf, "rb").read() == before


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
