"""Tests for openamer_cli.evaluation — Evaluation Benchmarks."""

import json
import pathlib
import tempfile
from pathlib import Path

import pytest

from openamer_cli.evaluation import (
    BENCHMARK_RUNS_DIR,
    BenchmarkRun,
    BenchmarkSuite,
    TestCase,
    TestResult,
    compare_runs,
    get_leaderboard,
    print_leaderboard,
    run_benchmark,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _echo_model(prompt: str) -> str:
    """A trivial model function that returns the prompt."""
    return prompt


def _capital_model(prompt: str) -> str:
    """A model that returns known answers."""
    answers = {
        "What is the capital of France?": "Paris",
        "What is 2+2?": "4",
        "What is the capital of Germany?": "Berlin",
        "What is the meaning of life?": "42",
    }
    return answers.get(prompt, "I don't know")


# ── Tests for TestCase and TestResult ─────────────────────────────────────────


class TestTestCase:
    def test_default_creation(self):
        tc = TestCase(name="test1", input="hello")
        assert tc.name == "test1"
        assert tc.input == "hello"
        assert tc.expected is None
        assert tc.evaluator is None
        assert tc.metadata == {}


class TestTestResult:
    def test_default_creation(self):
        tr = TestResult(test_name="t1", passed=True)
        assert tr.test_name == "t1"
        assert tr.passed is True
        assert tr.reason == ""


# ── Tests for BenchmarkRun ─────────────────────────────────────────────────────


class TestBenchmarkRun:
    def test_default_auto_date(self):
        run = BenchmarkRun(name="test-run")
        assert run.date != ""  # auto-populated

    def test_to_dict(self):
        run = BenchmarkRun(
            name="test",
            model="gpt-4",
            date="2026-01-01T00:00:00",
            total=2,
            passed=2,
            pass_rate=100.0,
            avg_latency=150.0,
            results=[
                TestResult(test_name="t1", passed=True, latency_ms=100.0, actual_output="ok"),
                TestResult(test_name="t2", passed=True, latency_ms=200.0, actual_output="yes"),
            ],
        )
        d = run.to_dict()
        assert d["name"] == "test"
        assert d["total"] == 2
        assert d["pass_rate"] == 100.0
        assert len(d["results"]) == 2

    def test_from_dict(self):
        d = {
            "name": "loaded",
            "date": "2026-06-01",
            "model": "claude-3",
            "total": 1,
            "passed": 1,
            "pass_rate": 100.0,
            "avg_latency": 50.0,
            "results": [
                {
                    "test_name": "t1",
                    "passed": True,
                    "reason": "",
                    "latency_ms": 50.0,
                    "actual_output": "Paris",
                    "metadata": {},
                }
            ],
        }
        run = BenchmarkRun.from_dict(d)
        assert run.name == "loaded"
        assert run.total == 1
        assert run.passed == 1

    def test_save_and_load(self):
        run = BenchmarkRun(
            name="save-test",
            model="gpt-4",
            total=2,
            passed=2,
            pass_rate=100.0,
            avg_latency=100.0,
            results=[
                TestResult(test_name="t1", passed=True, latency_ms=100.0),
                TestResult(test_name="t2", passed=True, latency_ms=100.0),
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            saved = run.save(path)
            assert saved == path
            loaded = BenchmarkRun.load(path)
            assert loaded.name == "save-test"
            assert len(loaded.results) == 2
            assert loaded.passed == 2


# ── Tests for BenchmarkSuite ──────────────────────────────────────────────────


class TestBenchmarkSuite:
    def test_empty_suite_raises(self):
        suite = BenchmarkSuite(name="empty")
        with pytest.raises(ValueError, match="No model function"):
            suite.run()

    def test_run_with_model_fn(self):
        suite = BenchmarkSuite(name="math")
        suite.add_case(TestCase(name="add", input="What is 2+2?", expected="4"))
        suite.add_case(TestCase(name="life", input="What is the meaning of life?", expected="42"))
        run = suite.run(model="test-model", model_fn=_capital_model)
        assert run.model == "test-model"
        assert run.total == 2
        assert run.passed >= 1  # "42" is valid, "4" appears in output

    def test_run_with_set_model_fn(self):
        suite = BenchmarkSuite(name="capitals")
        suite.add_case(TestCase(name="france", input="What is the capital of France?", expected="Paris"))
        suite.set_model_fn(_capital_model)
        run = suite.run(model="test-v2")
        assert run.total == 1
        assert run.passed == 1

    def test_run_with_evaluator(self):
        def custom_eval(_input: str, actual: str) -> tuple:
            return ("Paris" in actual or "Berlin" in actual), "Capital check"

        suite = BenchmarkSuite(name="custom")
        suite.add_case(TestCase(name="france", input="What is the capital of France?", evaluator=custom_eval))
        run = suite.run(model="test", model_fn=_capital_model)
        assert run.passed == 1

    def test_run_model_failure(self):
        def failing_model(_prompt: str) -> str:
            raise RuntimeError("API error")

        suite = BenchmarkSuite(name="fails")
        suite.add_case(TestCase(name="t1", input="hello"))
        run = suite.run(model="broken", model_fn=failing_model)
        assert run.passed == 0
        assert len(run.results) == 1
        assert "failed" in run.results[0].reason.lower()

    def test_add_cases(self):
        suite = BenchmarkSuite(name="multi")
        suite.add_cases(
            TestCase(name="a", input="q1"),
            TestCase(name="b", input="q2"),
        )
        assert len(suite.test_cases) == 2


# ── Tests for run_benchmark ────────────────────────────────────────────────────


class TestRunBenchmark:
    def test_run_benchmark(self):
        cases = [
            TestCase(name="t1", input="What is the capital of France?", expected="Paris"),
            TestCase(name="t2", input="What is 2+2?", expected="4"),
        ]
        run = run_benchmark(name="test", test_cases=cases, model="gpt4", model_fn=_capital_model)
        assert run.name == "test"
        assert run.total == 2
        assert run.pass_rate > 0


# ── Tests for compare_runs ─────────────────────────────────────────────────────


class TestCompareRuns:
    def test_compare_equal(self):
        def ident(prompt: str) -> str:
            return "yes"

        cases = [TestCase(name="t1", input="q1", expected="yes")]
        run1 = run_benchmark("a", cases, "m1", ident)
        run2 = run_benchmark("b", cases, "m2", ident)
        comparison = compare_runs(run1, run2)
        assert comparison["pass_rate_diff"] == 0.0
        assert len(comparison["regressions"]) == 0
        assert len(comparison["improvements"]) == 0

    def test_compare_regression(self):
        def good(_p: str) -> str:
            return "yes"

        def bad(_p: str) -> str:
            return "no"

        cases = [TestCase(name="t1", input="q1", expected="yes")]
        run1 = run_benchmark("a", cases, "m1", good)
        run2 = run_benchmark("b", cases, "m2", bad)
        comparison = compare_runs(run1, run2)
        assert len(comparison["regressions"]) == 1
        assert comparison["regressions"][0]["test_name"] == "t1"

    def test_compare_improvement(self):
        def bad(_p: str) -> str:
            return "no"

        def good(_p: str) -> str:
            return "yes"

        cases = [TestCase(name="t1", input="q1", expected="yes")]
        run1 = run_benchmark("a", cases, "m1", bad)
        run2 = run_benchmark("b", cases, "m2", good)
        comparison = compare_runs(run1, run2)
        assert len(comparison["improvements"]) == 1

    def test_compare_new_test_in_run2(self):
        def ident(p: str) -> str:
            return "ok"

        run1 = run_benchmark("a", [TestCase("t1", "q1")], "m1", ident)
        run2 = run_benchmark(
            "b",
            [TestCase("t1", "q1"), TestCase("t2", "q2")],
            "m2",
            ident,
        )
        comparison = compare_runs(run1, run2)
        # t2 is new in run2 and should appear as improvement if passed
        assert len(comparison["improvements"]) >= 1


# ── Tests for leaderboard ──────────────────────────────────────────────────────


class TestLeaderboard:
    def test_empty_leaderboard(self):
        entries = get_leaderboard()
        assert isinstance(entries, list)

    def test_print_empty_leaderboard(self):
        output = print_leaderboard()
        assert "No benchmark runs found" in output

    def test_leaderboard_with_saved_runs(self):
        """Test that saved runs appear in leaderboard."""
        run = BenchmarkRun(
            name="lb-test",
            model="gpt-4",
            total=2,
            passed=2,
            pass_rate=100.0,
            avg_latency=50.0,
        )
        with tempfile.TemporaryDirectory() as tmp:
            import openamer_cli.evaluation as ev
            original_dir = ev.BENCHMARK_RUNS_DIR
            try:
                ev.BENCHMARK_RUNS_DIR = Path(tmp)
                run.save()
                entries = ev.get_leaderboard()
                assert len(entries) >= 1
                output = ev.print_leaderboard()
                assert "lb-test" in output
                assert "gpt-4" in output
            finally:
                ev.BENCHMARK_RUNS_DIR = original_dir


# ── Tests for BenchmarkSuite.from_file ────────────────────────────────────────


class TestBenchmarkSuiteFromFile:
    def test_from_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.json"
            path.write_text(
                json.dumps({
                    "name": "json-suite",
                    "description": "from JSON",
                    "test_cases": [
                        {"name": "t1", "input": "Hello", "expected": "Hello"},
                    ],
                })
            )
            suite = BenchmarkSuite.from_file(path)
            assert suite.name == "json-suite"
            assert len(suite.test_cases) == 1
            assert suite.test_cases[0].name == "t1"