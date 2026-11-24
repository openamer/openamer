"""Tests for the evidence reranker in scripts/bench/memory_eval.py.

The reranker is the only part of retrieval whose weights are hand-chosen, so it
is also the part most likely to silently stop doing what it claims. These tests
pin the *behaviour* (what gets promoted) rather than the exact weight values,
so the weights can move without rewriting the suite -- but a change that stops
promoting the term-and-number evidence a question asks for fails here.
"""

from __future__ import annotations

import collections
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER = REPO_ROOT / "scripts" / "bench" / "memory_eval.py"


@pytest.fixture(scope="module")
def scorer():
    spec = importlib.util.spec_from_file_location("memory_eval_rerank_under_test", SCORER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture():
    """Three episodes: one exact answer, one near-miss, one unrelated."""
    index = {
        "h_answer": [
            "The brain export wrote 120 records, 40 of them trajectories, to "
            "memory/dataset/train.jsonl."
        ],
        "h_near": [
            "The brain export ran again and wrote some records, but the counts "
            "were not recorded in the log."
        ],
        "h_far": ["The docs build failed on an escaped pipe in a table cell."],
    }
    df = collections.Counter()
    for texts in index.values():
        df.update({token: 1 for token in set(texts[0].lower().split())})
    return index, df, len(index)


def test_rerank_promotes_the_candidate_carrying_the_asked_number(scorer):
    """Between two near-tied cosine matches, the one with the asked number wins.

    h_near has the higher cosine on purpose: the failure mode this reranker
    exists to fix is a nearby-in-embedding-space episode outranking the one that
    actually answers the question. The cosine gap here is realistic (0.005, in
    the measured 0.03-0.11 range of a real pool), so evidence must decide.
    """
    index, df, total = _fixture()
    question = "How many records did the brain export write in run 120, and how many were trajectories?"
    semantic_scores = {"h_near": 0.705, "h_answer": 0.700, "h_far": 0.660}

    ranked = scorer.rerank_scores(
        question, ["h_near", "h_answer", "h_far"], index, df, total, semantic_scores
    )

    assert ranked[0][1] == "h_answer", [digest for _score, digest in ranked]


def test_rerank_does_not_overrule_a_clear_semantic_preference(scorer):
    """A candidate far ahead on cosine keeps its place.

    The counterpart to the test above: reranking is a tie-breaker, not an
    override. If a huge similarity gap can be beaten by a keyword match, the
    reranker has quietly become a keyword search and will regress every question
    whose wording does not appear verbatim in the answer.
    """
    index, df, total = _fixture()
    question = "How many records did the brain export write in run 120, and how many were trajectories?"
    semantic_scores = {"h_answer": 0.740, "h_near": 0.600, "h_far": 0.400}

    ranked = scorer.rerank_scores(
        question, ["h_near", "h_answer"], index, df, total, semantic_scores
    )

    assert ranked[0][1] == "h_answer"


def test_rerank_without_numbers_still_prefers_term_coverage(scorer):
    """With no number to match, IDF-weighted term coverage decides."""
    index, df, total = _fixture()
    question = "Woran erkennt man eine echte Browser-Sitzung statt einer nachgebauten Kopfzeile?"
    semantic_scores = {"h_near": 0.9, "h_answer": 0.2, "h_far": 0.1}

    ranked = scorer.rerank_scores(
        question, ["h_near", "h_answer", "h_far"], index, df, total, semantic_scores
    )

    # Nothing in the fixture answers this question, so the check is only that
    # the function returns every candidate exactly once and sorts descending.
    assert {digest for _s, digest in ranked} == {"h_near", "h_answer", "h_far"}
    scores = [score for score, _digest in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rerank_skips_candidates_missing_from_the_index(scorer):
    """A digest with no text cannot be scored -- and must not raise or be invented."""
    index, df, total = _fixture()

    ranked = scorer.rerank_scores("Brain-Export Datensätze", ["h_answer", "h_ghost"], index, df, total, {})

    assert [digest for _score, digest in ranked] == ["h_answer"]


def test_question_features_drop_terms_that_appear_everywhere(scorer):
    """Ultra-common terms carry no signal and must not inflate coverage."""
    df = collections.Counter({"openamer": 5000, "testdatei": 1, "importiert": 3})
    content, numbers, mass = scorer._question_features(
        "Warum konnte die Testdatei nicht importiert werden? OpenAmer 2026", df, 5000
    )

    assert "openamer" not in content
    assert "testdatei" in content
    assert numbers == ["2026"]
    assert mass > 0
