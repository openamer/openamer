"""The two buffer gates must agree at the WRITE DECISION.

Regression test for root cause 142 (22.09.26), measured live: of 600 audited
`reason="junk"` rows in `buffer_junk.jsonl`, 368 (61%) were SILENT DROPS --
`internet_learner._is_junk()` judged the text learnable, `store()` then called
`buffer_store.is_junk()` and refused it, and the cycle could only report the
generic "rejected, not trained". That silent disagreement is the bulk of the
learner's 57% rejection rate.

Contract pinned here:
  1. The write decision consults the WRITER, not a hand-kept subset.
  2. The two gates may differ in strictness (that is intentional -- see the
     pitfall below), so the disagreement must be AUDITED, not silent.
  3. `active_learn` never buffers a reasoning trace and never reports a refused
     write as a success.

PITFALL pinned by test: folding the writer into `_is_junk()` regresses this
module's own contract -- `_clean_insight()` calls `_is_junk()`, so the extractor
would eat prose that merely MENTIONS a plan or an ad-wall (4 gate tests failed
when that was tried on 22.09.26). Keep them separate.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    # ty: spec_from_file_location returns ModuleSpec | None and its .loader is
    # Loader | None. The repo-wide importlib idiom skips the guard and ty
    # reports 3 diagnostics per file for it; this module is new code, so it
    # carries the guard rather than adding to that backlog.
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name!r} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


IL = _load("internet_learner", TRAINING / "internet_learner.py")
BS = _load("buffer_store", TRAINING / "buffer_store.py")
AL = _load("active_learn", TRAINING / "active_learn.py")


# --- the three leak families the extractor used to accept -------------------
# Dated SERP title + snippet (writer: _is_serp_snippet) -- 222 rows live.
_DATED_SERP = (
    "Transformers v2 Zero-to-Hero: Master Faster Inference … — 4. Jan. 2026 · "
    "This concise tutorial covers everything developers need: core differences, "
    "new features, and the migration path."
)
# The learner's own reasoning trace (writer: _JUNK_MARKERS 'self-critique') -- 109 rows.
_TRACE_ANSWER = (
    "Safety requires preserving alignment, control, and value stability across "
    "self-modifications.\n\nSelf-critique: Need maybe mention answer is broadly "
    "accurate but incomplete."
)
# Page chrome the extractor's 40+ single-class detectors miss (writer: _is_nav_chrome) -- 88 rows.
_NAV_CHROME = (
    "The extractor must never store an ad-wall notice; a row telling the reader "
    "to switch off the ad blocker and subscribe is page furniture, not an insight."
)


def test_writer_gate_refuses_agrees_with_the_writer_on_every_leak_family():
    """The new predicate must mirror buffer_store.is_junk exactly."""
    for leak in (_DATED_SERP, _TRACE_ANSWER, _NAV_CHROME):
        assert BS.is_junk(leak), leak
        assert IL._writer_gate_refuses(leak), leak


def test_writer_gate_refuses_is_not_the_bare_extractor_rule():
    """At least one family proves the two gates really differ.

    If this ever stops holding, the extractor gate has been made as eager as the
    writer -- which is the regression the pitfall warns about.
    """
    differing = [t for t in (_DATED_SERP, _TRACE_ANSWER, _NAV_CHROME)
                 if not IL._is_junk(t) and IL._writer_gate_refuses(t)]
    assert differing, "no family distinguishes the extractor gate from the writer gate"


def test_store_decision_consults_the_writer():
    """store() must ask the writer, so a refusal is explicit, not a lost write."""
    src = (TRAINING / "internet_learner.py").read_text(encoding="utf-8")
    assert "_writer_gate_refuses(cleaned)" in src, \
        "store() no longer consults the writer gate at its write decision"
    assert '"writer-gate"' in src, \
        "refusals are no longer audited under their own reason"


def test_extractor_still_keeps_prose_that_merely_mentions_a_plan_or_adwall():
    """The pitfall, pinned: the extractor must NOT inherit the writer's strictness.

    Folding `buffer_store.is_junk` into `_is_junk` made these return True and
    regressed 4 tests in test_internet_learner_gate.py.
    """
    prose = [
        _NAV_CHROME,   # a sentence ABOUT an ad-wall notice is not an ad-wall notice
        "We need to identify the most relevant failure mode when a cron job dies "
        "mid-run, because silent failures accumulate without alerting.",
    ]
    for p in prose:
        assert not IL._is_junk(p), p


def test_clean_insight_still_passes_that_prose():
    """`_clean_insight` depends on the looseness the pitfall protects."""
    for p in ("The extractor must never store an ad-wall notice; a row telling "
              "the reader to switch off the ad blocker and subscribe is page "
              "furniture, not an insight.",):
        assert IL._clean_insight(p) != "", p


# --- active_learn: never buffer a trace, never lie about a refused write ----

def test_strip_reasoning_trace_removes_the_self_critique_tail():
    clean = AL._strip_reasoning_trace(_TRACE_ANSWER)
    assert "Self-critique" not in clean
    assert clean == ("Safety requires preserving alignment, control, and value "
                     "stability across self-modifications.")
    assert not BS.is_junk(clean), "the stripped answer must be trainable"


def test_strip_reasoning_trace_keeps_clean_prose_untouched():
    clean = "Quantization reduces model size by mapping weights to lower precision."
    assert AL._strip_reasoning_trace(clean) == clean


def test_store_if_trainable_refuses_what_the_writer_refuses():
    """It must return False (not silently no-op) on junk, and never claim a write."""
    assert AL.store_if_trainable("q", _TRACE_ANSWER) is False


def test_store_if_trainable_accepts_and_grows_the_buffer(tmp_path):
    """A genuinely trainable row really lands (real append, presence verified)."""
    buf = tmp_path / "buffer.jsonl"
    AL.BUFFER = str(buf)
    ok = AL.store_if_trainable(
        "What is quantization?",
        "Quantization maps weights to lower precision, cutting model size 4x "
        "with minimal accuracy loss.",
    )
    assert ok is True
    lines = [l for l in buf.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
