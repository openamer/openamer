"""Session picker pagination must be deterministic when clock ticks tie."""

import pytest

from openamer_state import SessionDB


@pytest.mark.parametrize("by_activity", [False, True])
def test_equal_timestamps_use_stable_id_order_for_pagination(tmp_path, by_activity):
    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        for sid in ("s1", "s2", "s3"):
            db.create_session(sid, "cli", cwd="/repo")
        db._conn.execute("UPDATE sessions SET started_at = ?", (1_700_000_000.0,))
        db._conn.commit()
        rows = db.list_sessions_rich(cwd_prefix="/repo", order_by_last_active=by_activity)
        assert [r["id"] for r in rows] == ["s3", "s2", "s1"]
        pages = [db.list_sessions_rich(limit=1, offset=i,
                    order_by_last_active=by_activity)[0]["id"] for i in range(3)]
        assert pages == ["s3", "s2", "s1"]
    finally:
        db.close()
