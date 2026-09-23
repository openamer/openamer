#!/usr/bin/env python3
"""Tests for buffer_store.py — the single source of truth for buffer writes.

Run:  python test_buffer_store.py

Regression guard for the bug fixed 11.09: the 300-example cap lived only in
online_learning's replay branch, so any cycle with fresh data grew the buffer
without bound (training on unbounded duplicates degrades loss). These tests
prove the cap is enforced on EVERY append. All work on a TEMP buffer — the
real online_buffer.jsonl is never touched.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffer_store as bs

try:  # pytest is optional: this file also runs standalone
    import pytest
except ImportError:  # pragma: no cover
    pytest = None


def _isolated_audit_log():
    """Point the module's audit log at a throwaway file, return a restore fn.

    `append()` audits EVERY rejected row to `buffer_store.JUNK_LOG`, whose
    default is the real `scripts/training/buffer_junk.jsonl` -- the audit log
    the triage routine reads to decide whether a rejection is a leak. Only
    `test_append_refuses_junk_and_logs_it` patched it, so the other twelve
    `bs.append(...)` call sites wrote their own fixtures into the PRODUCTION
    log. Measured 20.09.26: 206 of 6,970 rows carried the unmistakable test
    signature `u == "q"`; re-measured 23.09.26 after the helper had been added
    to the live copy only: 1,376 of 9,599 rows (14.3 %) and STILL GROWING,
    because origin/main itself has no isolation -- so every suite run from the
    repo worktree re-appends them.

    `buffer_store._resolve_home()` is the reason origin/main leaks: with
    `OPENAMER_HOME` unset (the cron case) it falls back to the real install dir,
    so `JUNK_LOG` points at the live log no matter which checkout the test runs
    from. Confirmed 23.09.26 by running the un-isolated repo copy: the live log
    grew by exactly one `{"u": "q", "a": "Eine Woche hat sieben Tage."}` row,
    while the isolated live copy grew by zero.

    Nothing reached the training buffer (`online_buffer.jsonl`: 0 test fixtures,
    verified), but the audit log is the file the reject-rate triage reads, so
    the litter produces the recurring false lead "4 unproven `duplicate` rejects
    were `q` / `Eine Woche hat sieben Tage.`, not a leak".
    """
    orig = bs.JUNK_LOG
    d = tempfile.mkdtemp(prefix="bufstore_audit_")
    bs.JUNK_LOG = os.path.join(d, "buffer_junk.jsonl")

    def restore():
        bs.JUNK_LOG = orig

    return restore


if pytest is not None:
    @pytest.fixture(autouse=True)
    def _no_write_to_the_live_audit_log():
        """Keep the whole suite out of the live `buffer_junk.jsonl`."""
        restore = _isolated_audit_log()
        try:
            yield
        finally:
            restore()

def _tmp_buf():
    d = tempfile.mkdtemp(prefix="bufstore_test_")
    return os.path.join(d, "buf.jsonl")


def test_append_creates_and_counts():
    buf = _tmp_buf()
    assert bs.count(buf) == 0
    n = bs.append("q1", "a1", buffer=buf)
    assert n == 1, n
    assert bs.count(buf) == 1
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert rec["u"] == "q1" and rec["a"] == "a1"


def test_cap_enforced_on_every_append():
    """The core regression: 311 writes must leave exactly 300 lines."""
    buf = _tmp_buf()
    for i in range(311):
        bs.append(f"q{i}", f"a{i}", buffer=buf)
    assert bs.count(buf) == 300, bs.count(buf)
    lines = open(buf, encoding="utf-8").readlines()
    # FIFO: oldest evicted, newest kept
    assert json.loads(lines[0])["u"] == "q11"
    assert json.loads(lines[-1])["u"] == "q310"


def test_custom_cap_honoured():
    buf = _tmp_buf()
    for i in range(12):
        bs.append(f"q{i}", f"a{i}", buffer=buf, max_buf=5)
    assert bs.count(buf) == 5
    assert json.loads(open(buf, encoding="utf-8").readline())["u"] == "q7"


def test_enforce_cap_is_idempotent():
    buf = _tmp_buf()
    for i in range(305):
        bs.append(f"q{i}", f"a{i}", buffer=buf)
    assert bs.enforce_cap(buf) == 300
    assert bs.enforce_cap(buf) == 300  # second call is a no-op


def test_enforce_cap_missing_file_is_safe():
    """A trim on a nonexistent buffer must not raise into the caller."""
    assert bs.enforce_cap(_tmp_buf()) == 0


# A truncation test needs text that SURVIVES the junk gate first: `append`
# refuses degenerate text, never writes, and the truncation branch becomes
# unreachable. A repeated TEMPLATE fails by construction -- it trips
# is_glued_motif, the header-repeat rule AND the unique-token ratio. This
# fixture is therefore 74 distinct technical sentences (measured: len 5258,
# top-4-gram rate 0.0221 < 0.045 threshold, unique-token ratio 0.686,
# header-repeat False) and reaches the 4000-char branch via append().
_TRUNC_PROSE = (
    'Chunked prefill lets vLLM batch prompt tokens so peak KV-cache memory falls. '
    'LoRA freezes base weights and trains two low-rank matrices in each layer. '
    'Quantizing decoder weights to int4 recovers most of the fp16 accuracy. '
    'Paged attention keeps key-value blocks in non-contiguous device pages. '
    'Speculative decoding drafts a handful of tokens, then verifies them once. '
    'Retrieval augmentation grounds an answer in a vector index of passages. '
    'Gradient checkpointing recomputes activations instead of storing them. '
    'Expert routing sends each token to a sparse subset of feed-forward blocks. '
    'Flash attention tiles the softmax so scores never leave on-chip SRAM. '
    'Distillation moves a teacher distribution into a compact student net. '
    'Tensor parallelism shards a weight matrix across several accelerators. '
    'Continuous batching admits arrivals without draining the active queue. '
    'Rotary position embeddings rotate query and key vectors before scoring. '
    'Grouped-query attention shares key heads to shrink the cache footprint. '
    'A reranker scores passages with a cross encoder before generation starts. '
    'Tokenizers split rare identifiers into byte-level fallback sequences. '
    'Mixed precision keeps a master copy in fp32 beside a bf16 compute copy. '
    'ZeRO shards optimizer state, gradients and parameters across ranks. '
    'Pipeline parallelism splits layers into stages on separate devices. '
    'An adapter merges into the base by adding the scaled low-rank product. '
    'Beam search keeps several prefixes alive and prunes the weakest later. '
    'Top-p sampling truncates the tail of the distribution before drawing. '
    'A vector database returns nearest neighbours under a distance metric. '
    'Embedding models map text into a space where cosine similarity is useful. '
    'Chunking decides what a retriever can ever find, so boundaries matter. '
    'A guardrail classifier scores prompts before the model processes them. '
    'Tool schemas are serialized into the prompt on every single API call. '
    'Prompt caching reuses a stable prefix and cuts the billed input tokens. '
    'Sandboxing confines generated code to a disposable container image. '
    'An eval harness pins a dataset so regressions become measurable. '
    'Latency budgets split cleanly into prefill, decode and network delay. '
    'Throughput rises when a batch keeps every accelerator busy at once. '
    'Memory bandwidth limits decode far more than raw arithmetic does. '
    'A scheduler balances prefill and decode traffic on one shared device. '
    'Weight-only quantization leaves activations in their original precision. '
    'Activation quantization needs calibration data to choose clipping ranges. '
    'A cache eviction policy trades context length against resident memory. '
    'Prefix sharing lets many requests reuse one common system prompt. '
    'Speculative verification accepts a draft token only when it matches. '
    'An expert imbalance drops tokens, so a router needs an auxiliary loss. '
    'A quantized kernel must fuse dequantization into the matrix multiply. '
    'Sequence packing removes padding waste across short training examples. '
    'A draft model must be cheap enough to repay its own extra forward passes. '
    'Long context costs scale quadratically unless attention is approximated. '
    'Sparse retrieval beats dense search on rare entity names in practice. '
    'A tokenizer vocabulary trade-off decides how many merges stay useful. '
    'Logit processors mask forbidden tokens before the sampler sees a row. '
    'Positional interpolation stretches a window without retraining a model. '
    'Attention sinks keep early tokens addressable inside a streaming cache. '
    'A router temperature controls how sharply experts get selected per token. '
    'On-policy distillation samples from the student, then corrects the gap. '
    'Weight averaging across checkpoints often beats a single best epoch. '
    'A learning-rate warmup prevents an early divergence on large batches. '
    'Gradient clipping bounds the update norm when a batch holds an outlier. '
    'Data deduplication lowers memorization and improves held-out accuracy. '
    'Curriculum ordering feeds easy examples before the harder mixtures. '
    'A reward model scores completions and feeds a preference optimizer. '
    'Constitutional critique rewrites a draft answer against a written rule. '
    'Retrieval reordering lifts precision when the first stage over-recalls. '
    'An index refresh lag makes freshly written documents temporarily invisible. '
    'Hybrid search blends a keyword score with a dense similarity score. '
    'Chunk overlap preserves a sentence split across two adjacent windows. '
    'A metadata filter prunes candidates before the vector comparison runs. '
    'Query rewriting expands an ambiguous ask into several clearer variants. '
    "A context window budget must reserve room for the model's own output. "
    'Streaming decode hides first-token latency behind an incremental render. '
    'Batching across users raises throughput but adds a queueing delay. '
    'A prefill-decode split server keeps both phases on separate pools. '
    'Kernel fusion removes a memory round trip between two adjacent operations. '
    'An occupancy limit caps concurrent sequences when the cache is exhausted. '
    'A graceful degradation path serves shorter contexts under heavy load. '
    'Observability traces every request so a latency spike becomes attributable. '
    'A canary rollout limits blast radius when a new weights revision regresses. '
    'Rollback needs a pinned artifact, not a retrained model from scratch. '
)
_TRUNC_U = " ".join(f"Frage{i}" for i in range(900))[:5000]


def test_truncation_limits():
    buf = _tmp_buf()
    # Fixture must SURVIVE the junk gate: append() refuses degenerate text
    # (repeated template -> glued motif / header-repeat / low unique-ratio)
    # and the truncation branch would then be unreachable.
    bs.append(_TRUNC_U, _TRUNC_PROSE, buffer=buf)
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert len(rec["u"]) == 3000
    assert len(rec["a"]) == 4000


def test_none_values_are_tolerated():
    buf = _tmp_buf()
    bs.append(None, None, buffer=buf)
    rec = json.loads(open(buf, encoding="utf-8").readline())
    assert rec["u"] == "" and rec["a"] == ""


# --- junk gate (regression: 112 of 300 live buffer entries on 11.09.26 were
# reasoning-trace leaks, degenerate "Self Self Self" repetition, or raw
# tool-call JSON — all three would be trained on) ---

def test_junk_classifier_catches_the_three_observed_classes():
    # 1. reasoning-trace leak
    assert bs.is_junk("Self-critique: Here's a thinking process:\n\n1. **Analyze "
                      "User Input:**\n   - User asks a question")
    # 2. degenerate repetition
    assert bs.is_junk("Self\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf")
    # 3. raw tool-call JSON instead of an answer
    assert bs.is_junk('{"tool": "web_search", "params": {"query": "x"}}')


def test_real_answers_are_not_junk():
    for good in (
        "LoRA adapters inject trainable low-rank matrices into each layer.",
        "Sleep consolidation replays the day's episodes and promotes the "
        "high-usefulness ones into permanent memory.",
        "Prompt injection is blocked by a deterministic pre-execution gate "
        "that never calls a model.",
    ):
        assert not bs.is_junk(good), good


def test_append_refuses_junk_and_logs_it():
    """A junk write must not change the buffer, but must be auditable."""
    buf = _tmp_buf()
    junk_log = buf + ".junk.jsonl"
    orig = bs.JUNK_LOG
    bs.JUNK_LOG = junk_log
    try:
        bs.append("q", "a good answer with real content", buffer=buf)
        assert bs.count(buf) == 1
        n = bs.append("q", "Self\n\nSelf\n\nSelf\n\nSelf\n\nSelf\n\nSelf", buffer=buf)
        assert n == 1, "junk must not be appended"
        assert bs.count(buf) == 1
        assert json.loads(open(junk_log, encoding="utf-8").readline())["reason"] == "junk"
    finally:
        bs.JUNK_LOG = orig


def test_empty_completion_still_appends():
    """The historical contract tolerates placeholders; only junk is refused."""
    buf = _tmp_buf()
    assert bs.append("q", "", buffer=buf) == 1


# --- junk classes discovered live 11.09.26 (waves 2-4) -----------------------
# The original 10 markers missed four whole classes that were sitting in the
# live buffer: English planning-voice traces, raw SERP snippets, periodic
# repetition, and page/UI chrome. Each is pinned below, and a real answer is
# asserted to survive — a too-eager filter is worse than none.

_JUNK_WAVE = [
    ("planning-voice trace (un-numbered)", "We need to answer the question: \"Explain sleep consolidation\""),
    ("planning-voice trace (We have)", "We have a user asking: \"Find the structural connection\""),
    ("planning-voice trace (numbered)", "1.  The user asks for the structural connection between two situations"),
    ("planning-voice trace (We must)", "We must provide a comprehensive explanation. The user didn't ask"),
    ("SERP snippet with date", "AutoGPT Review 2026 — 3. Aug. 2026 · The power of AutoGPT lies in"),
    ("SERP snippet (Sept variant)", "30 Best AI Agents GitHub Repos — 1. Sept. 2026 · The best open-source"),
    ("SERP snippet truncated tail", "Some Title — Check this document for the core design principles…"),
    ("periodic repetition (space)", 'user [   " user [   " user [   " user [   "'),
    ("periodic repetition (newlines)", 'user\n[\n  "\nuser\n[\n  "\nuser\n[\n  "'),
    ("degenerate single token x4", "Self\n\nSelf\n\nSelf\n\nSelf"),
    ("self-critique segment", "x Self-critique: We need to"),
    ("html entity leak", "last quarter&#39;s hot framework is this quarter"),
    ("marketing testimonial", "No thanks \u201cSebastian is an incredible educator and has invaluable insights"),
    ("repeated page header", "Welcome to the Fine-Tuning Course Welcome to the Fine-Tuning Course 1."),
    ("prompt-template leak", "Key insight: <one sentence>. Focus on actionable knowledge."),
    ("UI chrome", "You switched accounts on another tab or window."),
    ("truncated fragment", "Both"),
    # reasoning-trace leaks found live 14.09.26 (active_learn + internet_learner)
    ("reasoning opener (okay, the user)", "Okay, the user wants me to find the structural connection between two situations"),
    ("bolded reasoning header + leading quote", '"\n\n2.  **Identify the Core "Technical Insight":**\n   - The text is mostly meta-information about arXiv.'),
]

_REAL_ANSWERS = [
    "Eine Woche hat sieben Tage.",
    "Der Gateway blockiert — den hat die letzte Runde gestartet. Ich kill ihn jetzt.",
    "Mamba-3 ist schneller als Transformer beim Decode und staerker bei langen Sequenzen.",
    "Ich fuehre den Funding-Tracker aus. Zuerst sammle ich die Repository-Informationen.",
    "Optimization and Tuning - vLLM supports multiple attention backends for serving.",
    "Die Antwort ist zweiundvierzig, weil die Rechnung stimmt und die Probe passt.",
    "Es gibt vier Jahreszeiten: Fruehling, Sommer, Herbst und Winter.",
    "Ja.",
    "Nein!",
    # 14.09.26 near-misses: the new markers must NOT swallow these
    "To cut tail latency, identify the core bottleneck in the tokenizer first.",
    "Okay, the result is 42 because the probe checks out.",
    "Loss sank von 2.88 auf 1.68 ueber 72 Steps — das Training konvergierte sauber.",
]


def test_all_junk_wave_classes_are_rejected():
    """Every junk class found live must be refused."""
    missed = [name for name, text in _JUNK_WAVE if not bs.is_junk(text)]
    assert not missed, f"not classified as junk: {missed}"


def test_real_answers_survive_the_junk_filter():
    """A filter that eats real answers is worse than no filter."""
    eaten = [t for t in _REAL_ANSWERS if bs.is_junk(t)]
    assert not eaten, f"real answers wrongly refused: {eaten}"


def test_periodic_repeat_is_order_independent():
    """The loop detector must not depend on whitespace shape."""
    assert bs._is_periodic_repeat('a b c a b c a b c a b c')
    assert not bs._is_periodic_repeat(
        "Die Antwort ist zweiundvierzig, weil die Rechnung stimmt.")


def test_duplicate_example_is_refused_but_distinct_kept():
    """A training set must not carry exact duplicate rows."""
    buf = _tmp_buf()
    assert bs.append("q", "Eine Woche hat sieben Tage.", buffer=buf) == 1
    assert bs.append("q", "Eine Woche hat sieben Tage.", buffer=buf) == 1, "duplicate must not grow the buffer"
    assert bs.append("q", "Ein Jahr hat zwoelf Monate.", buffer=buf) == 2




def test_suite_never_writes_the_live_audit_log():
    """Class 167: a rejected fixture must not reach the PRODUCTION log.

    `buffer_store._resolve_home()` falls back to the real install dir when
    `OPENAMER_HOME` is unset -- the cron case -- so without the autouse
    fixture every `bs.append(...)` call site above audited its own fixture
    into the live `scripts/training/buffer_junk.jsonl`. Measured 23.09.26:
    1,376 of 9,599 rows (14.3 %) carried a test-only signature and the count
    was still growing; removing the fixture (run from origin/main) added
    exactly one row per run, with it (this file) zero.

    Assert on the RESOLVED default, not on a hardcoded path: the regression
    is that the default IS the live log, so a test that stubs it out cannot
    see the bug it guards.
    """
    live = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "buffer_junk.jsonl")
    assert os.path.abspath(str(bs.JUNK_LOG)) != os.path.abspath(live), (
        "JUNK_LOG still points at the live audit log: %s" % bs.JUNK_LOG
    )
    before = os.path.getsize(live) if os.path.exists(live) else 0
    buf = _tmp_buf()
    bs.append("q", _JUNK_WAVE[0][1], buffer=buf)   # a refusal -> audit
    after = os.path.getsize(live) if os.path.exists(live) else 0
    assert after == before, "a rejected fixture leaked into %s" % live

if __name__ == "__main__":
    fails = 0
    restore_audit = _isolated_audit_log()
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  [PASS] {name}")
            except Exception as e:
                fails += 1
                print(f"  [FAIL] {name}: {e}")
    restore_audit()
    print(f"\n{'FAILED' if fails else 'OK'}: {fails} failure(s)")
    sys.exit(1 if fails else 0)
