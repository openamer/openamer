"""The runner's VERDICT must key on the leak finding, never on `acc`.

The pinned suite (test_self_learning_label_leak.py) covers the gate
(`leak_findings`). It did not cover the verdict that consumes it, so the
22.09.26 bug — gate fires, verdict still says "hat gelernt" — could regress
unnoticed. This pins the contract directly.

Reproduced 2026-09-23 (live state.db window, crafted inverted leak, net
deliberately under-converged with epochs=1):

    acc = 0.714   leak_findings() = ['tool_name']
    acc-gate    -> "✅ hat gelernt"      (wrong: a LEAK-WARNUNG printed above it)
    finding-gate -> "⚠️ NICHT gelernt"   (correct)

Hermetic: crafted data with a label decidable a priori, no live DB touched.
"""
import importlib.util
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("self_learning_verdict", SCRIPTS / "self_learning.py")
SL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SL)


def _inverted_leak(n=70, seed=7):
    """label == NOT tool_name — a real inverted leak by construction."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        feats = [rnd.randint(0, 1) for _ in range(len(SL.FEATURE_NAMES))]
        out.append((feats, [float(1 - feats[SL.FEATURE_NAMES.index("tool_name")])]))
    return out


def test_verdict_follows_the_finding_not_the_accuracy():
    """The regression: acc below 0.999 with a leak present must STILL warn.

    This is the exact case the old `if acc >= 0.999:` gate got wrong.
    """
    data = _inverted_leak()
    findings = SL.leak_findings(data)
    assert [n for n, _b, _s in findings] == ["tool_name"]

    # a deliberately under-converged net -> acc near chance, well below 0.999
    net = SL.train_self(data, epochs=1, lr=0.3)
    acc = SL._accuracy(net, data)
    assert acc < 0.999, f"fixture must under-converge to exercise the bug, got acc={acc}"

    assert SL.must_warn(findings, acc) is True, (
        "a leaking feature must force the warning even at low accuracy"
    )


def test_verdict_is_silent_without_a_finding():
    """No finding -> no warning, regardless of how high acc happens to be."""
    assert SL.must_warn([], 0.999) is False
    assert SL.must_warn([], 1.0) is False


def test_verdict_ignores_accuracy_entirely():
    """Pins the contract: findings decide, acc is not consulted."""
    finding = [("tool_name", 0.062, 0.938)]
    for acc in (0.0, 0.5, 0.714, 0.998, 1.0):
        assert SL.must_warn(finding, acc) is True
        assert SL.must_warn([], acc) is False
