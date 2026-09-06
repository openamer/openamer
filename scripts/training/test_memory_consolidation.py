#!/usr/bin/env python3
"""Tests for memory_consolidation.py.

Run:  python test_memory_consolidation.py
Covers: scoring, promotion, compression, archiving, and the never-delete
        invariant — using a TEMP copy of the store so the real memory is
        never touched.
"""
import json, os, sys, tempfile, datetime, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_consolidation as mc


def _make_episode(text, days_old, kind="brain_user"):
    ts = (datetime.datetime.now() - datetime.timedelta(days=days_old)).isoformat()
    return {"ts": ts, "kind": kind, "text": text, "meta": {}}


def _setup_temp_store(episodes):
    """Point the module at a temp store, return the temp dir."""
    tmp = tempfile.mkdtemp(prefix="mc_test_")
    mc.EPISODES = os.path.join(tmp, "episodes.jsonl")
    mc.ARCHIVE = os.path.join(tmp, "archive.jsonl")
    mc._save(mc.EPISODES, episodes)
    return tmp


def test_old_low_usefulness_gets_compressed():
    eps = [
        _make_episode("This is an old unimportant memory about a random thing.", 45),
        _make_episode("Fresh memory from today.", 1),
    ]
    tmp = _setup_temp_store(eps)
    mc.META_STATE = os.path.join(tmp, "meta_state.json")  # no usefulness data
    r = mc.consolidate(dry_run=True)
    assert r["compressed"] == 1, f"expected 1 compressed, got {r['compressed']}"
    assert r["kept_after"] == 2, "compressed pointer + fresh = 2 kept"
    shutil.rmtree(tmp)


def test_recent_episode_not_compressed():
    eps = [_make_episode("Recent memory, only 5 days old.", 5)]
    tmp = _setup_temp_store(eps)
    mc.META_STATE = os.path.join(tmp, "meta_state.json")
    r = mc.consolidate(dry_run=True)
    assert r["compressed"] == 0, "recent episode must not be compressed"
    shutil.rmtree(tmp)


def test_high_usefulness_promoted_to_permanent():
    eps = [_make_episode("This memory led to a fix and is very useful.", 60)]
    tmp = _setup_temp_store(eps)
    # simulate usefulness: this hash led to a fix
    h = mc._hash("This memory led to a fix and is very useful.")
    meta = {"memory_usefulness": {h: {"retrievals": 5, "led_to_fix": 2}}}
    mc.META_STATE = os.path.join(tmp, "meta_state.json")
    json.dump(meta, open(mc.META_STATE, "w"))
    r = mc.consolidate(dry_run=True)
    assert r["permanent"] == 1, "useful memory must be promoted to permanent"
    assert r["compressed"] == 0, "permanent memory must never be compressed"
    shutil.rmtree(tmp)


def test_archive_never_deletes_originals():
    eps = [_make_episode("Old memory to be archived.", 40)]
    tmp = _setup_temp_store(eps)
    mc.META_STATE = os.path.join(tmp, "meta_state.json")
    r = mc.consolidate(dry_run=False)
    # archive must contain the compressed summary
    arch = mc._load(mc.ARCHIVE)
    assert len(arch) == 1, "archive must hold the compressed original"
    assert arch[0]["summary"], "summary must be non-empty"
    # active store must still have a pointer (never fully deleted)
    active = mc._load(mc.EPISODES)
    assert any(e.get("kind") == "compressed" for e in active), \
        "compressed pointer must remain in active store"
    shutil.rmtree(tmp)


def test_summarize_strips_system_noise():
    text = "[System note: interrupted] The server ran out of memory and crashed."
    s = mc._summarize(text)
    assert "System note" not in s, "system noise must be stripped"
    assert "memory" in s.lower(), "real content must be kept"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {e}")
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
