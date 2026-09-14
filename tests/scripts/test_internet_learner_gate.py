"""Tests for the internet learner's learning-quality gates (scripts/training).

Hermetic: no network, no LLM, no real training buffer. We pin the contract that
keeps page furniture out of the LoRA training set — the failure mode is
concrete and was observed live (all four rows below really were "learned"):

  docs cycle       -> "Jetzt spenden Benutzerkonto erstellen Anmelden ..."  (DE wiki chrome)
  competitor cycle -> "Unsere Werbepartner Einkaufen Ferienwohnungen ..."  (DE ad chrome)
  competitor cycle -> "Pomysly na rodzinne spotkania ... Przepisy Porady"  (PL ad chrome)
  github cycle     -> "With GitHub, developers, agents, and code come together ..."

A cycle that finds nothing must report "rejected, not trained" rather than
store chrome, so `store()` returns False and the caller can be honest.
"""
import importlib.util
import sys
from pathlib import Path
import json
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))

_spec = importlib.util.spec_from_file_location(
    "internet_learner", TRAINING / "internet_learner.py"
)
IL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IL)

CHROME = [
    "Jetzt spenden Benutzerkonto erstellen Anmelden Meine Werkzeuge",
    "Unsere Werbepartner Einkaufen Ferienwohnungen Freizeit und Reise",
    "Pomysły na rodzinne spotkania Dania na grilla Inspiracje Kuchnia Przepisy Porady",
    "With GitHub, developers, agents, and code come together on one platform.",
    "You switched accounts on another tab or window.",
    "View all docs AWS Trainium &amp; Inferentia",
    # HuggingFace docs sidebar (live 14.09.26): 200 chars of product labels, so
    # it passed the >=90 "long prose" trust until the nav signature was added.
    "Inference Providers Kernels LeRobot Leaderboards Lighteval Microsoft Azure "
    "OpenEnv Optimum PEFT Reachy Mini Safetensors Sentence Transformers TRL Tasks "
    "Text Embeddings Inference Text Generation Inference Tokenizers Trackio "
    "Transformers Transformers.",
    # Leaked LLM instruction template (live 14.09.26): the multi-domain cycle
    # stored the 2B model's own extraction scaffolding verbatim.
    "\"\n\n2.  **Identify the Core Task:**\n   - Extract ONE technical insight "
    "from the provided text.\n   - Format it as a single sentence.\n   - Must "
    "start with \"[INSIGHT]\".\n   - No preamble before the insight.\n   - "
    "Target audience: autonomous AI agent.\n\n3.",
    # German/marketplace ad CTA (live 14.09.26): the multi-domain cycle stored
    # this exact CTA copy (Advolux + a Udemy-style course ad), 300 chars long so
    # it cleared the >=90 "long prose" trust.
    "Legal-Tech-Software - Kanzleimanagement mit Advolux — Advolux, die optimale "
    "Anwaltssoftware für moderne Kanzleiarbeit. Jetzt kostenlos testen. Mit Advolux "
    "arbeiten Sie besser, schneller und entspannter in; AI Law Course - AI for Legal "
    "Professionals — Find the right instructor for you. Choose from ma",
    # vendor first-person boilerplate (live 14.09.26): the efficiency cycle
    # stored this exact SSL-compliance chrome — the bare digit 256 satisfied the
    # technical-signal gate, so the junk gate keys on the vendor voice instead.
    "Bit-TLS-Verschlüsselung Für die sichere Datenübertragung nutzen wir 256-Bit-TLS-",
]

# Link-shrapnel with no junk keyword and no sentence shape: caught by the
# "short candidate needs a technical signal" rule in _clean_insight (the
# multi-domain cycle distilled exactly this string from a PDF landing page).
SHORT_FURNITURE = [
    "Download PDF Download PDF Review Article Open access Publish",
    # a search "title" that is really a URL: the bare digits of %20 satisfied the
    # technical-signal gate until the candidate was decoded first
    "Which%20Programming%20Language%20used%20behind%20Microsoft%20Edge%20Browser%20.",
]

