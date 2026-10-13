#!/usr/bin/env python3
"""Tests for the central world model (world_model.py).

Run:  python test_world_model.py
Covers: observe (real embeddings), recall (semantic search), predict,
        stats health, and the no-placeholder invariant.
"""
import json, os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world_model as wm


def _count_edges():
    return len(wm._load())


def test_observe_writes_real_embedding():
    # HERMETIC: parallel suites observe into the shared live store, so any
    # count assertion on wm.WM is a race. Point wm.WM at a temp store —
    # the observe/dedup contract is exercised identically.
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        cause = "disk full causes write failures"
        effect = "free space or rotate logs"
        e = wm.observe(cause, effect)
        assert e["embed_ok"] is True, "embedding must be real"
        assert len(e["embedding"]) == wm.DIM, "embedding must be 768-dim"
        assert any(abs(x) > 0.5 for x in e["embedding"]), "embedding must not be a constant"
        # observe deduplicates exact repeats: first call adds, repeat increments only
        assert _count_edges() == 1
        e2 = wm.observe(cause, effect)
        assert e2.get("dup_count", 1) >= 2, "repeat observe must increment dup_count"
        assert _count_edges() == 1, "repeat observe must NOT append a new edge"
    finally:
        wm.WM = old_wm
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_recall_finds_semantic_neighbour():
    # HERMETIC: isolated store — parallel consolidation prunes the shared
    # live store, so the just-observed edge could vanish mid-recall.
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        wm.observe("RAM exhaustion kills the server process",
                   "recovery requires releasing memory and restarting")
        hits = wm.recall("out of memory crash", k=3)
        assert hits, "recall must return results"
        assert hits[0]["score"] > 0.3, "top hit must be semantically close"
        assert "RAM" in hits[0]["cause"] or "memory" in hits[0]["cause"].lower()
    finally:
        wm.WM = old_wm
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_predict_projects():
    p = wm.predict("server running out of memory")
    assert p["status"] == "projected"
    assert p["predictions"], "predictions must be non-empty"


def test_stats_embed_health():
    # RACE-SAFE via isolated store: other suites (consolidation) prune the
    # shared live store in parallel — pointing wm.WM at a temp file makes
    # this test hermetic while still exercising the real stats path.
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        for i in range(3):
            wm.observe(f"test health edge {i} {time.time()}", "effect")
        s = wm.stats()
        assert s["embed_health"] == 1.0, f"test edges must embed real: {s}"
        assert s["total_edges"] >= 3
    finally:
        wm.WM = old_wm
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_placeholder_embeddings_in_code():
    import subprocess
    d = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run(["grep", "-rn", "0.1.*768", "--include=*.py", d],
                       capture_output=True, text=True)
    # exclude this test file itself (it contains the literal grep pattern)
    hits = [l for l in r.stdout.splitlines()
            if "test_world_model.py" not in l]
    assert not hits, f"placeholder embedding still present:\n{chr(10).join(hits)}"


def test_schema_migration_v1_to_v2():
    """Old v1 edges (type/predicted) must migrate to v2 (kind/cause/effect)."""
    old_pred = {"ts": "2026-09-01", "type": "prediction",
                "predicted": "If X recurs expect Y", "confidence": 0.6}
    m = wm._migrate_edge(dict(old_pred))
    assert m["kind"] == "prediction", m
    assert m["cause"] == "If X recurs expect Y", m
    assert m["effect"] == "", m
    assert m["schema_version"] == wm.SCHEMA_VERSION, m
    assert "type" not in m and "predicted" not in m, m

    old_fact = {"ts": "2026-09-01", "cause": "A", "effect": "B",
                "embedding": [0.0] * wm.DIM}
    m = wm._migrate_edge(dict(old_fact))
    assert m["kind"] == "fact", m
    assert m["schema_version"] == wm.SCHEMA_VERSION, m


def test_schema_migration_idempotent():
    """A v2 edge must pass through unchanged."""
    v2 = {"ts": "x", "schema_version": wm.SCHEMA_VERSION, "kind": "fact",
          "cause": "A", "effect": "B"}
    assert wm._migrate_edge(dict(v2)) == v2


def test_migrate_rewrites_store():
    """migrate() must rewrite a temp store to the current schema."""
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        with open(wm.WM, "w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "x", "type": "prediction",
                                "predicted": "If A recurs expect B"}) + "\n")
            f.write(json.dumps({"ts": "x", "cause": "A", "effect": "B",
                                "embedding": [0.0] * wm.DIM}) + "\n")
        r = wm.migrate()
        assert r["migrated"] == 2, r
        loaded = wm._load()
        assert all(e.get("schema_version") == wm.SCHEMA_VERSION for e in loaded)
    finally:
        wm.WM = old_wm
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def _remove_edge(cause):
    """Remove one edge by exact cause (test cleanup — guarded, never truncates)."""
    try:
        lines = open(wm.WM, encoding="utf-8").readlines()
        kept = [l for l in lines if l.strip()
                and json.loads(l).get("cause") != cause]
        if len(kept) == len(lines):
            return  # nothing to remove
        if not kept:
            return  # never write an empty store
        open(wm.WM, "w", encoding="utf-8").writelines(kept)
    except Exception:
        pass


