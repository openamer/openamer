#!/usr/bin/env python3
"""Regression tests for prediction validation (predict_validate.py).

The bug these guard against (found 12.09.2026): `validate_predictions()` asked
the world model "did this prediction come true?" WITHOUT excluding the
prediction itself from the search. An edge always has cosine 1.0 against its
own embedding, so every prediction found itself and scored "correct". Measured
live before the fix: 32/32 validatable predictions had themselves as their top
hit, the confidence file read `validated=1763, correct=784, wrong=0`, and no
run had ever recorded a miss.

Run:  python test_predict_validate.py
Hermetic: no Ollama, no real store — embeddings are stubbed deterministically
and every path is redirected into a temp dir.
"""
import json
import os
import shutil
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world_model as wm       # noqa: E402
import predict_validate as pv  # noqa: E402


# ---------------------------------------------------------------- test doubles

def _fake_embed(text, retries=2):
    """Deterministic bag-of-words embedding (64-dim, real maths, no Ollama).

    Same text -> identical vector (cosine 1.0). Different text -> low
    similarity. That is exactly the property the self-match bug depended on.
    """
    vec = [0.0] * 64
    for tok in str(text).lower().split():
        vec[hash(tok) % 64] += 1.0
    if not any(vec):
        vec[0] = 1.0
    return vec


def _iso(hours_ago):
    return (datetime.datetime.now() -
            datetime.timedelta(hours=hours_ago)).isoformat()


class Env:
    """Redirect world_model + predict_validate into a temp dir and stub embed."""

    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        self._wm, self._embed = wm.WM, wm.embed
        self._pv = (pv.WM, pv.T, pv.VALID_LOG, pv.CONFIDENCE_FILE, pv.SCORED_FILE)
        wm.WM = os.path.join(self.tmp, "world_model.jsonl")
        wm.embed = _fake_embed
        pv.WM = wm.WM
        pv.T = self.tmp
        pv.VALID_LOG = os.path.join(self.tmp, "prediction_validation.jsonl")
        pv.CONFIDENCE_FILE = os.path.join(self.tmp, "prediction_confidence.json")
        pv.SCORED_FILE = os.path.join(self.tmp, "prediction_scored.json")
        return self

    def __exit__(self, *exc):
        wm.WM, wm.embed = self._wm, self._embed
        (pv.WM, pv.T, pv.VALID_LOG, pv.CONFIDENCE_FILE, pv.SCORED_FILE) = self._pv
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False

    def write_edges(self, edges):
        with open(wm.WM, "w", encoding="utf-8") as f:
            for e in edges:
                e.setdefault("schema_version", wm.SCHEMA_VERSION)
                e.setdefault("kind", "fact")
                e["embedding"] = wm.embed(f"{e.get('cause','')} -> {e.get('effect','')}")
                e["embed_ok"] = True
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def conf(self):
        return json.load(open(pv.CONFIDENCE_FILE, encoding="utf-8"))


# --------------------------------------------------------------------- tests

def test_uncorroborated_prediction_is_not_a_win():
    """THE regression: a lone prediction must score 'unverified', not 'correct'.

    Before the fix this exact setup reported 'correct' — the prediction's only
    match was itself.
    """
    with Env() as env:
        env.write_edges([
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs", "effect": "expect: writes fail",
             "confidence": 0.6},
        ])
        summary = pv.validate_predictions()
        assert summary["status"] == "validated", summary
        assert summary["scored_this_run"] == 1, summary
        assert summary["results"][-1]["outcome"] == "unverified", summary["results"]
        assert env.conf()["correct"] == 0, "a self-match must never count as correct"
        assert env.conf()["validated"] == 1, env.conf()


