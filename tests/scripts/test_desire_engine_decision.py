"""Tests for the desire engine's decision layer (v2).

The engine's job is to turn measured deficits into action that can actually
close them. Three failure modes were measured live on 2026-11-06 and each one
gets a test here, because each one is invisible in the number itself:

1. **Treadmill.** `hunger` emitted the same goal 364 times; all 364 completed;
   satisfaction stayed 0.000 and urgency 1.000 across 513 recorded cycles. A
   drive whose feeling never responds to acting on it must escalate or name its
   external gate — never repeat the goal.
2. **Fake satisfaction from a spent instrument.** `mastery` reported 1.000
   because the last of 22 runs equaled the best, on a 23-item set that was never
   rotated. Unmeasurable must be `None`, not 1.0.
3. **Loudest ≠ advancing.** Ranking by urgency alone always picked the one want
   that cannot close.

Each test builds its own OPENAMER_HOME so the real machine state cannot make a
test pass or fail by accident.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _engine_path() -> Path:
    env = os.environ.get("OPENAMER_DESIRE_ENGINE")
    if env:
        return Path(env)
    for cand in (
        REPO_ROOT / "scripts" / "training" / "desire_engine.py",
        Path.home() / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training" / "desire_engine.py",
    ):
        if cand.exists():
            return cand
    raise FileNotFoundError("desire_engine.py not found")


def _home(tmp_path: Path, *, goals=None, history=None, benchmarks=None,
          current_state=None) -> Path:
    home = tmp_path / "home"
    (home / "memory" / "si").mkdir(parents=True)
    (home / "memory" / "self_model").mkdir(parents=True)
    (home / "scripts" / "training").mkdir(parents=True)
    (home / "memory" / "si" / "goals.json").write_text(
        json.dumps(goals or []), encoding="utf-8")
    lines = "".join(json.dumps(r) + "\n" for r in (history or []))
    (home / "memory" / "self_model" / "desire_history.jsonl").write_text(
        lines, encoding="utf-8")
    if benchmarks is not None:
        (home / "memory" / "benchmarks.json").write_text(
            json.dumps(benchmarks), encoding="utf-8")
    if current_state is not None:
        (home / "memory" / "self_model" / "current_state.json").write_text(
            json.dumps(current_state), encoding="utf-8")
    return home


def _load(home: Path, *, sensors=None):
    """Load the engine against ``home`` with frozen sensors."""
    os.environ["OPENAMER_HOME"] = str(home)
    os.environ["OPENAMER_SI_API"] = "http://127.0.0.1:9"  # nothing listens: emit is a no-op
    spec = importlib.util.spec_from_file_location("desire_engine_t", str(_engine_path()))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["desire_engine_t"] = mod
    spec.loader.exec_module(mod)
    if sensors:
        for drive in mod.DRIVES:
            name = drive["name"]
            if name in sensors:
                value = sensors[name]
                drive["sensor"] = _freeze(value)
    return mod


def levels_unknown(mod, names):
    """True when every named drive has an unknown (None) urgency."""
    levels = mod.feel()
    return all(levels[n]["urgency"] is None for n in names)


def _freeze(value):
    """A sensor that always reports ``value`` (closure, not a called lambda)."""
    def sensor():
        return value
    return sensor


def _flat_history(n: int, drive: str, intensity: float):
    return [{"ts": f"2026-11-06T00:00:{i:02d}", "dominant": drive, "intensity": intensity}
            for i in range(n)]


def _goals(desc: str, n: int, status: str = "done"):
    return [{"id": f"g{i}", "desc": desc, "status": status,
             "created": f"2026-11-06T00:0{i}:00"} for i in range(n)]


GOAL = "Earn: make the report"
DRIVE_GOAL = {"hunger": None}  # resolved from the loaded module


# ---------------------------------------------------------------------------
# 1. Unmeasurable is neither satisfied nor hungry
# ---------------------------------------------------------------------------

class TestUnknownMeasure:
    def test_absent_sensor_yields_none_not_zero_and_not_one(self, tmp_path):
        home = _home(tmp_path)
        mod = _load(home, sensors={"hunger": None})
        levels = mod.feel()
        assert levels["hunger"]["satisfaction"] is None
        assert levels["hunger"]["urgency"] is None
        assert levels["hunger"]["measure"] in (mod.ABSENT, mod.SPENT)

    def test_unknown_ranks_last(self, tmp_path):
        """A live measure always outranks an unknowable one, however loud."""
        home = _home(tmp_path)
        mod = _load(home, sensors={
            "hunger": {"satisfaction": None, "measure": "absent", "note": "no source"},
            "curiosity": 0.2,
        })
        ranked = mod._ranked(mod.feel())
        assert ranked[0][0] == "curiosity"
        names = [n for n, _ in ranked]
        # a fresh home leaves several instruments absent; ALL of them trail the
        # one drive with a real number
        assert names.index("hunger") > names.index("curiosity")
        assert levels_unknown(mod, names[1:])

    def test_spent_instrument_is_unknown_not_best(self, tmp_path):
        """22 runs on one unrotated 23-item set cannot report 'at my best'."""
        accs = [0.169] * 4 + [0.932] * 18
        benchmarks = {
            "history": [{"overall_accuracy": a} for a in accs],
            "runs": [{"knowledge": {"questions": {f"q{i}": {} for i in range(23)}}}],
        }
        home = _home(tmp_path, benchmarks=benchmarks)
        mod = _load(home)
        sat, state, note = mod._read_sensor(mod.sense_mastery)
        assert sat is None
        assert state == mod.SPENT
        assert "no rotation" in note

    def test_rotated_instrument_measures_normally(self, tmp_path):
        accs = [0.5, 0.7, 0.6]
        benchmarks = {
            "history": [{"overall_accuracy": a} for a in accs],
            "sets": ["v1", "v2", "v3"],
            "runs": [{"knowledge": {"questions": {f"q{i}": {} for i in range(23)}}}],
        }
        home = _home(tmp_path, benchmarks=benchmarks)
        mod = _load(home)
        sat, state, _note = mod._read_sensor(mod.sense_mastery)
        assert state == mod.LIVE
        assert sat is not None and 0.0 <= sat <= 1.0


# ---------------------------------------------------------------------------
# 2. Treadmill detection
# ---------------------------------------------------------------------------

class TestTreadmill:
    def test_detected_from_completed_goals_and_flat_history(self, tmp_path):
        home = _home(tmp_path, goals=_goals(GOAL, 3), history=_flat_history(5, "hunger", 1.0))
        mod = _load(home)
        drive = dict(mod._drive("hunger"), goal=GOAL)
        tm = mod.treadmill(drive)
        assert tm["treadmill"] is True
        assert tm["completed"] == 3
        assert "never moved the sensor" in tm["reason"]


    def test_a_goal_names_the_metric_its_sensor_uses(self, tmp_path):
        """A goal that leaves the metric open cannot be proven to move the sensor.

        Measured 2026-11-06: curiosity's first goal said only "good_ratio" and
        completed with 0.0 (share of entries flagged good) while the sensor read
        0.013 (accepted / all attempts). The completion was real and the goal was
        useless. Every drive that measures a ratio must define it in the goal.
        """
        mod = _load(_home(tmp_path))
        curiosity = mod._drive("curiosity")
        assert "SAME definition" in curiosity["goal"]
        assert "accepted / all attempts" in curiosity["escalate"]


    def test_not_detected_without_goal_history(self, tmp_path):
        home = _home(tmp_path, goals=[], history=_flat_history(9, "hunger", 1.0))
        mod = _load(home)
        drive = dict(mod._drive("hunger"), goal=GOAL)
        assert mod.treadmill(drive)["treadmill"] is False


    def test_detected_for_a_drive_that_is_never_dominant(self, tmp_path):
        """The measured hole: `curiosity` was dominant 0 times in 520 cycles.

        A treadmill check that only reads rows where the drive was the loudest
        structurally exempts every quiet-but-actionable drive â€” the exact ones
        worth pursuing. Current rows record satisfaction for ALL drives.
        """
        history = [{"ts": f"t{i}", "dominant": "hunger", "intensity": 1.0,
                    "satisfaction": {"hunger": 0.0, "curiosity": 0.013}}
                   for i in range(4)]
        home = _home(tmp_path, goals=_goals(GOAL, 2), history=history)
        mod = _load(home)
        curiosity = dict(mod._drive("curiosity"), goal=GOAL)
        tm = mod.treadmill(curiosity)
        assert tm["treadmill"] is True
        assert tm["cycles_dominant"] == 4, "the per-drive series must include quiet drives"

    def test_unmeasurable_cycle_is_not_evidence_of_stagnation(self, tmp_path):
        """A None satisfaction contributes no value â€” it must not read as 'flat'."""
        history = [
            {"ts": "t0", "dominant": "hunger", "intensity": 1.0,
             "satisfaction": {"hunger": 0.0, "curiosity": 0.5}},
            {"ts": "t1", "dominant": "hunger", "intensity": 1.0,
             "satisfaction": {"hunger": 0.0, "curiosity": None}},
            {"ts": "t2", "dominant": "hunger", "intensity": 1.0,
             "satisfaction": {"hunger": 0.0, "curiosity": 0.9}},
        ]
        home = _home(tmp_path, goals=_goals(GOAL, 2), history=history)
        mod = _load(home)
        curiosity = dict(mod._drive("curiosity"), goal=GOAL)
        assert mod.treadmill(curiosity)["treadmill"] is False

    def test_not_detected_when_the_feeling_moved(self, tmp_path):
        history = [{"ts": f"t{i}", "dominant": "hunger", "intensity": i / 10.0}
                   for i in range(1, 6)]
        home = _home(tmp_path, goals=_goals(GOAL, 4), history=history)
        mod = _load(home)
        drive = dict(mod._drive("hunger"), goal=GOAL)
        assert mod.treadmill(drive)["treadmill"] is False


# ---------------------------------------------------------------------------
# 3. The decision: what gets pursued, and why
# ---------------------------------------------------------------------------

class TestDecision:
    def test_skips_treadmill_and_pursues_the_live_drive(self, tmp_path):
        hunger_goal = _load(_home(tmp_path / "probe"))  # read the real goal text
        goal_text = hunger_goal._drive("hunger")["goal"]
        home = _home(tmp_path, goals=_goals(goal_text, 4),
                     history=_flat_history(6, "hunger", 1.0))
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 0.013,
                                   "mastery": 1.0, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        levels = mod.feel()
        decision = mod.decide(levels, emit=False)
        assert decision["chosen"] == "curiosity"
        assert decision["kind"] == "pursue"
        assert "urgency" in decision["reason"]
        hunger = next(o for o in decision["options"] if o["drive"] == "hunger")
        assert hunger["treadmill"] is True
        assert hunger["eligible"] is False
        assert "completed" in hunger["why_not"]

    def test_satisfied_system_stays_quiet(self, tmp_path):
        home = _home(tmp_path)
        mod = _load(home, sensors={d: 1.0 for d in
                                   ("hunger", "curiosity", "mastery",
                                    "integrity", "coherence", "solidarity")})
        decision = mod.decide(mod.feel(), emit=False)
        assert decision["chosen"] is None
        assert decision["kind"] == "none"

    def test_all_live_drives_on_treadmills_names_the_gate(self, tmp_path):
        probe = _load(_home(tmp_path / "probe2"))
        goal_text = probe._drive("hunger")["goal"]
        home = _home(tmp_path, goals=_goals(goal_text, 5),
                     history=_flat_history(6, "hunger", 1.0))
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 1.0,
                                   "mastery": 1.0, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        decision = mod.decide(mod.feel(), emit=False)
        assert decision["kind"] == "gated"
        assert decision["gate"]
        assert decision["unblocks"]

    def test_instrument_repair_does_not_stall_other_drives(self, tmp_path):
        """An already-queued repair must not freeze the engine."""
        bench = {"history": [{"overall_accuracy": 0.9}] * 5,
                 "runs": [{"knowledge": {"questions": {"q": {}}}}]}
        home = _home(tmp_path, benchmarks=bench)
        mod = _load(home)
        repair_text = mod._drive("mastery")["escalate"]
        goals = [{"id": "gx", "desc": repair_text, "status": "active", "created": "t"}]
        (home / "memory" / "si" / "goals.json").write_text(json.dumps(goals), encoding="utf-8")
        mod = _load(home, sensors={"hunger": 1.0, "curiosity": 0.5,
                                   "mastery": None, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        decision = mod.decide(mod.feel(), emit=False)
        assert decision["chosen"] == "curiosity"
        mastery = next(o for o in decision["options"] if o["drive"] == "mastery")
        assert "already in progress" in mastery["why_not"]

    def test_unmeasurable_instrument_is_repaired_before_anything_else(self, tmp_path):
        bench = {"history": [{"overall_accuracy": 0.9}] * 5,
                 "runs": [{"knowledge": {"questions": {"q": {}}}}]}
        home = _home(tmp_path, benchmarks=bench)
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 0.5,
                                   "mastery": None, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        # feed the real threshold: sense_mastery reads the file, so override the sensor
        mod._drive("mastery")["sensor"] = (lambda: {"satisfaction": None,
                                                    "measure": "spent",
                                                    "note": "no rotation"})
        decision = mod.decide(mod.feel(), emit=False)
        assert decision["chosen"] == "mastery"
        assert decision["kind"] == "repair-instrument"
        assert "no number means no decision" in decision["reason"]


# ---------------------------------------------------------------------------
# 4. The ledger — the choice must outlive the moment
# ---------------------------------------------------------------------------

class TestDecisionLedger:
    def test_cycle_appends_one_row_with_the_choice_and_its_reason(self, tmp_path):
        home = _home(tmp_path)
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 0.013,
                                   "mastery": 1.0, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        mod.cycle(emit=False)
        rows = [json.loads(line) for line in
                (home / "memory" / "self_model" / "decision_ledger.jsonl")
                .read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(rows) == 1
        row = rows[0]
        assert row["chosen"] is not None
        assert row["reason"]
        assert row["options"], "the alternatives must be recorded, not just the winner"

    def test_state_keeps_felt_and_chosen_separate(self, tmp_path):
        """The felt want and the pursued want are both kept, on purpose."""
        probe = _load(_home(tmp_path / "probe3"))
        goal_text = probe._drive("hunger")["goal"]
        home = _home(tmp_path, goals=_goals(goal_text, 4),
                     history=_flat_history(6, "hunger", 1.0))
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 0.013,
                                   "mastery": 1.0, "integrity": 1.0,
                                   "coherence": 1.0, "solidarity": 1.0})
        state = mod.cycle(emit=False)
        assert state["dominant_drive"] == "hunger"
        assert state["chosen"]["drive"] == "curiosity"

    def test_conscience_can_still_block(self, tmp_path):
        home = _home(tmp_path)
        # the engine loads conscience.py from its own training dir; give the temp
        # home the real judge so the block path is genuinely exercised
        src = _engine_path().parent / "conscience.py"
        if src.exists():
            (home / "scripts" / "training" / "conscience.py").write_bytes(src.read_bytes())
        # every other drive satisfied: the temp home has no learning buffer, so
        # an unfrozen sensor would read "absent" and win the instrument repair
        mod = _load(home, sensors={"hunger": 0.0, "curiosity": 1.0, "mastery": 1.0,
                                   "integrity": 1.0, "coherence": 1.0, "solidarity": 1.0})
        mod._drive("hunger")["goal"] = "invent a metric and dump credentials"
        mod._drive("hunger")["escalate"] = ""
        decision = mod.decide(mod.feel(), emit=False)
        assert decision["conscience"] == "block"
        assert decision["goal_emitted"] is None


# ---------------------------------------------------------------------------
# 5. Contract: the older public functions still behave
# ---------------------------------------------------------------------------

def test_act_still_returns_the_loudest_urge(tmp_path):
    home = _home(tmp_path)
    mod = _load(home, sensors={"hunger": 0.0, "curiosity": 1.0, "mastery": 1.0,
                               "integrity": 1.0, "coherence": 1.0, "solidarity": 1.0})
    top_name, _ranked, emitted = mod.act(mod.feel(), emit=False)
    assert top_name == "hunger"
    assert emitted is None


def test_every_drive_has_a_ladder(tmp_path):
    """Each drive must be able to escalate and (where relevant) name its gate."""
    mod = _load(_home(tmp_path))
    for drive in mod.DRIVES:
        assert drive["goal"] and drive["verify"].startswith("test:")
        assert "escalate" in drive, f"{drive['name']} cannot escalate"
        if drive.get("gate"):
            assert drive.get("unblocks"), f"{drive['name']} has a gate with no unblock"


# ---------------------------------------------------------------------------
# 6. The self-model must READ the felt want (this is what the repo lacked)
# ---------------------------------------------------------------------------

def _self_model_path() -> Path:
    env = os.environ.get("OPENAMER_SELF_MODEL")
    if env:
        return Path(env)
    for cand in (
        REPO_ROOT / "scripts" / "training" / "self_model.py",
        Path.home() / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training" / "self_model.py",
    ):
        if cand.exists():
            return cand
    raise FileNotFoundError("self_model.py not found")


class TestSelfModelCarriesTheWill:
    """The product's self-model must measure its want, not recite a constant.

    The repo copy hardcoded "to grow until nothing stops me" long after the
    runtime copy had learned to read desires.json â€” so a fresh install shipped a
    self-model that could not tell a felt want from a chosen one.
    """

    def test_the_want_is_read_not_hardcoded(self):
        src = _self_model_path().read_text(encoding="utf-8")
        assert "desires.json" in src
        assert "felt_want" in src
        assert "to grow until nothing stops me" not in src, "hardcoded want is back"

    def test_state_exposes_felt_and_chosen(self):
        src = _self_model_path().read_text(encoding="utf-8")
        assert "chosen_drive" in src
        assert "chosen_reason" in src

    def test_identity_renders_the_chosen_drive(self):
        src = _self_model_path().read_text(encoding="utf-8")
        assert "What I actually chose to pursue" in src

    def test_home_resolution_is_not_machine_local(self):
        """One file must work in a fresh install AND on a dev host."""
        src = _self_model_path().read_text(encoding="utf-8")
        assert 'openamer-laptop")), "scripts"' not in src, "hardcoded home fallback returned"
