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


def test_every_learning_cycle_reports_a_rejection_honestly():
    src = (TRAINING / "internet_learner.py").read_text(encoding="utf-8")
    assert src.count("if not store(") == 8, "all 8 cycles must gate their write"
    assert "rejected, not trained" in src
