"""Legacy/malformed ``repeat`` shapes must not crash the cron bookkeeping.

Regression for 2026-10-04: two watchdog jobs carried ``repeat: "forever"``
instead of the canonical ``{"times": None, "completed": N}``. ``mark_job_run``
read it with ``.get()`` and raised
``AttributeError: 'str' object has no attribute 'get'`` on every tick — and the
caller's error path then called ``mark_job_run`` again, so the tick died twice
and the job's status was never persisted. The same shape is read by
``claim_dispatch`` and ``get_due_jobs``.
"""

import pytest

from cron.jobs import (
    _repeat_fields,
    claim_dispatch,
    get_due_jobs,
    load_jobs,
    mark_job_run,
    save_jobs,
)


@pytest.fixture()
def tmp_cron_dir(tmp_path, monkeypatch):
    """Redirect cron storage to a temp directory (mirrors test_jobs.py)."""
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")
    return tmp_path


# =========================================================================
# _repeat_fields — every shape the field can arrive in
# =========================================================================


class TestRepeatFields:
    def test_canonical_infinite(self):
        assert _repeat_fields({"repeat": {"times": None, "completed": 228}}) == (None, 228)

    def test_canonical_finite(self):
        assert _repeat_fields({"repeat": {"times": 5, "completed": 2}}) == (5, 2)

    @pytest.mark.parametrize(
        "repeat,expected",
        [
            ("forever", (None, 0)),
            ("infinite", (None, 0)),
            ("", (None, 0)),
            (0, (None, 0)),
            (-1, (None, 0)),
            (3, (3, 0)),
            (None, (None, 0)),
            ({"times": "forever", "completed": 1}, (None, 1)),
            ({"times": 2, "completed": "bad"}, (2, 0)),
            ({"completed": 7}, (None, 7)),
            ([], (None, 0)),
        ],
    )
    def test_tolerates_every_shape(self, repeat, expected):
        assert _repeat_fields({"repeat": repeat}) == expected


# =========================================================================
# The crash itself — a bare "forever" must not take the tick down
# =========================================================================


def _watchdog_job(repeat):
    return {
        "id": "hb",
        "name": "Heartbeat Watchdog",
        "enabled": True,
        "state": "scheduled",
        "schedule": {"kind": "interval", "minutes": 15, "display": "every 15m"},
        "repeat": repeat,
        "next_run_at": "2026-01-01T00:00:00+00:00",
    }


class TestMalformedRepeatDoesNotCrash:
    def test_mark_job_run_survives_bare_forever(self, tmp_cron_dir):
        """Before the fix this raised AttributeError from ``repeat.get``."""
        save_jobs([_watchdog_job("forever")])

        mark_job_run("hb", True)  # must not raise

        job = load_jobs()[0]
        # Normalized in place to the canonical shape, counter incremented.
        assert job["repeat"] == {"times": None, "completed": 1}
        assert job["last_status"] == "ok"

    def test_mark_job_run_survives_bare_zero(self, tmp_cron_dir):
        save_jobs([_watchdog_job(0)])

        mark_job_run("hb", False, "boom")

        job = load_jobs()[0]
        assert job["repeat"] == {"times": None, "completed": 1}
        assert job["last_status"] == "error"

    def test_claim_dispatch_survives_malformed_repeat(self, tmp_cron_dir):
        for bad in ("forever", 0, "infinite"):
            save_jobs([
                {
                    "id": "os1",
                    "name": "one-shot",
                    "enabled": True,
                    "schedule": {"kind": "once", "run_at": "2026-01-01T00:00:00+00:00"},
                    "repeat": bad,
                }
            ])
            # An infinite/malformed repeat always dispatches — and must not raise.
            assert claim_dispatch("os1") is True

    def test_get_due_jobs_survives_malformed_repeat(self, tmp_cron_dir):
        save_jobs([_watchdog_job("forever")])
        get_due_jobs()  # must not raise

    def test_canonical_finite_limit_still_removes_job(self, tmp_cron_dir):
        """The tolerant reader must not break the finite-repeat removal."""
        job = {
            "id": "os2",
            "name": "finite",
            "enabled": True,
            "schedule": {"kind": "once", "run_at": "2026-01-01T00:00:00+00:00"},
            "repeat": {"times": 1, "completed": 1},
        }
        save_jobs([job])
        assert claim_dispatch("os2") is False
        assert load_jobs() == []  # limit reached -> removed, will not re-fire
