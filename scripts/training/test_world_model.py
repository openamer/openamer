#!/usr/bin/env python3
"""Tests for the central world model (world_model.py).

Run:  python test_world_model.py
Covers: observe (real embeddings), recall (semantic search), predict,
        stats health, and the no-placeholder invariant.
"""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world_model as wm


def _count_edges():
    return len(wm._load())


def test_observe_writes_real_embedding():
    before = _count_edges()
    e = wm.observe("disk full causes write failures", "free space or rotate logs")
    assert e["embed_ok"] is True, "embedding must be real"
    assert len(e["embedding"]) == wm.DIM, "embedding must be 768-dim"
    assert any(abs(x) > 0.5 for x in e["embedding"]), "embedding must not be a constant"
    assert _count_edges() == before + 1


def test_recall_finds_semantic_neighbour():
    wm.observe("RAM exhaustion kills the server process",
               "recovery requires releasing memory and restarting")
    hits = wm.recall("out of memory crash", k=3)
    assert hits, "recall must return results"
    assert hits[0]["score"] > 0.3, "top hit must be semantically close"
    assert "RAM" in hits[0]["cause"] or "memory" in hits[0]["cause"].lower()


def test_predict_projects():
    p = wm.predict("server running out of memory")
    assert p["status"] == "projected"
    assert p["predictions"], "predictions must be non-empty"


def test_stats_embed_health():
    s = wm.stats()
    assert s["embed_health"] == 1.0, "all embeddings must be real"
    assert s["total_edges"] >= 0


def test_no_placeholder_embeddings_in_code():
    import subprocess
    d = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run(["grep", "-rn", "0.1.*768", "--include=*.py", d],
                       capture_output=True, text=True)
    # exclude this test file itself (it contains the literal grep pattern)
    hits = [l for l in r.stdout.splitlines()
            if "test_world_model.py" not in l]
    assert not hits, f"placeholder embedding still present:\n{chr(10).join(hits)}"


def _cleanup_test_edges():
    """Remove edges added by these tests so the model isn't polluted."""
    test_causes = {
        "disk full causes write failures",
        "RAM exhaustion kills the server process",
    }
    lines = open(wm.WM, encoding="utf-8").readlines()
    kept = [l for l in lines
            if json.loads(l).get("cause") not in test_causes]
    open(wm.WM, "w", encoding="utf-8").writelines(kept)


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
    _cleanup_test_edges()
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