def test_prediction_corroborated_by_an_independent_fact_is_a_win():
    """A real corroboration (separate edge, same content) still scores correct."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs",
             "effect": "expect: disk full writes fail",
             "confidence": 0.6},
            {"ts": _iso(4), "kind": "fact",
             "cause": "disk full", "effect": "writes fail"},
        ])
        summary = pv.validate_predictions()
        assert summary["results"][-1]["outcome"] == "correct", summary["results"]
        assert env.conf()["correct"] == 1, env.conf()


def test_recall_exclude_keeps_an_edge_out_of_its_own_results():
    """world_model.recall(exclude=...) must drop the named edge."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(2), "kind": "prediction",
             "cause": "If 'X' recurs", "effect": "expect Y"},
        ])
        edges = wm._load()
        key = wm.edge_key(edges[0])
        assert wm.recall("If 'X' recurs", k=3), "edge must be findable without exclude"
        assert wm.recall("If 'X' recurs", k=3, exclude={key}) == [], \
            "excluded edge must not be returned"


def test_recall_exclude_only_drops_the_named_edge():
    """Excluding one edge must not silently empty the whole result set."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(2), "kind": "fact", "cause": "alpha beta", "effect": "gamma"},
            {"ts": _iso(1), "kind": "fact", "cause": "alpha beta", "effect": "delta"},
        ])
        edges = wm._load()
        key = wm.edge_key(edges[0])
        hits = wm.recall("alpha beta", k=5, exclude={key})
        assert len(hits) == 1, f"expected the sibling edge, got {len(hits)}"


def test_a_prediction_is_scored_at_most_once():
    """Re-running the validator must not inflate the track record.

    Before the fix the counters were incremented for every prediction on every
    run: 46 distinct predictions produced 1763 'validated' observations.
    """
    with Env() as env:
        env.write_edges([
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs", "effect": "expect: writes fail"},
        ])
        pv.validate_predictions()
        first = env.conf()["validated"]
        summary2 = pv.validate_predictions()
        assert env.conf()["validated"] == first, "second run must not re-score"
        assert summary2["scored_this_run"] == 0, summary2


def test_recent_prediction_is_skipped_not_counted():
    """A prediction younger than 1h is not yet verifiable — skip, don't score."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(0.1), "kind": "prediction",
             "cause": "If 'brand new' recurs", "effect": "expect: unknown"},
        ])
        summary = pv.validate_predictions()
        assert summary["scored_this_run"] == 0, summary
        assert env.conf()["validated"] == 0, env.conf()


def test_antecedent_fact_does_not_confirm_the_prediction():
    """THE second regression: the premise the prediction was derived from is not proof.

    Live evidence (12.09.2026): after self-exclusion was added, 32/32
    predictions STILL matched — every one of them against the fact edge that
    had produced it ("If '<X>' recurs" matched the earlier <X>). A prediction
    is generated FROM an observed cause; matching that same cause back is
    tautological. Only an edge observed AFTER the prediction can confirm it.
    """
    with Env() as env:
        env.write_edges([
            # the premise, observed BEFORE the prediction
            {"ts": _iso(9), "kind": "fact",
             "cause": "disk full", "effect": "writes fail"},
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs",
             "effect": "expect: disk full writes fail",
             "confidence": 0.6},
        ])
        summary = pv.validate_predictions()
        assert summary["results"][-1]["outcome"] == "unverified", \
            f"the premise must not confirm the prediction: {summary['results']}"
        assert env.conf()["correct"] == 0, env.conf()