def test_atomic_write_never_exposes_partial_file():
    """A concurrent reader must never parse a half-written store.

    Regression (16.09.26): every writer rewrote the store with
    open(WM, "w"), which truncates FIRST. A reader in another process
    (threading._lock is process-local) could then parse 0..N partial
    lines, and knowledge_to_action reported the phantom
    'not enough observed facts to predict from' against a 425-edge store.

    First fix attempt (temp file + os.replace) was NOT enough: os.replace is
    atomic, but a reader that opens the file between the writer's
    open(tmp,"w") and the swap still sees a truncated store, and when the
    swap hit PermissionError the writer fell back to the very in-place
    truncate being removed. Live probe against that version, 120-edge store,
    1.5s of traffic:

        reader saw lengths {0: 5, 120: 104}   <- 5 partial reads
        writer passes 44, os.replace ok 44, fallback 1

    So the contract this test pins is *writer and reader both take the
    store lock*. Same probe after the lock: {120: N} with zero partials.
    """
    import threading
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        seed = [json.dumps({'ts': str(i), 'schema_version': wm.SCHEMA_VERSION,
                            'kind': 'fact', 'cause': f'c{i}', 'effect': f'e{i}',
                            'embedding': [0.0] * wm.DIM, 'embed_ok': True})
                for i in range(120)]
        with wm._store_lock():
            wm._atomic_write(seed)
        assert len(wm._load()) == 120

        stop = {'v': False}

        def writer():
            n = 0
            while not stop['v']:
                # The writer side of the contract: hold the lock for the whole
                # read-modify-write, exactly as observe()/prune()/migrate() do.
                try:
                    with wm._store_lock():
                        with open(wm.WM, encoding="utf-8") as f:
                            lines = f.readlines()
                        wm._atomic_write(lines)
                    n += 1
                except wm._StoreBusy:
                    continue
            writer.passes = n

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        try:
            seen = set()
            t0 = time.time()
            while time.time() - t0 < 1.5:
                seen.add(len(wm._load()))
                time.sleep(0.002)
        finally:
            stop['v'] = True
            t.join(timeout=5)
        assert writer.passes > 0, 'writer never ran — test proved nothing'
        assert seen == {120}, (
            f'atomic write leaked a partial read: saw lengths {sorted(seen)}'
        )
    finally:
        wm.WM = old_wm
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)


def test_atomic_write_never_truncates_on_swap_failure():
    """A failed swap must leave the old store intact, never a truncated file.

    The pre-lock version fell back to `open(WM, "w")` when os.replace raised
    PermissionError — the exact truncate-first write the function exists to
    remove. Forcing every replace to fail must now leave the old bytes whole
    and report False.
    """
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    old_replace = os.replace
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        good = [json.dumps({'ts': 'x', 'schema_version': wm.SCHEMA_VERSION,
                            'kind': 'fact', 'cause': 'kept', 'effect': 'e',
                            'embedding': [0.0] * wm.DIM, 'embed_ok': True})]
        with wm._store_lock():
            assert wm._atomic_write(good) is True
        before = open(wm.WM, "rb").read()
        assert before, 'seed store must not be empty'

        def always_denied(src, dst):
            raise PermissionError("simulated: destination held open")

        os.replace = always_denied
        with wm._store_lock():
            ok = wm._atomic_write(['{"ts":"y","cause":"new","effect":"e"}'])
        os.replace = old_replace

        assert ok is False, 'a failed swap must report failure, not pretend success'
        assert open(wm.WM, "rb").read() == before, (
            'failed swap TRUNCATED the store — the removed fallback is back'
        )
        assert len(wm._load()) == 1
    finally:
        os.replace = old_replace
        wm.WM = old_wm
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)


def test_store_lock_reclaims_a_dead_holder():
    """A killed process must not wedge the store forever.

    Lock files are reclaimed when the owning PID is gone (or the lock is
    older than the stale budget), so one crashed cron cannot block every
    later writer.
    """
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        wm.WM = os.path.join(tmp, "wm.jsonl")
        lock = f"{wm.WM}.lock"
        # A PID that certainly is not alive: 0 is never a real holder.
        with open(lock, "w", encoding="utf-8") as f:
            f.write("0 0.0\n")
        assert os.path.exists(lock)
        t0 = time.time()
        with wm._store_lock(timeout=5):
            pass
        assert time.time() - t0 < 3, 'dead-holder lock was not reclaimed promptly'
        assert not os.path.exists(lock), 'lock must be released on exit'
    finally:
        wm.WM = old_wm
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)



def test_load_retries_when_file_reads_empty():
    """A non-empty file that parses to 0 edges must trigger one retry.

    That combination is always a torn read, never a real empty store, and
    reporting it upstream as 'no facts' is what made the failure silent.
    """
    tmp = tempfile.mkdtemp()
    old_wm = wm.WM
    try:
        p = os.path.join(tmp, "wm.jsonl")
        wm.WM = p
        wm._atomic_write([json.dumps({'ts': '1', 'schema_version': wm.SCHEMA_VERSION,
                                     'kind': 'fact', 'cause': 'c', 'effect': 'e',
                                     'embedding': [0.0] * wm.DIM, 'embed_ok': True})])
        assert len(wm._load()) == 1
        # an absent store is legitimately empty (no retry loop / no hang)
        wm.WM = os.path.join(tmp, 'missing.jsonl')
        assert wm._load() == []
    finally:
        wm.WM = old_wm
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)


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
