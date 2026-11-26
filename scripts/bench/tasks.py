"""Deterministic task catalog for the OpenAmer self-benchmark.

Every task carries its own verifier, so a "pass" is a computed fact, never an
opinion. No network, no RNG at scoring time: the same catalog scored twice
returns the same verdict for the same model output.

Task kinds map to the capabilities the mission claims:
  arith          -> multi-step numeric reasoning
  string         -> exact transformation under constraints
  json           -> structured output discipline
  code           -> executable Python correctness (assertion-run)
  instruction    -> format compliance (must/must-not constraints)
  retrieval      -> long-context recall from a supplied passage
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import os

def _build_tasks() -> list:
    """Built after the verifier helpers exist, so the lambdas can resolve them."""
    return [
    {
        "id": "arith.chain.v1",
        "kind": "arith",
        "prompt": "Compute ((17 * 23) - 91) / 4. Answer with the single integer only.",
        "check": lambda out: _int_match(out, 75),
    },
    {
        "id": "arith.rate.v1",
        "kind": "arith",
        "prompt": (
            "A worker produces 320 units in 8 hours. After a 15% efficiency gain, "
            "how many units in 10 hours? Answer with the integer only."
        ),
        "check": lambda out: _int_match(out, 460),
    },
    {
        "id": "string.reverse_words.v1",
        "kind": "string",
        "prompt": (
            "Reverse the order of the words in this sentence, keep the words "
            "themselves intact, and output only the result: "
            "'the quiet machine learns at night'"
        ),
        "check": lambda out: _norm(out) == "night at learns machine quiet the",
    },
    {
        "id": "string.count.v1",
        "kind": "string",
        "prompt": (
            "How many times does the letter 'a' appear in the word "
            "'banana_bandana'? Answer with the integer only."
        ),
        "check": lambda out: _int_match(out, 6),
    },
    {
        "id": "json.shape.v1",
        "kind": "json",
        "prompt": (
            'Output ONLY a JSON object with exactly two keys: "name" (string) and '
            '"scores" (array of three integers, descending). Use name "ada" and '
            "the integers 9, 5, 3."
        ),
        "check": _check_json_shape,
    },
    {
        "id": "code.fizzbuzz.v1",
        "kind": "code",
        "prompt": (
            "Write a Python function fizzbuzz(n) that returns a list of strings for "
            "1..n: 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' "
            "for multiples of both, otherwise the number as a string. Output only "
            "the code in one fenced block."
        ),
        "check": lambda out: _run_assertions(
            out,
            "assert fizzbuzz(5) == ['1','2','Fizz','4','Buzz']\n"
            "assert fizzbuzz(15)[-1] == 'FizzBuzz'\n"
            "assert fizzbuzz(3)[2] == 'Fizz'\n"
            "assert fizzbuzz(1) == ['1']\n",
        ),
    },
    {
        "id": "code.dedupe.v1",
        "kind": "code",
        "prompt": (
            "Write a Python function dedupe(items) that removes duplicates while "
            "preserving first-occurrence order, works for mixed hashables, and "
            "returns a list. Output only the code in one fenced block."
        ),
        "check": lambda out: _run_assertions(
            out,
            "assert dedupe([1,2,1,3,2]) == [1,2,3]\n"
            "assert dedupe(['b','a','b']) == ['b','a']\n"
            "assert dedupe([]) == []\n",
        ),
    },
    {
        "id": "instruction.constraints.v1",
        "kind": "instruction",
        "prompt": (
            "Write one sentence about memory. Hard constraints: it must contain the "
            "word 'recall', must NOT contain the letter 'z', and must be at most 12 "
            "words long."
        ),
        "check": _check_instruction,
    },
    {
        "id": "retrieval.needle.v1",
        "kind": "retrieval",
        "prompt": (
            "Passage: 'The vault opened at 04:12. The archivist logged 219 entries "
            "that night. A single copper key was missing, tagged K-7741. The lamps "
            "were refilled before dawn.'\n\n"
            "Question: What is the tag of the missing key? Answer with the tag only."
        ),
        "check": lambda out: "k-7741" in (out or "").lower(),
    },
    {
        "id": "reason.multi_step.v1",
        "kind": "reason",
        "prompt": (
            "Three boxes hold 12, 18 and 30 marbles. Move marbles so all three boxes "
            "hold the same amount, moving as few marbles as possible, and moving only "
            "from fuller to emptier boxes. How many marbles move in total? "
            "Answer with the integer only."
        ),
        "check": lambda out: _int_match(out, 10),
    },
    ]


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _int_match(text: str, expected: int) -> bool:
    """True when the expected integer appears as a number in ``text``.

    Compared numerically, not as a string: string comparison rejects "075" for 75
    and would accept "488" inside "1488" if the separators were stripped first.
    """
    for token in re.findall(r"-?\d+", (text or "").replace(",", "")):
        try:
            if int(token) == expected:
                return True
        except ValueError:
            continue
    return False


def _check_json_shape(text: str) -> bool:
    raw = text or ""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return False
    try:
        d = json.loads(m.group(0))
    except Exception:
        return False
    if set(d.keys()) != {"name", "scores"}:
        return False
    if d.get("name") != "ada":
        return False
    s = d.get("scores")
    if not isinstance(s, list) or len(s) != 3 or not all(isinstance(x, int) for x in s):
        return False
    return s == sorted(s, reverse=True) and s == [9, 5, 3]


def _check_instruction(text: str) -> bool:
    t = (text or "").strip()
    low = t.lower()
    if "recall" not in low:
        return False
    if "z" in low:
        return False
    words = [w for w in re.split(r"\s+", t) if w]
    return 0 < len(words) <= 12


_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*(.*?)```", re.S)


def _extract_code(text: str) -> str:
    m = _CODE_BLOCK.search(text or "")
    return m.group(1) if m else (text or "")


def _run_assertions(text: str, assertions: str) -> bool:
    """Execute model-written code against assertions in an isolated subprocess."""
    code = _extract_code(text)
    if not code.strip():
        return False
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "candidate.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
            fh.write("\n\n")
            fh.write(assertions)
            fh.write("\nprint('ASSERTIONS_PASSED')\n")
        try:
            r = subprocess.run(
                [sys.executable, "-I", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                cwd=td,
            )
        except subprocess.TimeoutExpired:
            return False
        return r.returncode == 0 and "ASSERTIONS_PASSED" in (r.stdout or "")


def by_id(task_id: str):
    for t in TASKS:
        if t["id"] == task_id:
            return t
    raise KeyError(task_id)


TASKS = _build_tasks()
