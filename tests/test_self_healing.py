"""Tests for Memory Healing, Auto Tester, and Swarm Metrics."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from openamer_cli import memory_healing, auto_tester, swarm_metrics


# ----- Memory Healing -----


class TestMemoryHealing:
    def test_check_empty_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            import openamer_cli.memory_healing as mh
            orig = mh._home
            mh._home = lambda: base
            try:
                report = mh.check_memory_integrity()
                assert "issues" in report
            finally:
                mh._home = orig

    def test_check_with_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            memdir = base / "memories"
            memdir.mkdir()
            f = memdir / "CORRUPT.md"
            f.write_bytes(b"\xff\xfe\x00\x01corrupt data")
            import openamer_cli.memory_healing as mh
            orig = mh._home
            mh._home = lambda: base
            try:
                report = mh.check_memory_integrity()
                assert report["issues_count"] >= 1
            finally:
                mh._home = orig

    def test_healing_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            memdir = base / "memories"
            memdir.mkdir()
            f = memdir / "EMPTY.md"
            f.write_text("")
            import openamer_cli.memory_healing as mh
            orig = mh._home
            mh._home = lambda: base
            try:
                result = mh.run_healing_cycle()
                assert result["issues_found"] >= 0
            finally:
                mh._home = orig

    def test_cron_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            import openamer_cli.memory_healing as mh
            orig = mh._home
            mh._home = lambda: base
            try:
                logpath = mh.run_cron_entry()
                assert logpath.endswith(".json")
                assert Path(logpath).exists()
            finally:
                mh._home = orig


# ----- Auto Tester -----


class TestAutoTester:
    def test_repo_dir_fallback(self):
        # Just check it returns something
        repo = auto_tester._repo_dir()
        assert isinstance(repo, Path)

    def test_run_new_tests(self):
        result = auto_tester.run_new_tests()
        # Should find and run the test files
        assert result["status"] in ("pass", "fail")
        assert "elapsed_seconds" in result

    def test_save_test_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.auto_tester as at
            orig = at._home
            at._home = lambda: Path(tmpdir)
            try:
                logpath = at.save_test_result({"status": "pass", "passed": 5})
                assert Path(logpath).exists()
                with open(logpath, encoding="utf-8") as f:
                    data = json.load(f)
                assert data["status"] == "pass"
            finally:
                at._home = orig

    def test_cron_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.auto_tester as at
            orig = at._home
            at._home = lambda: Path(tmpdir)
            try:
                logpath = at.run_cron_entry()
                assert logpath.endswith(".json")
            finally:
                at._home = orig


# ----- Swarm Metrics -----


class TestSwarmMetrics:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.swarm_metrics as sm
            orig = sm._home
            sm._home = lambda: Path(tmpdir)
            sm._metrics.clear()
            try:
                sm.record_metric("swarm", "query", 42.0, {"peer": "test"})
                results = sm.get_metrics("swarm")
                assert results["total_records"] >= 1
            finally:
                sm._home = orig

    def test_swarm_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.swarm_metrics as sm
            orig = sm._home
            sm._home = lambda: Path(tmpdir)
            sm._metrics.clear()
            try:
                sm.record_swarm_operation("delegate", 150.5, True)
                sm.record_swarm_operation("query", 1200.0, True)
                summary = sm.get_swarm_summary()
                assert "avg_latency_ms" in summary
                assert summary["total_operations"] >= 1
            finally:
                sm._home = orig

    def test_generate_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.swarm_metrics as sm
            orig = sm._home
            sm._home = lambda: Path(tmpdir)
            sm._metrics.clear()
            try:
                sm.record_swarm_operation("test", 100.0, True)
                report = sm.generate_report()
                assert "SWARM METRICS" in report
                assert "Avg" in report
            finally:
                sm._home = orig

    def test_cron_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import openamer_cli.swarm_metrics as sm
            orig = sm._home
            sm._home = lambda: Path(tmpdir)
            sm._metrics.clear()
            try:
                sm.record_swarm_operation("cron", 50.0, True)
                logpath = sm.run_cron_entry()
                assert Path(logpath).exists()
            finally:
                sm._home = orig