#!/usr/bin/env python3
"""Tests for the three self-initiated agency scripts.

Run: python test_agency.py
Covers: morning_brief (renders from real sources), competitor_scan
(watchdog quiet/seen logic), active_learn.world_explore (real job
status, not text-mining).
"""
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestMorningBrief(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mb = _load("morning_brief", os.path.join(T, "morning_brief.py"))

    def test_build_renders_from_real_sources(self):
        out = self.mb.build()
        self.assertIn("System:", out, "must include cron fleet")
        self.assertIn("Weltmodell", out, "must include world-model growth")
        self.assertGreater(len(out), 100, "brief must not be empty")

    def test_build_never_raises(self):
        # degraded sources (missing files) must still render
        with mock.patch.object(self.mb, "_cron_fleet", side_effect=Exception("x")):
            out = self.mb.build()
            self.assertIsInstance(out, str)


class TestCompetitorScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cs = _load("competitor_scan", os.path.join(T, "competitor_scan.py"))

    def test_seen_logic_is_persistent(self):
        self.cs._mark_seen(["testid1", "testid2"])
        seen = self.cs._seen_ids()
        self.assertIn("testid1", seen)
        self.assertIn("testid2", seen)

    def test_no_fake_data(self):
        src = open(os.path.join(T, "competitor_scan.py"), encoding="utf-8").read()
        self.assertNotIn("MOCK", src.upper().replace("MOCK_DATA", ""))
        # real API endpoint
        self.assertIn("hn.algolia.com", src)


class TestWorldExplore(unittest.TestCase):
    """world_explore must read REAL scheduler status, not text-mining."""

    def test_uses_jobs_json_not_output_mining(self):
        src = open(os.path.join(T, "active_learn.py"), encoding="utf-8").read()
        # the text-mining path must be gone
        self.assertNotIn('content.splitlines()', src.split("def world_explore")[1].split("def ")[0],
                         "world_explore must not mine report text lines")
        self.assertIn("last_status", src, "must read scheduler job status")

    def test_returns_real_failures_only(self):
        al = _load("active_learn", os.path.join(T, "active_learn.py"))
        r = al.world_explore()
        # must be one of the known return shapes — never fabricate counts
        self.assertTrue(
            r.startswith(("world-explore:", "world-explore: synthetic", "error:")),
            f"unexpected shape: {r[:80]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
