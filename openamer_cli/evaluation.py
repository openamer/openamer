"""
Evaluation Benchmarks
=====================

A lightweight evaluation framework for benchmarking OpenAmer models.

Provides:

- ``BenchmarkRun`` dataclass capturing a single evaluation run
- ``BenchmarkSuite`` for defining and running benchmark test cases
- ``run_benchmark()`` — run test cases against a model
- ``compare_runs()`` — compare two benchmark runs
- ``print_leaderboard()`` — print a leaderboard of model results
- CLI integration via ``openamer eval run`` and ``openamer eval compare``
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default directory for persisting benchmark runs
BENCHMARK_RUNS_DIR = Path.home() / ".openamer" / "eval_runs"


# ── TestCase ──────────────────────────────────────────────────────────────────


@dataclass
class TestCase:
    """A single evaluation test case.

    Attributes:
        name: Human-readable test identifier.
        input: The input prompt or payload to send to the model.
        expected: Optional expected output (exact or substring).
        evaluator: Optional callable ``(input, actual_output) -> (bool, str)``
            that returns (passed, reason). If not provided, uses exact match
            against ``expected``.
        metadata: Optional extra metadata dict.
    """

    name: str
    input: str
    expected: Optional[str] = None
    evaluator: Optional[Callable[[str, str], Tuple[bool, str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── TestResult ────────────────────────────────────────────────────────────────


@dataclass
class TestResult:
    """Result of a single test case execution."""

    test_name: str
    passed: bool
    reason: str = ""
    latency_ms: float = 0.0
    actual_output: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── BenchmarkRun ──────────────────────────────────────────────────────────────


@dataclass
class BenchmarkRun:
    """A complete benchmark evaluation run.

    Serialisable to/from JSON for persistence and comparison.
    """

    name: str
    date: str = ""
    model: str = ""
    test_cases: List[TestCase] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    pass_rate: float = 0.0
    avg_latency: float = 0.0
    total: int = 0
    passed: int = 0

    def __post_init__(self) -> None:
        if not self.date:
            self.date = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "date": self.date,
            "model": self.model,
            "results": [
                {
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "reason": r.reason,
                    "latency_ms": r.latency_ms,
                    "actual_output": r.actual_output,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
            "pass_rate": self.pass_rate,
            "avg_latency": self.avg_latency,
            "total": self.total,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkRun":
        """Deserialize from a dict (as produced by ``to_dict()``)."""
        results = [
            TestResult(
                test_name=r["test_name"],
                passed=r["passed"],
                reason=r.get("reason", ""),
                latency_ms=r.get("latency_ms", 0.0),
                actual_output=r.get("actual_output", ""),
                metadata=r.get("metadata", {}),
            )
            for r in data.get("results", [])
        ]
        return cls(
            name=data["name"],
            date=data.get("date", ""),
            model=data.get("model", ""),
            results=results,
            pass_rate=data.get("pass_rate", 0.0),
            avg_latency=data.get("avg_latency", 0.0),
            total=data.get("total", 0),
            passed=data.get("passed", 0),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist this run as JSON to disk."""
        if path is None:
            BENCHMARK_RUNS_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = self.name.replace(" ", "_").replace("/", "_")
            path = BENCHMARK_RUNS_DIR / f"{safe_name}_{int(time.time())}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Benchmark run saved to %s", path)
        return path

    @classmethod
    def load(cls, path: Path) -> "BenchmarkRun":
        """Load a benchmark run from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ── BenchmarkSuite ────────────────────────────────────────────────────────────


class BenchmarkSuite:
    """Define and run a collection of benchmark test cases.

    Example::

        suite = BenchmarkSuite(name="my-suite")
        suite.add_case(TestCase(name="add", input="1+1=?", expected="2"))
        suite.add_case(TestCase(name="capital", input="Capital of France?", expected="Paris"))
        run = suite.run(model="gpt-4")
    """

    def __init__(
        self,
        name: str = "default",
        test_cases: Optional[List[TestCase]] = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self._test_cases: List[TestCase] = list(test_cases or [])
        self._model_fn: Optional[Callable[[str], str]] = None

    def add_case(self, test_case: TestCase) -> None:
        """Add a test case to the suite."""
        self._test_cases.append(test_case)

    def add_cases(self, *test_cases: TestCase) -> None:
        """Add multiple test cases."""
        self._test_cases.extend(test_cases)

    @property
    def test_cases(self) -> List[TestCase]:
        """Return the list of test cases."""
        return list(self._test_cases)

    def set_model_fn(self, fn: Callable[[str], str]) -> None:
        """Set a custom model invocation function.

        The function receives a prompt string and returns a response string.
        """
        self._model_fn = fn

    def run(
        self,
        model: Optional[str] = None,
        model_fn: Optional[Callable[[str], str]] = None,
    ) -> BenchmarkRun:
        """Run all test cases and return a ``BenchmarkRun``.

        Args:
            model: Model identifier string (stored in the run metadata).
            model_fn: Optional callable ``(prompt) -> response``. If not provided,
                uses the suite's default model function or raises.

        Returns:
            A populated ``BenchmarkRun``.
        """
        fn = model_fn or self._model_fn
        if fn is None:
            raise ValueError(
                "No model function provided. Pass model_fn to run() or set one "
                "via set_model_fn()."
            )

        results: List[TestResult] = []

        for tc in self._test_cases:
            start = time.perf_counter()
            try:
                actual = fn(tc.input)
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000
                results.append(
                    TestResult(
                        test_name=tc.name,
                        passed=False,
                        reason=f"Model call failed: {exc}",
                        latency_ms=latency,
                        actual_output="",
                    )
                )
                continue

            latency = (time.perf_counter() - start) * 1000

            if tc.evaluator is not None:
                passed, reason = tc.evaluator(tc.input, actual)
            elif tc.expected is not None:
                passed = tc.expected.strip().lower() in actual.strip().lower()
                reason = (
                    f"Expected substring: {tc.expected!r}"
                    if passed
                    else f"Expected substring {tc.expected!r} not found in output"
                )
            else:
                # No evaluator and no expected — just record the output
                passed = True
                reason = "No expected value set — recorded only"

            results.append(
                TestResult(
                    test_name=tc.name,
                    passed=passed,
                    reason=reason,
                    latency_ms=latency,
                    actual_output=actual,
                )
            )

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        pass_rate = (passed_count / total * 100) if total > 0 else 0.0
        avg_latency = (
            sum(r.latency_ms for r in results) / total if total > 0 else 0.0
        )

        return BenchmarkRun(
            name=self.name,
            model=model or "",
            test_cases=self._test_cases,
            results=results,
            pass_rate=pass_rate,
            avg_latency=avg_latency,
            total=total,
            passed=passed_count,
        )

    @classmethod
    def from_file(cls, path: Path) -> "BenchmarkSuite":
        """Load a benchmark suite from a JSON or YAML file.

        Expected format (JSON)::

            {
                "name": "my-suite",
                "description": "...",
                "test_cases": [
                    {"name": "test1", "input": "...", "expected": "..."},
                    ...
                ]
            }
        """
        raw: Dict[str, Any] = {}
        if path.suffix in (".yaml", ".yml"):
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        else:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

        cases = []
        for c in raw.get("test_cases", []):
            cases.append(
                TestCase(
                    name=c["name"],
                    input=c["input"],
                    expected=c.get("expected"),
                    metadata=c.get("metadata", {}),
                )
            )

        return cls(
            name=raw.get("name", path.stem),
            test_cases=cases,
            description=raw.get("description", ""),
        )


# ── run_benchmark ─────────────────────────────────────────────────────────────


def run_benchmark(
    name: str,
    test_cases: List[TestCase],
    model: str,
    model_fn: Callable[[str], str],
) -> BenchmarkRun:
    """Run a benchmark with the given test cases against a model.

    This is a convenience wrapper around ``BenchmarkSuite.run()``.

    Args:
        name: Benchmark name.
        test_cases: List of ``TestCase`` objects.
        model: Model identifier.
        model_fn: Callable ``(prompt) -> response``.

    Returns:
        A ``BenchmarkRun`` with populated results.
    """
    suite = BenchmarkSuite(name=name, test_cases=test_cases)
    return suite.run(model=model, model_fn=model_fn)


# ── compare_runs ──────────────────────────────────────────────────────────────


def compare_runs(run1: BenchmarkRun, run2: BenchmarkRun) -> Dict[str, Any]:
    """Compare two benchmark runs and return a diff summary.

    Returns a dict with:
        - run1 / run2: basic info about each run
        - pass_rate_diff: pass_rate_1 - pass_rate_2
        - latency_diff_ms: avg_latency_1 - avg_latency_2
        - regressions: list of tests that passed in run1 but failed in run2
        - improvements: list of tests that failed in run1 but passed in run2
    """
    results1 = {r.test_name: r for r in run1.results}
    results2 = {r.test_name: r for r in run2.results}

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []

    all_names = set(results1.keys()) | set(results2.keys())

    for name in sorted(all_names):
        r1 = results1.get(name)
        r2 = results2.get(name)
        if r1 is None and r2 is not None:
            if r2.passed:
                improvements.append(
                    {"test_name": name, "detail": "New test in run2 — passed"}
                )
            continue
        if r2 is None and r1 is not None:
            if r1.passed:
                regressions.append(
                    {"test_name": name, "detail": "Removed in run2 — was passing"}
                )
            continue
        if r1 and r2 and r1.passed and not r2.passed:
            regressions.append(
                {
                    "test_name": name,
                    "detail": f"Was passing, now failing: {r2.reason}",
                    "old_latency_ms": r1.latency_ms,
                    "new_latency_ms": r2.latency_ms,
                }
            )
        if r1 and r2 and not r1.passed and r2.passed:
            improvements.append(
                {
                    "test_name": name,
                    "detail": f"Was failing, now passing: {r1.reason}",
                    "old_latency_ms": r1.latency_ms,
                    "new_latency_ms": r2.latency_ms,
                }
            )

    return {
        "run1": {
            "name": run1.name,
            "date": run1.date,
            "model": run1.model,
            "pass_rate": run1.pass_rate,
            "avg_latency_ms": run1.avg_latency,
            "total": run1.total,
        },
        "run2": {
            "name": run2.name,
            "date": run2.date,
            "model": run2.model,
            "pass_rate": run2.pass_rate,
            "avg_latency_ms": run2.avg_latency,
            "total": run2.total,
        },
        "pass_rate_diff": round(run1.pass_rate - run2.pass_rate, 2),
        "latency_diff_ms": round(run1.avg_latency - run2.avg_latency, 2),
        "regressions": regressions,
        "improvements": improvements,
    }


# ── Leaderboard ───────────────────────────────────────────────────────────────


def _iter_saved_runs() -> List[Tuple[BenchmarkRun, Path]]:
    """Iterate over all saved benchmark runs on disk."""
    if not BENCHMARK_RUNS_DIR.is_dir():
        return []
    results: List[Tuple[BenchmarkRun, Path]] = []
    for f in sorted(BENCHMARK_RUNS_DIR.iterdir()):
        if f.suffix == ".json":
            try:
                run = BenchmarkRun.load(f)
                results.append((run, f))
            except Exception:
                pass
    return results


def get_leaderboard() -> List[Dict[str, Any]]:
    """Compute a leaderboard from all saved benchmark runs.

    Returns list of dicts sorted by pass rate descending, then latency ascending.
    Each entry contains: model, run_name, date, pass_rate, avg_latency_ms, total.
    """
    entries: List[Dict[str, Any]] = []
    for run, _path in _iter_saved_runs():
        entries.append(
            {
                "model": run.model or "unknown",
                "run_name": run.name,
                "date": run.date,
                "pass_rate": run.pass_rate,
                "avg_latency_ms": run.avg_latency,
                "total": run.total,
                "passed": run.passed,
            }
        )
    # Sort: highest pass rate first, then lowest latency
    entries.sort(key=lambda e: (-e["pass_rate"], e["avg_latency_ms"]))
    return entries


def print_leaderboard() -> str:
    """Return a formatted leaderboard string.

    Uses a simple table format (Rich not required).
    """
    entries = get_leaderboard()
    if not entries:
        return "No benchmark runs found. Run `openamer eval run <suite>` first."

    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  BENCHMARK LEADERBOARD")
    lines.append("=" * 100)
    lines.append(
        f"{'Rank':<5} {'Model':<25} {'Suite':<25} {'Pass Rate':<10} {'Avg Latency':<14} {'Tests'}"
    )
    lines.append("-" * 100)
    for i, entry in enumerate(entries, 1):
        lines.append(
            f"{i:<5} {entry['model']:<25} {entry['run_name']:<25} "
            f"{entry['pass_rate']:>6.1f}%   "
            f"{entry['avg_latency_ms']:>8.1f}ms   "
            f"{entry['passed']}/{entry['total']}"
        )
    lines.append("=" * 100)
    return "\n".join(lines)