# Darwin live-rewrite & gate parity

Lessons from keeping the internet-learning loops correct while
`darwin_engine.py --autopilot` rewrites their files live (measured 16.09.26,
while patching the `online_buffer` chrome gates).

## 1. "The autopilot already fixed it" is a PER-FILE verdict, never a whole-fix verdict

Two gates guard every buffered learning:
- extraction gate — `internet_learner._JUNK_RE` (rejects early, saves a 30–160 s read)
- writer gate — `buffer_store._NAV_CHROME` / `is_junk` (covers `active_learn`,
  `online_learning` and any other writer path)

The autopilot may adopt your change in **one** file and substitute its own rule in
the other. Measured on the same leak, same session:

| file | state after the autopilot rewrite | verdict |
|---|---|---|
| `internet_learner.py` | my marker was GONE, yet the extract gate still returned `True` | my edit became redundant |
| `buffer_store.py` | my marker was the ONLY thing catching the leak | the writer edit IS load-bearing — keep it |

Never delete one side of a two-file gate fix on the assumption that the other side
covers it. Prove which side is load-bearing.

## 2. Prove it by stripping the marker in memory

```python
src = open(path, encoding="utf-8").read()
mod = src.replace(MY_MARKER_LINE, "")
assert mod != src, "marker line not found verbatim"
p = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "check", "bs_nomarker.py")
os.makedirs(os.path.dirname(p), exist_ok=True)   # /tmp resolves to C:\tmp on MSYS
open(p, "w", encoding="utf-8").write(mod)
spec = importlib.util.spec_from_file_location("bsx", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.is_junk(LEAK))
# True  -> my entry is redundant, the autopilot's rule covers it
# False -> my entry is load-bearing, KEEP it
```

Two-sided proof that the leak was real and that the fix landed: load the
pre-patch revision (`git show <commit>~1:path > <temp>/old.py`) and the current
one in the **same process**, then compare on the exact leak string. PRE `False` /
CURRENT `True` is the whole result.

**Use an in-process `importlib` load, never a second shell invocation.** The
autopilot rewrites these files mid-session, so shell-level `grep`/`diff` and a
later Python import can observe different revisions.

## 3. Marker-parity probe bugs

- **A bounded regex hides the marker.** `grep -o "explore.\{0,60\}business"`
  returned nothing for a marker a Python `in` test then found — the real span was
  ~90 chars, so the probe's own distance bound hid it. Prove presence with a plain
  substring test (`in`, or `grep -F`), never a bounded `.\{0,N\}` regex.
- **A 0-FP result on the live buffer is NOT sufficient.** The naive short marker
  scored "1 hit, 0 real-prose FPs" on the buffer and then flagged a hand-written
  sentence (`Explore Microsoft products and services to understand the pricing
  model of the API.`). Always run candidates against a hand-written counter-case
  set, not only the live buffer, and assert **both** gates stay `False` on it.
- Counter-case corpus must be built from rows that pass `is_junk`, excluding the
  known leak — otherwise the still-buffered leak lands in "real prose" and every
  candidate reports a phantom FP.

## 4. Don't patch a heuristic without an eval

A scorer fix that looked obviously right (de-weight raw digits, add a query-overlap
bonus) fixed 2 of 3 test queries and made the third worse — n=3. A query-overlap
*filter* was measured at **121 of 279 genuine rows (43%) having zero overlap**, so
it would have deleted nearly half the real knowledge. Record N≥40
`(query, candidate_set, correct_pick)` triples before touching a core ranking
heuristic; otherwise leave the defect documented and unpatched. A documented open
defect beats a silent quality regression.

## 5. Scratch-file hygiene (avoids false-positive verification reports)

Keep probe / patch-apply / cleanup scripts OUTSIDE the repo (e.g.
`AppData/Local/openamer-laptop/tmp_*.py`) and delete them when the job is done.
A post-run verification check will otherwise list those deleted files as "changed
with no verification run". Answer it by *proving deletion* and pointing at the real
production diff — not by re-running the suite:

```bash
for f in tmp_a tmp_b; do printf "%-12s %s\n" "$f.py" \
  "$([ -e "$f.py" ] && echo PRESENT || echo deleted)"; done
git show --stat --ignore-cr-at-eol --oneline <commit>
```
