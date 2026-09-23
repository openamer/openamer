"""Regression test: KTA's group-state arm must not report a constant as a result.

Live bug 23.09.26: ``experiment_group_state()`` evaluated the saved **Z10**
model. Z10 has ``num_gens == 1``, so the choice softmax over a single generator
is degenerate — the generator's weight is 1.0 whatever ``W`` and ``b`` hold —
and the structural readout ``<S, M_c>`` is exact for the permutation
representation by construction. Measured at L=2048 on the install:

    saved model          acc = 1.000
    scrambled W,b        acc = 1.000
    all-zero W,b         acc = 1.000

The arm logged ``worst min over 3 seeds x 3 lengths = 1.0000`` every cycle: a
number that cannot come out wrong, reported as a measurement. The same probe on
A5 (``|G|=60``, 2 generators) separates: saved 1.000 vs scrambled 0.000.

These tests pin the replacement contract:
  * a saturated group is refused as a measurement target (Z10 is degenerate)
  * the arm runs a parameter-BLIND control alongside the trained model
  * the reported result quotes the control, not just the trained number
  * a control that saturates the task is surfaced as SATURATED, not green
"""
import importlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
TRAIN = SCRIPTS / "training"
for p in (str(SCRIPTS), str(TRAIN)):
    if p not in sys.path:
        sys.path.insert(0, p)


import knowledge_to_action as kta  # noqa: E402
from group_scaling_lab import GroupState, _attach, accuracy, build_group  # noqa: E402


def test_z10_is_parameter_blind():
    """The degeneracy itself: one generator => softmax is a no-op.

    If this assertion ever fails the premise of the fix changed, and the
    comment in experiment_group_state() is stale.
    """
    g = _attach(build_group("Z10"))
    assert g.num_gens == 1

    model = GroupState(g, __import__("random").Random(0), tau=0.1)
    for i in range(len(model.W.data)):
        model.W.data[i] = 0.0
    for i in range(len(model.b.data)):
        model.b.data[i] = 0.0

    zero_acc = min(accuracy(model, g, 256, n=20, seed=s) for s in (0, 1, 2))
    assert zero_acc == 1.0, (
        "Z10 with all-zero parameters should still be exact — that is why the "
        "old arm's 1.0000 carried no information")


def test_a5_is_parameter_dependent():
    """The replacement target must actually depend on its parameters."""
    import random

    g = _attach(build_group("A5"))
    assert g.num_gens > 1

    blind = GroupState(g, random.Random(11), tau=0.1)
    r = random.Random(99)
    for i in range(len(blind.W.data)):
        blind.W.data[i] = r.gauss(0.0, 2.0)
    for i in range(len(blind.b.data)):
        blind.b.data[i] = r.gauss(0.0, 2.0)

    blind_acc = min(accuracy(blind, g, 256, n=20, seed=s) for s in (0, 1, 2))
    assert blind_acc < 0.2, (
        "A5 with scrambled parameters must FAIL the task, otherwise the arm "
        "would again measure something it cannot get wrong")


def _models(tmp_path):
    """Copy the shipped group-state artifacts into a scratch models dir."""
    import shutil

    dst = tmp_path / "models"
    dst.mkdir(exist_ok=True)
    for name in ("group_state_a5.json", "group_state_z10.json"):
        src = ROOT / "models" / name
        if src.exists():
            shutil.copy(src, dst / name)
    return dst


def test_arm_reports_a_blind_control(tmp_path, monkeypatch):
    """The result must quote the control, not only the trained number."""
    import group_state_engine as engine

    monkeypatch.setattr(engine, "DEFAULT_DIR", str(_models(tmp_path)))
    result = kta.experiment_group_state()

    assert result["measurable"] is True
    assert "blind-parameter control" in result["result"]
    assert "trained-minus-blind" in result["result"]
    assert result["trained_worst_min"] > result["blind_worst_min"] + 0.5
    assert result["saturated"] is False
    assert Path(result["artifact"]).exists()


def test_arm_flags_a_saturated_target(tmp_path, monkeypatch):
    """Pointed at Z10 (parameter-blind), the arm must flag SATURATED."""
    import group_state_engine as engine

    monkeypatch.setattr(engine, "DEFAULT_DIR", str(_models(tmp_path)))
    result = kta.experiment_group_state(group_name="Z10")

    assert result["measurable"] is True
    assert result["saturated"] is True
    assert "SATURATED" in result["result"]
    assert result["trained_worst_min"] - result["blind_worst_min"] <= 0.05


def test_arm_fits_the_cron_slot(tmp_path, monkeypatch):
    """3 lengths x 3 seeds x 3 arms must stay inside one */30 cron slot."""
    import group_state_engine as engine

    monkeypatch.setattr(engine, "DEFAULT_DIR", str(_models(tmp_path)))
    t0 = time.time()
    kta.experiment_group_state()
    assert time.time() - t0 < 120