REAL = [
    "vLLM PagedAttention raises serving throughput about 24x over naive HF generation.",
    "PEFT LoRA reduces trainable parameters to under 1% of the base model at int4.",
    "Continuous batching lets a serving engine process many prompts per GPU step, "
    "which cuts cost per token substantially for high-traffic agent workloads.",
    # the vendor-voice pattern must key on first-person boilerplate, never on the
    # topic — a genuine TLS/encryption insight still has to survive
    "TLS 1.3 removes a round trip from the handshake; session resumption cuts "
    "per-connection CPU cost.",
]


def test_chrome_is_rejected_as_junk():
    for text in CHROME:
        assert IL._is_junk(text), text


def test_real_insights_survive_the_junk_gate():
    for text in REAL:
        assert not IL._is_junk(text), text


def test_clean_insight_drops_short_chrome_and_keeps_prose():
    for text in CHROME + SHORT_FURNITURE:
        assert IL._clean_insight(text) == "", text
    assert IL._clean_insight(REAL[0])
    assert IL._clean_insight(REAL[2])


def test_store_refuses_chrome_and_writes_real_insights(tmp_path):
    buf = tmp_path / "buf.jsonl"
    import buffer_store  # imported lazily by store()

    with patch.object(buffer_store, "_audit", lambda *a, **k: None):
        for text in CHROME:
            assert IL.store("q", text, buffer=buf) is False, text
        assert IL.store("q", REAL[0], buffer=buf) is True
    lines = [ln for ln in buf.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, "only the real insight may reach the training buffer"
    assert REAL[0][:40] in lines[0]


def test_clean_insight_decodes_percent_escapes_before_judging():
    """Percent-escapes must be decoded, not judged raw (digits fake a signal)."""
    assert IL._clean_insight("LoRA%20adapters%20cut%20VRAM%20by%2040%25%20at%20int4.") \
        == "LoRA adapters cut VRAM by 40% at int4."



class _Resp:
    """urlopen() stand-in: .read() hands back the JSON we seeded."""

    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b


def test_headline_prefers_real_articles_and_refuses_self_posts():
    """Show/Ask HN landing pages are ad copy, never a seed for a cycle.

    Live 15.09.26: cycle_c_github took "Show HN: A murder mystery game built on
    an open-source gen-AI agent framework", deep-read the product page and was
    gated — the whole cycle wasted. "" must hand over to the LLM query instead.
    """
    only_self = [{"title": "Show HN: A murder mystery game built on an open-source gen-AI agent framework"},
                 {"title": "Ask HN: who is hiring agent engineers right now"}]
    with patch.object(IL.urllib.request, "urlopen", lambda *a, **k: _Resp({"hits": only_self})):
        assert IL._fresh_headline("AI agent framework", []) == ""

    with_article = [{"title": "Show HN: my agent framework, please star it"},
                    {"title": "A practical guide to agent memory architectures with benchmarks"}]
    with patch.object(IL.urllib.request, "urlopen", lambda *a, **k: _Resp({"hits": with_article})):
        assert IL._fresh_headline("AI agent", []).startswith("A practical guide")


def test_store_or_deep_retries_the_read_with_a_wider_k():
    """A page with no qualifying sentence must not waste the cycle: retry k=6.

    Live 15.09.26: cycle_e/cycle_g logged "rejected, not trained" every other
    run because the first pass (k=2) found nothing storable.
    """
    ks, good = [], "vLLM 0.9 adds disaggregated prefill and 2x throughput."
    with patch.object(IL, "store", lambda u, i: i == good),          patch.object(IL, "deep_learn", lambda q, k=2: (ks.append(k), good if k == 6 else "")[1]):
        assert IL.store_or_deep("u", "q", "") == good
    assert ks == [2, 6], f"expected k=2 then k=6, got {ks}"

def test_every_learning_cycle_gates_its_write_and_reports_honestly():
    """Invariant, not a snapshot: one gate call and one honest rejection path per
    cycle. The gate helper's concrete name is an implementation detail, so key
    the assertion on the number of cycles rather than a literal call shape — a
    change-detector on `if not store(` broke when the cycles switched to
    store_or_deep() (14.09.26)."""
    src = (TRAINING / "internet_learner.py").read_text(encoding="utf-8")
    cycles = src.count("\ndef cycle_")
    assert cycles == 8, f"expected 8 cycles, found {cycles}"
    assert src.count("store_or_deep(") - 1 == cycles, \
        "every cycle must route its write through the gate helper"
    assert src.count('return "rejected, not trained') == cycles, \
        "every cycle must report a rejection honestly when both reads are gated"
