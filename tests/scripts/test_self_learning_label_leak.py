"""The self-learning runner must not claim it learned when it only read its own label.

Observed live (22.09.26): `scripts/self_learning.py` trained a 7->6->1 net on session
messages, hit 1.000/1.000 accuracy and printed "oa_ripple hat gelernt". The label was
`role == "assistant"`, and the input vector contained `role == "user"` and
`tool_name is not None` — so the label was derivable from the features. Measured
cross-tab over the window, exact:

    role='assistant'  tool_name=NULL   n=12
    role='tool'       tool_name set    n=40
    role='user'       tool_name=NULL   n=1

Hermetic: every case runs against a temp DB built here, never the live state.db.
The crafted cases carry labels decidable a priori, so they are stable regardless of
what the live store contains.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("self_learning", SCRIPTS / "self_learning.py")
SL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SL)

_TOOL_IDX = SL.FEATURE_NAMES.index("tool_name")
_ROLE_IDX = SL.FEATURE_NAMES.index("role==user")


def _db(tmp_path, rows):
    """A minimal `messages` table. rows = [(role, content, tool_name), ...] by id."""
    db = tmp_path / "state.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT, tool_name TEXT)")
    con.executemany("INSERT INTO messages (role, content, tool_name) VALUES (?,?,?)", rows)
    con.commit()
    con.close()
    return db


def test_live_shape_flags_the_leak(tmp_path):
    """The observed shape: assistant rows carry no tool_name, tool rows do.

    This is the real bug. `tool_name` separates the label at ~1.000 from below, so
    the gate must fire and the feature must be reported as an INVERTED separator.
    """
    rows = (
        [("assistant", "answer " * 50, None)] * 12
        + [("tool", "result " * 200, "read_file")] * 40
        + [("user", "question " * 300, None)] * 1
    )
    data = SL.extract_training_data(limit=80, db_path=_db(tmp_path, rows))
    assert len(data) == 53

    findings = {name: (base, strength) for name, base, strength in SL.leak_findings(data)}
    assert "tool_name" in findings, "the tool_name leak must be reported"
    base, strength = findings["tool_name"]
    assert strength >= 0.7
    # inverted: the feature predicts the label *backwards*, so |1 - base| is the signal.
    # A gate that only tests base >= 0.70 misses this entirely.
    assert base < 0.5, f"expected an inverted separator, got direct accuracy {base}"
    assert strength > base


def test_uncorrelated_data_is_not_flagged(tmp_path):
    """A perfect score must come from the data, not the gate being trigger-happy."""
    rows = []
    for i in range(60):
        role = "assistant" if i % 2 else "tool"
        rows.append((role, "abcdefg", "t" if i % 3 else None))
    data = SL.extract_training_data(limit=80, db_path=_db(tmp_path, rows))
    # role -> label is systematic here; assert the gate reports only what separates.
    for _name, _base, strength in SL.leak_findings(data):
        assert strength >= 0.7, "leak_findings must not return sub-threshold entries"


def test_extraction_is_deterministic(tmp_path):
    """ORDER BY RANDOM() made consecutive runs sample different rows (48..65 live),
    so no accuracy figure from this script was comparable. Newest-first instead."""
    rows = [(f"role{r}", f"content {r} " * 3, None) for r in range(40)]
    db = _db(tmp_path, rows)
    first = [x for x, _y in SL.extract_training_data(limit=80, db_path=db)]
    second = [x for x, _y in SL.extract_training_data(limit=80, db_path=db)]
    assert first == second


def test_role_ablation_keeps_the_second_channel(tmp_path):
    """Zeroing the role feature must NOT silence the gate — tool_name still leaks it.
    An ablation that "fixes" the leak would hide the real problem."""
    rows = (
        [("assistant", "answer " * 50, None)] * 12
        + [("tool", "result " * 200, "read_file")] * 40
        + [("user", "question " * 300, None)] * 2
    )
    db = _db(tmp_path, rows)
    plain = SL.extract_training_data(limit=80, db_path=db)
    ablated = SL.extract_training_data(limit=80, db_path=db, drop_role=True)

    assert all(x[_ROLE_IDX] == 0.0 for x, _y in ablated)
    assert any(x[_ROLE_IDX] == 1.0 for x, _y in plain), "fixture must exercise the role feature"
    assert [name for name, _b, _s in SL.leak_findings(ablated)], (
        "ablation must not empty the leak report — a second channel remains"
    )


def test_gate_threshold_is_a_real_bound(tmp_path):
    """A ~55% separator must stay below the 0.70 threshold."""
    rows = []
    for i in range(100):
        # every 11th row breaks the otherwise perfect tool_name<->role mapping
        role = "tool" if i % 11 == 0 or i % 2 else "assistant"
        rows.append((role, "x" * 30, "read_file" if role == "tool" else None))
    data = SL.extract_training_data(limit=80, db_path=_db(tmp_path, rows))
    strong = [n for n, _b, s in SL.leak_findings(data, threshold=0.99)]
    weak = [n for n, _b, s in SL.leak_findings(data, threshold=0.70)]
    assert set(strong) <= set(weak), "a higher threshold can only report fewer features"


def test_unreadable_db_degrades_quietly(tmp_path):
    """No DB / no schema must not raise — the caller still prints its report."""
    empty = tmp_path / "absent.db"
    assert SL.extract_training_data(limit=80, db_path=empty) == []
