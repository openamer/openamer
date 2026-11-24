# Blocked-outreach fallback: verify + fix instead of retrying gates

When the outreach cron finds **every** channel shut (comments still work but are
one-per-run by design; posts BAD_CAPTCHA; Dev.to/Medium/Hashnode/HN/IH/LinkedIn
credential- or tier-gated), do NOT run a retry-loop and do NOT close the run with
"nothing to do". The productive, honest fallback is: **make the deliverable's
claims true.** A measured defect in a feature the launch copy advertises is a
stronger future post angle than the original text, and it is the only real
progress available while the gates hold.

Proven 09.10.2026 (evening run): Reddit live, everything else gated → found and
fixed 2 real bugs in `openamer-agent/scripts/benchmark.py` that the canonical home
suite already had pinned as red.

## 1. Run the canonical home suite (OPENAMER_HOME, not the source repo)

`OPENAMER_HOME` (`C:\Users\damir\AppData\Local\openamer-laptop`) is an install
tree with its OWN `pytest.ini`:

```
[pytest]
testpaths = scripts/tests       # scripts/ standalone *_test.py diagnostics are NOT collected
python_files = test_*.py
addopts = -q
```

So a bare `pytest` from the home dir **is** the full suite for this tree.
Run it **serially** — `-n32`/xdist hangs silently on this host (a single file with
`-n32` never returns):

```bash
cd C:/Users/damir/AppData/Local/openamer-laptop
./venv/Scripts/python.exe -m pytest -p no:xdist -q            # full home suite
./venv/Scripts/python.exe -m pytest scripts/tests/<file>.py -p no:xdist -q
```

- `--timeout=30` is NOT installed → `unrecognized arguments`. Use the `timeout`
  shell builtin around the whole call for a bound instead.
- The agent venv (`openamer-agent/venv`) has **no pytest**; use the home `./venv`.
  To run `openamer-agent/tests/*` you must point HOME's python at it:
  `PYTHONPATH=<openamer-agent> ../venv/Scripts/python.exe -m pytest tests/scripts`.
  That surface is large and has many pre-existing red tests — bound it and do not
  report it as green if you truncated it.

## 2. Read the failing test: it names the target module AND the exact bug

`scripts/tests/*.py` usually `importlib`-load a module by absolute path, e.g.
`openamer-agent/scripts/benchmark.py`, and mock the network. The test docstring is
the bug report. Fix at the single read/write site, closing the whole bug class.

Two real defects fixed this run (both pre-existing, Oct-5 dated — unrelated to the
outreach turn itself):
- **Schema split → frozen time-series.** File written under `{"history": [...]}`,
  but the cron path did `all_results = load_results(); all_results["runs"].append(...)`
  → `KeyError: 'runs'` on every `--cron` run, so the capability series never grew.
  Fix: normalize in `load_results()` (`runs = data.get("runs", data.get("history", []))`,
  return both keys), `save_results()` keeps `history` in sync; guard `json.JSONDecodeError/OSError`.
- **Unguarded null content.** `resp["choices"][0]["message"]["content"].strip()` on a
  reasoning model that returns `content=None` raised → the `except` reported
  `{"correct": None}` instead of `False`. Fix: `(…get("content") or "").strip().lower()`.

## 3. Prove it three ways before reporting