def test_a_later_fact_does_confirm_the_prediction():
    """The mirror case: the same fact AFTER the prediction IS corroboration."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(9), "kind": "fact",
             "cause": "disk full", "effect": "writes fail"},
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs",
             "effect": "expect: disk full writes fail",
             "confidence": 0.6},
            # recurrence, observed AFTER the prediction was written
            {"ts": _iso(2), "kind": "fact",
             "cause": "disk full", "effect": "writes fail"},
        ])
        summary = pv.validate_predictions()
        assert summary["results"][-1]["outcome"] == "correct", summary["results"]


def test_a_later_prediction_does_not_confirm_an_earlier_one():
    """Two overlapping predictions must not validate each other."""
    with Env() as env:
        env.write_edges([
            {"ts": _iso(5), "kind": "prediction",
             "cause": "If 'disk full' recurs", "effect": "expect: writes fail"},
            {"ts": _iso(2), "kind": "prediction",
             "cause": "If 'disk full' recurs", "effect": "expect: writes fail"},
        ])
        summary = pv.validate_predictions()
        assert all(r["outcome"] == "unverified" for r in summary["results"]), \
            summary["results"]


def test_malformed_timestamp_does_not_crash():
    with Env() as env:
        env.write_edges([
            {"ts": "not-a-date", "kind": "prediction",
             "cause": "If 'x' recurs", "effect": "expect y"},
        ])
        summary = pv.validate_predictions()
        assert summary["status"] == "validated", summary
        assert summary["scored_this_run"] == 0, summary


def test_predict_world_does_not_predict_from_a_prediction():
    """KTA must build its prediction from a FACT, never from the last prediction.

    Live evidence before the fix: the newest store entry was literally
    `If 'If 'Competitor update: ...' recurs' recurs`.
    """
    import knowledge_to_action as kta
    with Env():
        with open(wm.WM, "w", encoding="utf-8") as f:
            for e in [
                {"ts": _iso(9), "kind": "fact", "cause": "cpu hot", "effect": "throttle"},
                {"ts": _iso(8), "kind": "fact", "cause": "ram full", "effect": "swap"},
                {"ts": _iso(7), "kind": "fact", "cause": "disk full", "effect": "write fails"},
                {"ts": _iso(6), "kind": "prediction",
                 "cause": "If 'ram full' recurs", "effect": "expect: swap"},
            ]:
                e["schema_version"] = wm.SCHEMA_VERSION
                e["embedding"] = wm.embed(e["cause"])
                e["embed_ok"] = True
                f.write(json.dumps(e) + "\n")

        r = kta.experiment_predict_world()
        assert r.get("measurable") is True, r
        assert "If 'If " not in r["result"], f"nested prediction: {r['result']}"
        assert r["result"].startswith("If '"), r["result"]
        # and it must not have re-predicted a cause that already has one
        assert "ram full" not in r["result"], r["result"]


def test_predict_world_picks_a_fact_not_the_last_edge():
    """The source of a new prediction is a fact, even when a prediction is newest."""
    import knowledge_to_action as kta
    with Env():
        with open(wm.WM, "w", encoding="utf-8") as f:
            for e in [
                {"ts": _iso(9), "kind": "fact", "cause": "a one", "effect": "b one"},
                {"ts": _iso(8), "kind": "fact", "cause": "a two", "effect": "b two"},
                {"ts": _iso(7), "kind": "fact", "cause": "a three", "effect": "b three"},
            ]:
                e["schema_version"] = wm.SCHEMA_VERSION
                e["embedding"] = wm.embed(e["cause"])
                e["embed_ok"] = True
                f.write(json.dumps(e) + "\n")
        r = kta.experiment_predict_world()
        assert r["predicted_from"] == "a three", r   # newest FACT, not a prediction


def test_predict_world_refuses_when_effect_is_empty():
    """A prediction with no recorded effect carries no information."""
    import knowledge_to_action as kta
    with Env():
        with open(wm.WM, "w", encoding="utf-8") as f:
            for e in [
                {"ts": _iso(9), "kind": "fact", "cause": "a one", "effect": "b one"},
                {"ts": _iso(8), "kind": "fact", "cause": "a two", "effect": "b two"},
                {"ts": _iso(7), "kind": "fact", "cause": "a three", "effect": ""},
            ]:
                e["schema_version"] = wm.SCHEMA_VERSION
                e["embedding"] = wm.embed(e["cause"])
                e["embed_ok"] = True
                f.write(json.dumps(e) + "\n")
        r = kta.experiment_predict_world()
        assert r.get("measurable") is False, r


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
            import traceback
            print(f"  [ERROR] {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
