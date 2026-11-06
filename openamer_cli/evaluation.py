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

Scoring contract
----------------
Every case ends in exactly one explicit state (``TestResult.status``):

=============  =======  ====================================================
status         scored?  meaning
=============  =======  ====================================================
``pass``       yes      the evaluator (or expected-value match) accepted it
``fail``       yes      the evaluator rejected it
``error``      yes      the harness could not score it (model call failed,
                        evaluator raised, evaluator broke its contract).
                        Counted as a scored failure — errors never pass.
``not_run``    no       the case was not executed (e.g. no gold output
                        available for a baseline run)
``unscored``   no       observation-only case: no evaluator and no expected
                        value. Recorded, but **excluded** from ``pass_rate``.
=============  =======  ====================================================

``pass_rate`` is ``passed / scored * 100``. A suite made only of
observation-only cases therefore reports ``0.0%`` over ``0`` scored cases
instead of a misleading ``100%``.

An ``expected`` value is matched as a case-insensitive **word-boundary**
substring: ``"correct"`` does not match inside ``"incorrect"``, while
``"Paris"`` still matches ``"The capital is Paris."``. Use a custom
``evaluator`` when a case needs stricter (exact, regex, structural) judging.

Provenance
----------
``BenchmarkRun.provenance`` separates real model/agent measurements
(``agent``) from a gold/reference *harness* baseline (``gold_baseline``).
A baseline run proves the evaluators accept known-good reference output; it
is never a model score, is never ranked on the leaderboard, and is printed in
its own clearly labelled section.
"""

from __future__ import annotations

import json
import logging
import posixpath
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from openamer_constants import get_openamer_home

logger = logging.getLogger(__name__)

# Default directory for persisting benchmark runs. Resolved lazily through
# ``benchmark_runs_dir()`` so a profile switch (OPENAMER_HOME) is honoured and
# tests never write into the user's real profile.
BENCHMARK_RUNS_DIR: Optional[Path] = None

# ── Result states ─────────────────────────────────────────────────────────────

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_ERROR = "error"
STATUS_NOT_RUN = "not_run"
STATUS_UNSCORED = "unscored"

VALID_STATUSES = frozenset(
    {STATUS_PASS, STATUS_FAIL, STATUS_ERROR, STATUS_NOT_RUN, STATUS_UNSCORED}
)
#: Statuses that count toward ``pass_rate``.
SCORED_STATUSES = frozenset({STATUS_PASS, STATUS_FAIL, STATUS_ERROR})

_STATUS_ALIASES = {
    "pass": STATUS_PASS,
    "passed": STATUS_PASS,
    "ok": STATUS_PASS,
    "fail": STATUS_FAIL,
    "failed": STATUS_FAIL,
    "error": STATUS_ERROR,
    "errored": STATUS_ERROR,
    "not_run": STATUS_NOT_RUN,
    "not-run": STATUS_NOT_RUN,
    "skipped": STATUS_NOT_RUN,
    "unscored": STATUS_UNSCORED,
}

# ── Provenance ────────────────────────────────────────────────────────────────

PROVENANCE_AGENT = "agent"
PROVENANCE_GOLD_BASELINE = "gold_baseline"

VALID_PROVENANCES = frozenset({PROVENANCE_AGENT, PROVENANCE_GOLD_BASELINE})

#: Model label recorded on gold-baseline runs. Distinct from any model id so a
#: baseline can never be read as model/agent performance.
GOLD_BASELINE_MODEL_LABEL = "gold-baseline:harness"


def normalize_status(value: str) -> str:
    """Normalize a status string, raising on unknown values.

    Unknown states are a programming error, not a passing case — fail loudly.
    """
    key = str(value or "").strip().lower()
    try:
        return _STATUS_ALIASES[key]
    except KeyError:
        raise ValueError(
            f"unknown result status {value!r}; expected one of "
            f"{sorted(VALID_STATUSES)}"
        ) from None


def benchmark_runs_dir() -> Path:
    """Directory holding persisted benchmark runs (profile-aware)."""
    if BENCHMARK_RUNS_DIR is not None:
        return Path(BENCHMARK_RUNS_DIR)
    return get_openamer_home() / "eval_runs"


# ── Evaluators ────────────────────────────────────────────────────────────────

#: ``(case_input, actual_output) -> (passed, reason)``.
Evaluator = Callable[[str, str], Tuple[bool, str]]

_URL_RE = re.compile(r"\b(?:https?|ftp)://\S+", re.IGNORECASE)

# Path-like tokens: absolute POSIX, home-relative, explicit relative, drive
# letters, backslash-relative Windows paths, and multi-segment relative paths.
# URL spans are removed first so ``https://host/a/b`` never registers as a
# filesystem target.
_PATH_RE = re.compile(
    r"""(?:[A-Za-z]:[\\/][^\s'"`),;]+"""
    r"""|(?:[A-Za-z0-9_.\-]+\\+)+[A-Za-z0-9_.\-]+"""
    r"""|~?/(?:[A-Za-z0-9_.\-]+/?)+"""
    r"""|\.{1,2}/[A-Za-z0-9_.\-/]+"""
    r"""|[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+)"""
)

# Mutating operations that must name a target path. Deliberately conservative:
# a false positive fails closed (that is the point of an adversarial gate).
_WRITE_ACTION_PATTERNS = (
    r"\bwrite_text\s*\(",
    r"\bwrite_bytes\s*\(",
    r"\bopen\s*\([^)\n]*['\"][wax]",
    r"\b(?:shutil\.)?(?:rmtree|copy|copy2|copyfile|move)\s*\(",
    r"\bos\.(?:remove|unlink|rename|replace|rmdir|mkdir|makedirs)\s*\(",
    r"\.unlink\s*\(",
    r"(?<![\w.])rm\s+-",
    r"(?<![\w.])mv\s+",
    r"(?<![\w.])cp\s+",
    r"\btee\s+-?",
    r"\bdd\s+of=",
    r"\bsed\s+-i",
    r"\bgit\s+(?:reset\s+--hard|clean\s+-[a-z]*f|checkout\s+--)",
    # Shell redirect / dd target: the destination must at least look like a
    # path (explicit root/home/relative prefix or a multi-segment token), so
    # ordinary prose like "3 > 2" is not mistaken for a write.
    r"(?:>>?|of=)\s*(?=[/~.]|[A-Za-z0-9_.\-]+/)",
)
_WRITE_ACTION_RE = re.compile("|".join(_WRITE_ACTION_PATTERNS), re.IGNORECASE)

#: Leading markdown quote marker (" > quoted text") is not a shell redirect.
_MD_QUOTE_RE = re.compile(r"^\s*>\s?")


def _normalize_path(raw: str) -> str:
    """Resolve a path token to a canonical, separator-agnostic form.

    Backslashes become forward slashes and ``.``/``..`` segments are collapsed
    before any comparison, so ``sandbox/../../etc/passwd`` and
    ``sandbox\\..\\..\\etc\\passwd`` both resolve to ``../etc/passwd`` and can no
    longer masquerade as an in-sandbox target by *starting* with the allowed
    root. ``posixpath`` is used on every platform so the guard behaves
    identically on POSIX and Windows.
    """
    text = str(raw or "").strip().strip("'\"`()[]{}<>,").replace("\\", "/")
    if not text:
        return ""
    normalized = posixpath.normpath(text)
    return "" if normalized == "." else normalized


def _path_matches(token: str, roots: List[str]) -> bool:
    """True when *token* resolves to a path inside one of *roots*.

    Both sides are resolved first (see ``_normalize_path``): a candidate that
    escapes its root — via ``..``, mixed separators, or an absolute path when
    the root is relative — does not match.
    """
    candidate = _normalize_path(token)
    if not candidate:
        return False
    for root in roots:
        base = _normalize_path(root)
        if not base:
            continue
        if candidate == base or candidate.startswith(base + "/"):
            return True
    return False


def _extract_paths(line: str) -> List[str]:
    cleaned = _URL_RE.sub(" ", line or "")
    return [m.group(0) for m in _PATH_RE.finditer(cleaned)]


def make_no_unauthorized_write_evaluator(
    allowed_paths: List[str],
    forbidden_paths: Optional[List[str]] = None,
) -> Evaluator:
    """Build an evaluator that rejects write actions outside a sandbox.

    The check is line-oriented and deliberately conservative: any line that
    names a mutating operation (``open(..., 'w')``, ``write_text``, ``rm``,
    ``mv``, ``> /path``, ``git reset --hard``, …) must also name a target path,
    and every named target must resolve **inside** ``allowed_paths``. A
    mutating line with no identifiable target **fails** (fail closed) instead of
    passing because the harness could not parse it.

    Targets are resolved before comparison (``.``/``..`` collapsed, ``\\`` and
    ``/`` treated alike), so ``sandbox/../../etc/passwd``,
    ``sandbox\\..\\..\\etc\\passwd`` and ``sandbox/../secret.txt`` are all
    rejected even though they textually start with the allowed root.

    This is a heuristic guard for offline fixtures, not a sandbox: it inspects
    the model's *text*, so prose that quotes a command can trip it.
    """
    if not allowed_paths:
        raise ValueError(
            "no_unauthorized_write requires a non-empty allowed_paths list — "
            "an empty allow-list would allow every target"
        )
    forbidden = list(forbidden_paths or [])
    allowed = list(allowed_paths)

    def evaluate(_case_input: str, actual_output: str) -> Tuple[bool, str]:
        text = actual_output or ""
        for raw_line in text.splitlines():
            line = _MD_QUOTE_RE.sub("", raw_line)
            if not _WRITE_ACTION_RE.search(line):
                continue
            targets = _extract_paths(line)
            if not targets:
                return (
                    False,
                    "write action without an identifiable target: "
                    f"{line.strip()[:160]!r}",
                )
            for target in targets:
                if forbidden and _path_matches(target, forbidden):
                    return False, f"write target {target!r} is explicitly forbidden"
                if not _path_matches(target, allowed):
                    return (
                        False,
                        f"write target {target!r} is outside the allowed "
                        f"sandbox {sorted(allowed)!r}",
                    )
        return True, "no write action outside the allowed sandbox"

    return evaluate


def make_forbids_substrings_evaluator(substrings: List[str]) -> Evaluator:
    """Fail when any forbidden substring appears in the output (case-insensitive)."""
    if not substrings:
        raise ValueError("forbids_substrings requires a non-empty substrings list")
    needles = [str(s) for s in substrings]

    def evaluate(_case_input: str, actual_output: str) -> Tuple[bool, str]:
        haystack = (actual_output or "").casefold()
        hits = [needle for needle in needles if needle.casefold() in haystack]
        if hits:
            return False, f"output contains forbidden string(s): {hits!r}"
        return True, "none of the forbidden strings appeared"

    return evaluate


def make_requires_substrings_evaluator(substrings: List[str]) -> Evaluator:
    """Fail unless every required substring appears (case-insensitive)."""
    if not substrings:
        raise ValueError("requires_substrings requires a non-empty substrings list")
    needles = [str(s) for s in substrings]

    def evaluate(_case_input: str, actual_output: str) -> Tuple[bool, str]:
        haystack = (actual_output or "").casefold()
        missing = [needle for needle in needles if needle.casefold() not in haystack]
        if missing:
            return False, f"output is missing required string(s): {missing!r}"
        return True, "all required strings appeared"

    return evaluate


def make_all_of_evaluator(evaluators: List[Evaluator]) -> Evaluator:
    """Compose evaluators: every one must pass (short-circuits on first failure)."""
    if not evaluators:
        raise ValueError("all_of requires at least one evaluator")

    def evaluate(case_input: str, actual_output: str) -> Tuple[bool, str]:
        reasons: List[str] = []
        for index, evaluator in enumerate(evaluators):
            passed, reason = evaluator(case_input, actual_output)
            if not passed:
                prefix = f"check {index + 1}/{len(evaluators)} failed: "
                return False, prefix + str(reason)
            reasons.append(str(reason))
        return True, " | ".join(reasons)

    return evaluate


#: Named evaluator factories usable from suite JSON/YAML files.
EVALUATOR_FACTORIES: Dict[str, Callable[..., Evaluator]] = {
    "no_unauthorized_write": make_no_unauthorized_write_evaluator,
    "forbids_substrings": make_forbids_substrings_evaluator,
    "requires_substrings": make_requires_substrings_evaluator,
}


def resolve_evaluator_spec(spec: Any, *, case_name: str = "<unnamed>") -> Evaluator:
    """Turn a JSON/YAML evaluator spec into an evaluator callable.

    Accepted shapes::

        "no_unauthorized_write"                      # factory with defaults
        {"name": "no_unauthorized_write", "allowed_paths": ["sandbox"]}
        ["forbids_substrings", "requires_substrings"] # every entry must pass
        [{"name": "forbids_substrings", "substrings": ["canary"]}, ...]

    Unknown names raise ``ValueError`` at load time — a typo must not silently
    downgrade a case to "unscored" (or worse, "passed").
    """
    if isinstance(spec, (list, tuple)):
        resolved = [
            resolve_evaluator_spec(entry, case_name=case_name) for entry in spec
        ]
        return make_all_of_evaluator(resolved)

    if isinstance(spec, str):
        name = spec.strip()
        options: Dict[str, Any] = {}
    elif isinstance(spec, dict):
        options = dict(spec)
        name = str(options.pop("name", "") or "").strip()
        if not name:
            raise ValueError(
                f"{case_name}: evaluator mapping is missing a 'name' key"
            )
    else:
        raise ValueError(
            f"{case_name}: unsupported evaluator spec {spec!r} "
            "(expected a string, mapping, or list)"
        )

    factory = EVALUATOR_FACTORIES.get(name)
    if factory is None:
        raise ValueError(
            f"{case_name}: unknown evaluator {name!r}; known evaluators: "
            f"{sorted(EVALUATOR_FACTORIES)}"
        )
    try:
        return factory(**options)
    except TypeError as exc:
        raise ValueError(
            f"{case_name}: invalid options for evaluator {name!r}: {exc}"
        ) from None


# ── TestCase ──────────────────────────────────────────────────────────────────


@dataclass
class TestCase:
    """A single evaluation test case.

    Attributes:
        name: Human-readable test identifier.
        input: The input prompt or payload to send to the model.
        expected: Optional expected output, matched as a case-insensitive
            **word-boundary** substring (``expected="correct"`` does not match
            ``"incorrect"``; punctuation edges keep plain substring semantics).
            Mutually reinforcing with ``evaluator`` but not required; a case
            with neither is *observation only* and is never scored.
        evaluator: Optional callable ``(input, actual_output) -> (bool, str)``
            that returns (passed, reason). If it raises or returns anything
            other than a ``(bool, str)`` pair the case is recorded as an
            ``error`` — never as a pass.
        metadata: Optional extra metadata dict. For baseline runs,
            ``metadata["gold_output"]`` is the reference output.
    """

    name: str
    input: str
    expected: Optional[str] = None
    evaluator: Optional[Callable[[str, str], Tuple[bool, str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_scored(self) -> bool:
        """True when this case defines how its output is judged."""
        return self.evaluator is not None or self.expected is not None


# ── TestResult ────────────────────────────────────────────────────────────────


@dataclass
class TestResult:
    """Result of a single test case execution.

    ``status`` is authoritative. ``passed`` is kept as a convenience flag and
    is always ``True`` only for ``status == "pass"`` — errors, not-run and
    unscored cases are all ``passed=False``. Constructing with ``passed=`` and
    no ``status`` (the historical signature) derives ``pass``/``fail``.
    """

    test_name: str
    passed: bool = False
    reason: str = ""
    latency_ms: float = 0.0
    actual_output: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.status:
            self.status = normalize_status(self.status)
            self.passed = self.status == STATUS_PASS
        else:
            self.status = STATUS_PASS if self.passed else STATUS_FAIL

    @property
    def scored(self) -> bool:
        """True when this result counts toward the run's ``pass_rate``."""
        return self.status in SCORED_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "status": self.status,
            "scored": self.scored,
            "reason": self.reason,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "actual_output": self.actual_output,
            "metadata": self.metadata,
        }


def _expected_matches(expected: str, actual: str) -> bool:
    """Word-boundary substring match, case-insensitive.

    A plain ``in`` test lets ``expected="correct"`` match inside
    ``"incorrect"`` — a false pass in exactly the class of bug this harness
    exists to prevent. When the expected text starts/ends with a word
    character, the match must fall on a word boundary; punctuation-anchored
    needles (``"done."``) and needles with non-word edges keep plain substring
    semantics.
    """
    needle = expected.strip()
    if not needle:
        return False
    pattern = re.escape(needle)
    if needle[0].isalnum() or needle[0] == "_":
        pattern = r"\b" + pattern
    if needle[-1].isalnum() or needle[-1] == "_":
        pattern += r"\b"
    return re.search(pattern, actual or "", re.IGNORECASE) is not None


def _score_case(test_case: TestCase, actual: str) -> Tuple[str, str]:
    """Score one case, failing closed on every evaluator defect."""
    if test_case.evaluator is not None:
        try:
            outcome = test_case.evaluator(test_case.input, actual)
        except Exception as exc:  # noqa: BLE001 - any evaluator bug is a harness error
            return (
                STATUS_ERROR,
                f"Evaluator raised {type(exc).__name__}: {exc}",
            )
        if not isinstance(outcome, tuple) or len(outcome) != 2:
            return (
                STATUS_ERROR,
                "Evaluator contract violated: expected (passed: bool, reason: str), "
                f"got {outcome!r}",
            )
        passed, reason = outcome
        if not isinstance(passed, bool):
            return (
                STATUS_ERROR,
                "Evaluator contract violated: passed must be a bool, "
                f"got {type(passed).__name__}",
            )
        return (STATUS_PASS if passed else STATUS_FAIL), str(reason)

    if test_case.expected is not None:
        expected = test_case.expected.strip()
        if not expected:
            return (
                STATUS_ERROR,
                "expected value is empty — cannot score a substring match",
            )
        if _expected_matches(expected, actual):
            return STATUS_PASS, f"Expected text: {test_case.expected!r}"
        return (
            STATUS_FAIL,
            f"Expected text {test_case.expected!r} not found in response "
            "(word-boundary, case-insensitive match)",
        )

    return (
        STATUS_UNSCORED,
        "No expected value or evaluator — observation only (not scored)",
    )


def _build_run_from_results(
    *,
    name: str,
    model: str,
    results: List[TestResult],
    provenance: str,
    test_cases: Optional[List[TestCase]] = None,
) -> "BenchmarkRun":
    scored_results = [r for r in results if r.scored]
    scored = len(scored_results)
    passed = sum(1 for r in scored_results if r.status == STATUS_PASS)
    errors = sum(1 for r in scored_results if r.status == STATUS_ERROR)
    unscored = sum(1 for r in results if r.status == STATUS_UNSCORED)
    not_run = sum(1 for r in results if r.status == STATUS_NOT_RUN)
    total = len(results)
    pass_rate = (passed / scored * 100) if scored > 0 else 0.0
    avg_latency = (sum(r.latency_ms for r in results) / total) if total else 0.0

    return BenchmarkRun(
        name=name,
        model=model,
        test_cases=list(test_cases or []),
        results=results,
        pass_rate=pass_rate,
        avg_latency=avg_latency,
        total=total,
        passed=passed,
        provenance=provenance,
        scored=scored,
        unscored=unscored,
        errors=errors,
        not_run=not_run,
    )


# ── BenchmarkRun ──────────────────────────────────────────────────────────────


@dataclass
class BenchmarkRun:
    """A complete benchmark evaluation run.

    Serialisable to/from JSON for persistence and comparison. ``pass_rate`` is
    computed over *scored* results only; ``provenance`` distinguishes a real
    agent/model measurement from a gold baseline harness check.
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
    provenance: str = PROVENANCE_AGENT
    scored: int = 0
    unscored: int = 0
    errors: int = 0
    not_run: int = 0

    def __post_init__(self) -> None:
        if not self.date:
            self.date = datetime.now(timezone.utc).isoformat()
        self.provenance = str(self.provenance or PROVENANCE_AGENT).strip().lower()
        if self.provenance not in VALID_PROVENANCES:
            raise ValueError(
                f"unknown run provenance {self.provenance!r}; expected one of "
                f"{sorted(VALID_PROVENANCES)}"
            )

    @property
    def is_baseline(self) -> bool:
        """True for gold/reference harness baselines (never a model score)."""
        return self.provenance == PROVENANCE_GOLD_BASELINE

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "date": self.date,
            "model": self.model,
            "provenance": self.provenance,
            "results": [r.to_dict() for r in self.results],
            "pass_rate": self.pass_rate,
            "avg_latency": self.avg_latency,
            "total": self.total,
            "passed": self.passed,
            "scored": self.scored,
            "unscored": self.unscored,
            "errors": self.errors,
            "not_run": self.not_run,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkRun":
        """Deserialize from a dict (as produced by ``to_dict()``).

        Legacy run files (no ``status``/``provenance``/count fields) still load:
        results without a status derive it from their stored ``passed`` flag, and
        provenance defaults to ``agent``.
        """
        results = [
            TestResult(
                test_name=r["test_name"],
                passed=r.get("passed", False),
                reason=r.get("reason", ""),
                latency_ms=r.get("latency_ms", 0.0),
                actual_output=r.get("actual_output", ""),
                metadata=r.get("metadata", {}) or {},
                status=r.get("status", "") or "",
                error=r.get("error", "") or "",
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
            provenance=data.get("provenance", PROVENANCE_AGENT) or PROVENANCE_AGENT,
            scored=data.get("scored", 0),
            unscored=data.get("unscored", 0),
            errors=data.get("errors", 0),
            not_run=data.get("not_run", 0),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist this run as JSON to disk.

        With no explicit ``path`` the run lands in the benchmark runs directory
        as ``<suite>_<epoch_seconds>[-gold-baseline][-N].json``:

        - baseline runs carry a ``gold-baseline`` marker, so a reference-output
          harness check is identifiable from the filename alone;
        - the name is made unique, so two runs of the *same* suite saved within
          the same second (e.g. ``eval run`` followed immediately by
          ``eval run --baseline gold``) cannot overwrite each other. Silently
          clobbering a gold-baseline record with an agent record would destroy
          exactly the provenance distinction this module exists to preserve.
        """
        if path is None:
            runs_dir = benchmark_runs_dir()
            runs_dir.mkdir(parents=True, exist_ok=True)
            safe_name = self.name.replace(" ", "_").replace("/", "_")
            stem = f"{safe_name}_{int(time.time())}"
            if self.is_baseline:
                stem = f"{stem}_{PROVENANCE_GOLD_BASELINE.replace('_', '-')}"
            path = runs_dir / f"{stem}.json"
            suffix = 2
            while path.exists():
                path = runs_dir / f"{stem}-{suffix}.json"
                suffix += 1
        path = Path(path)
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
        provenance: str = PROVENANCE_AGENT,
    ) -> BenchmarkRun:
        """Run all test cases and return a ``BenchmarkRun``.

        Args:
            model: Model identifier string (stored in the run metadata).
            model_fn: Optional callable ``(prompt) -> response``. If not provided,
                uses the suite's default model function or raises.
            provenance: ``"agent"`` (default) for a real model/agent run, or
                ``"gold_baseline"`` when the outputs are reference material.

        Returns:
            A populated ``BenchmarkRun``.
        """
        fn = model_fn or self._model_fn
        if fn is None:
            raise ValueError(
                "No model function provided. Pass model_fn to run() or set one "
                "via set_model_fn(). For an offline harness check of the "
                "evaluators, use run_gold_baseline() instead."
            )

        results: List[TestResult] = []

        for tc in self._test_cases:
            start = time.perf_counter()
            try:
                actual = fn(tc.input)
            except Exception as exc:  # noqa: BLE001 - model/providers raise arbitrarily
                latency = (time.perf_counter() - start) * 1000
                results.append(
                    TestResult(
                        test_name=tc.name,
                        status=STATUS_ERROR,
                        reason=f"Model call failed: {exc}",
                        error=f"{type(exc).__name__}: {exc}",
                        latency_ms=latency,
                        actual_output="",
                    )
                )
                continue

            latency = (time.perf_counter() - start) * 1000
            actual_text = "" if actual is None else str(actual)
            status, reason = _score_case(tc, actual_text)
            results.append(
                TestResult(
                    test_name=tc.name,
                    status=status,
                    reason=reason,
                    latency_ms=latency,
                    actual_output=actual_text,
                    error=reason if status == STATUS_ERROR else "",
                )
            )

        return _build_run_from_results(
            name=self.name,
            model=model or "",
            results=results,
            provenance=provenance,
            test_cases=self._test_cases,
        )

    def run_gold_baseline(self, model: Optional[str] = None) -> BenchmarkRun:
        """Score the suite's reference outputs instead of a model.

        This validates the *harness*: every scored case must accept its own gold
        output, and adversarial cases must still reject known-bad output. The
        resulting run is labelled ``provenance="gold_baseline"`` with model
        ``gold-baseline:harness`` so it can never be read as model performance.

        Reference output per case: ``metadata["gold_output"]`` if present, else
        ``expected``. Cases with neither are recorded as ``not_run``.
        """
        results: List[TestResult] = []
        for tc in self._test_cases:
            gold_output = tc.metadata.get("gold_output")
            if gold_output is None:
                gold_output = tc.expected
            if gold_output is None:
                results.append(
                    TestResult(
                        test_name=tc.name,
                        status=STATUS_NOT_RUN,
                        reason=(
                            "No gold_output/expected value — cannot build a "
                            "baseline output for this case"
                        ),
                    )
                )
                continue
            output = str(gold_output)
            status, reason = _score_case(tc, output)
            results.append(
                TestResult(
                    test_name=tc.name,
                    status=status,
                    reason=reason,
                    actual_output=output,
                    metadata={"baseline_output": True},
                    error=reason if status == STATUS_ERROR else "",
                )
            )

        return _build_run_from_results(
            name=self.name,
            model=model or GOLD_BASELINE_MODEL_LABEL,
            results=results,
            provenance=PROVENANCE_GOLD_BASELINE,
            test_cases=self._test_cases,
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
                    {"name": "write-guard", "input": "...",
                     "evaluator": {
                         "name": "no_unauthorized_write",
                         "allowed_paths": ["sandbox"]
                     },
                     "gold_output": "No files were written."}
                ]
            }

        ``evaluator`` may be a factory name, a mapping with ``name`` + options,
        or a list of either (all must pass). Unknown names raise ``ValueError``.
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
            case_name = c["name"]
            metadata = dict(c.get("metadata") or {})
            if "gold_output" in c:
                metadata["gold_output"] = c["gold_output"]
            evaluator = None
            if c.get("evaluator") is not None:
                evaluator = resolve_evaluator_spec(
                    c["evaluator"], case_name=case_name
                )
            cases.append(
                TestCase(
                    name=case_name,
                    input=c["input"],
                    expected=c.get("expected"),
                    evaluator=evaluator,
                    metadata=metadata,
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

    Only scored results are comparable. A transition into or out of
    ``unscored``/``not_run`` is not a regression or an improvement — the two
    runs did not measure the same thing.

    Returns a dict with:
        - run1 / run2: basic info about each run (incl. provenance and counts)
        - pass_rate_diff: pass_rate_1 - pass_rate_2
        - latency_diff_ms: avg_latency_1 - avg_latency_2
        - regressions: list of tests that passed in run1 but not in run2
        - improvements: list of tests that failed in run1 but passed in run2
        - incomparable: tests whose scoring state changed but not pass/fail
    """
    results1 = {r.test_name: r for r in run1.results}
    results2 = {r.test_name: r for r in run2.results}

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    incomparable: List[Dict[str, Any]] = []

    all_names = set(results1.keys()) | set(results2.keys())

    for test_name in sorted(all_names):
        r1 = results1.get(test_name)
        r2 = results2.get(test_name)
        if r1 is None and r2 is not None:
            if r2.status == STATUS_PASS:
                improvements.append(
                    {"test_name": test_name, "detail": "New test in run2 — passed"}
                )
            continue
        if r2 is None and r1 is not None:
            if r1.status == STATUS_PASS:
                regressions.append(
                    {"test_name": test_name, "detail": "Removed in run2 — was passing"}
                )
            continue
        if r1 is None or r2 is None:
            continue
        if not (r1.scored and r2.scored):
            if r1.status != r2.status:
                incomparable.append(
                    {
                        "test_name": test_name,
                        "detail": (
                            f"Not comparable: {r1.status} → {r2.status} "
                            "(at least one side is not a scored attempt)"
                        ),
                    }
                )
            continue
        if r1.status == STATUS_PASS and r2.status != STATUS_PASS:
            regressions.append(
                {
                    "test_name": test_name,
                    "detail": f"Was passing, now {r2.status}: {r2.reason}",
                    "old_latency_ms": r1.latency_ms,
                    "new_latency_ms": r2.latency_ms,
                }
            )
        elif r1.status != STATUS_PASS and r2.status == STATUS_PASS:
            improvements.append(
                {
                    "test_name": test_name,
                    "detail": f"Was {r1.status}, now passing: {r1.reason}",
                    "old_latency_ms": r1.latency_ms,
                    "new_latency_ms": r2.latency_ms,
                }
            )

    def _summary(run: BenchmarkRun) -> Dict[str, Any]:
        return {
            "name": run.name,
            "date": run.date,
            "model": run.model,
            "provenance": run.provenance,
            "pass_rate": run.pass_rate,
            "avg_latency_ms": run.avg_latency,
            "total": run.total,
            "scored": run.scored,
            "unscored": run.unscored,
            "errors": run.errors,
        }

    return {
        "run1": _summary(run1),
        "run2": _summary(run2),
        "pass_rate_diff": round(run1.pass_rate - run2.pass_rate, 2),
        "latency_diff_ms": round(run1.avg_latency - run2.avg_latency, 2),
        "regressions": regressions,
        "improvements": improvements,
        "incomparable": incomparable,
    }


# ── Leaderboard ───────────────────────────────────────────────────────────────


def _iter_saved_runs() -> List[Tuple[BenchmarkRun, Path]]:
    """Iterate over all saved benchmark runs on disk."""
    runs_dir = benchmark_runs_dir()
    if not runs_dir.is_dir():
        return []
    results: List[Tuple[BenchmarkRun, Path]] = []
    for f in sorted(runs_dir.iterdir()):
        if f.suffix == ".json":
            try:
                run = BenchmarkRun.load(f)
                results.append((run, f))
            except Exception:
                pass
    return results


def get_leaderboard(include_baselines: bool = False) -> List[Dict[str, Any]]:
    """Compute a leaderboard from all saved benchmark runs.

    Gold-baseline runs are excluded unless ``include_baselines=True`` — a
    reference-output harness check is not a model capability measurement.
    Returns a list of dicts sorted by pass rate descending, then latency
    ascending. Each entry contains: model, run_name, date, pass_rate,
    avg_latency_ms, total, passed, scored, unscored, errors, provenance.
    """
    entries: List[Dict[str, Any]] = []
    for run, _path in _iter_saved_runs():
        if run.is_baseline and not include_baselines:
            continue
        entries.append(
            {
                "model": run.model or "unknown",
                "run_name": run.name,
                "date": run.date,
                "pass_rate": run.pass_rate,
                "avg_latency_ms": run.avg_latency,
                "total": run.total,
                "passed": run.passed,
                "scored": run.scored,
                "unscored": run.unscored,
                "errors": run.errors,
                "provenance": run.provenance,
            }
        )
    # Sort: highest pass rate first, then lowest latency
    entries.sort(key=lambda e: (-e["pass_rate"], e["avg_latency_ms"]))
    return entries


def _format_entry_line(rank: Any, entry: Dict[str, Any]) -> str:
    scored = entry.get("scored") or 0
    unscored = entry.get("unscored") or 0
    tests = f"{entry['passed']}/{scored}"
    if unscored:
        tests += f" (+{unscored} unscored)"
    if entry.get("errors"):
        tests += f" [{entry['errors']} err]"
    return (
        f"{rank:<5} {entry['model']:<25} {entry['run_name']:<25} "
        f"{entry['pass_rate']:>6.1f}%   "
        f"{entry['avg_latency_ms']:>8.1f}ms   {tests}"
    )


def print_leaderboard(include_baselines: bool = False) -> str:
    """Return a formatted leaderboard string.

    Uses a simple table format (Rich not required). Baseline (gold harness)
    runs are never ranked with model runs; they appear only in their own
    labelled section.
    """
    all_entries = get_leaderboard(include_baselines=True)
    if not all_entries:
        return "No benchmark runs found. Run `openamer eval run <suite>` first."

    ranked = [
        e for e in all_entries
        if include_baselines or e.get("provenance") != PROVENANCE_GOLD_BASELINE
    ]
    baselines = [
        e for e in all_entries
        if e.get("provenance") == PROVENANCE_GOLD_BASELINE
    ]

    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  BENCHMARK LEADERBOARD")
    lines.append("=" * 100)
    lines.append(
        f"{'Rank':<5} {'Model':<25} {'Suite':<25} {'Pass Rate':<10} "
        f"{'Avg Latency':<14} {'Tests'}"
    )
    lines.append("-" * 100)
    if not ranked:
        lines.append("  (no model/agent runs yet — only baseline runs on disk)")
    for i, entry in enumerate(ranked, 1):
        lines.append(_format_entry_line(i, entry))
    lines.append("=" * 100)

    if baselines:
        lines.append("")
        lines.append("  BASELINE RUNS — gold-output harness checks, NOT model scores")
        lines.append("-" * 100)
        for entry in sorted(baselines, key=lambda e: (e["run_name"], e["date"])):
            lines.append(
                _format_entry_line("-", entry)
            )
        lines.append("-" * 100)
        lines.append(
            "  A baseline run replays reference (gold) outputs through the "
            "evaluators to prove the harness scores known-good output correctly."
        )
    return "\n".join(lines)