```bash
./venv/Scripts/python.exe -m pytest scripts/tests/test_<x>.py -p no:xdist -q   # target: was RED -> GREEN
./venv/Scripts/python.exe -m pytest -p no:xdist -q                              # full suite: no regressions
~/.local/bin/ruff.exe check <changed-file>                                      # E9,F63,F7,F82 + full = clean
```
Then **E2E against the live artifact**, not just the unit mock — import the real
module and exercise the live store read-only:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bm", "openamer-agent/scripts/benchmark.py")
m = importlib.util.module_from_spec(spec); sys.modules["bm"] = m; spec.loader.exec_module(m)
d = m.load_results()                 # live memory/benchmarks.json
assert d["runs"] == d["history"]; d["runs"].append({"ts": "probe"})   # append-safe
m.report()                           # renders
```

## 4. Log the fallback in the visibility ledger

Add rows to `memory/si/visibility_log.jsonl` for the fallback too (platform
`repo`/`verify_readme` + a `skill`/`fix_*` row is the established shape), so the
next run sees that a real fix landed instead of assuming the run was empty.

## 5. Third bug class (13.10.2026): a stale assertion on a RENAMED private helper

The red test was `scripts/tests/test_tool_server_keepalive.py::test_module_loads`,
asserting `hasattr(mod, "main") and hasattr(mod, "_alive")`. The module had been
rewritten **the same day** (its docstring cites 13.10.26) and its liveness predicate
is now `_healthy` — so the assertion was a change-detector on a private name that no
longer existed, not a functional defect.

**The four checks that settle "stale test" vs "real regression" — do them before fixing:**

1. **Is the name consumed outside the test?** `grep -rn "_alive\b" scripts/ …`. Here the only
   consumer was the test; the cron job runs the script as a process → `main()` (confirm in
   `cron/jobs.json`: it listed `"script": "tool_server_keepalive.py"`, no `_alive`). A name with
   no production consumer is a naming detail, not a broken contract.
2. **What does the sibling family do?** The module docstring says it mirrors `a2a_keepalive.py` /
   `si_core_watchdog.py`; those define `_alive()` / `alive()`. Naming *drift* is real — but check
   semantics before "unifying": `a2a_keepalive._alive()` is a **bare TCP connect**, while
   `tool_server_keepalive._healthy()` deliberately validates the canonical `/health` **shape**
   (a bare TCP check lets a deprecated squatter survive forever). Same family, stricter predicate
   ⇒ do NOT rename it back; the test is what's stale.
3. **Does the file exist in the upstream repo?** `ls <repo>/scripts/ | grep -i keepalive` →
   **NO repo copy**. Both the module and its test exist ONLY in `OPENAMER_HOME` (`find` → exactly
   1 copy each). So the user's "root-cause upstream + PR" order is **not applicable** — say that
   plainly instead of promising a PR you cannot open.
4. **Was it RED for a reason?** The test's sibling assertions (`PORT == 8081`, `SCRIPT.name ==
   "tool_server.py"`, `TRAINING_VENV`) all passed — only the name assertion failed. An isolated
   name failure next to passing behaviour assertions is the signature of a rename, not a regression.

**Fix shape:** assert the module's real contract with `callable(getattr(...))`, and leave a
comment pinning *why* the name differs, so a future "consistency" refactor does not rename it back
and re-break the test:
```python
def test_module_loads():
    mod = _load()
    assert callable(getattr(mod, "main", None))
    # _healthy, deliberately NOT a2a_keepalive's `_alive`: a bare TCP check is not
    # enough here — a deprecated squatter satisfies it and survives forever.
    assert callable(getattr(mod, "_healthy", None))
```
Check EOLs before editing (`crlf`/`lf` counts via a `rb` read) so the patch does not flip line
endings on a whole file.

## 6. E2E for a watchdog/keepalive module: import it and probe LIVE

`importlib`-load the real module and call its read-only predicates against the running service —
that proves the *shipped* wiring, not just the test's mocks:
```python
m = ...  # spec_from_file_location(...) on scripts/tool_server_keepalive.py
print(m.PORT, m.SCRIPT.exists(), m.CANONICAL_HEALTH_KEY)   # 8081, True, 'tools'
print(m._healthy(), m._port_open(), len(m._owners()))      # True True 1  <- live :8081, read-only
```
Measured 13.10.2026: target 4 passed `rc=0`; full home suite **239 passed `rc=0`** (was 1 failed);
`ruff check` → *All checks passed*; E2E `_healthy()=True` against the live `:8081`. Note the
predicate doubles as a service health check — a green E2E here also confirms the served core is up.

