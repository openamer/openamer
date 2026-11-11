**Engineering note — a session that pays for its imports once.** (commit `44552bec3`, Sep 23 2026)

Something in the self-healing loop was always there but easy to miss: the code path underneath it started a **fresh interpreter for every call**. So a variable set in one step was gone in the next, and every turn of a multi-step repair paid to re-import and re-load the same things. That is not a bug you notice in a test — it is a tax you pay in every run, forever.

`code_kernel` keeps **one child interpreter per session** and execs one cell per call.

**What it does not do** — this is the part worth reading. It does *not* widen the sandbox. A cell goes through the project's own machinery: the same environment scrubber, the same interpreter/cwd resolution (so project mode still gets the user's venv), the same generated `openamer_tools` module so `terminal()` / `read_file()` work inside a cell, and the same process-group kill path with escalation. **Only the process lifetime changes.**

**The caller contract, stated plainly:**

- **Cells share one namespace.** `x = 1` in one cell is visible in the next.
- **An error is reported and the kernel stays alive.** State is still there afterwards.
- **Timeouts lose state on purpose.** A cell that exceeds `timeout` (default 60s) has its process tree killed and the kernel dropped; the next call starts clean. A Python frame cannot be interrupted in place safely, so the error says so instead of pretending the state can be resumed. Long work belongs in a cell that writes progress somewhere durable.
- **Env is frozen at spawn.** A variable exported after the kernel started is invisible until you pass `reset=true`.

**Verified by running it, not by reading it.** Against the repo tree:

```
cell 1  import math; root = math.sqrt(144)   -> ok    exec 1  kernel demo:project:1  mode project
cell 2  print(root)                          -> 12.0  exec 2  (same kernel)
cell 3  raise ValueError('boom')             -> error exec 3  (same kernel — not torn down)
cell 4  print(root + 1)                      -> 13.0  exec 4  (state survived the error)
```

Regression suite `tests/scripts/test_code_kernel_session.py`: **12 passed in 63.2s**. It asserts the *contract*, not "it runs code" — that part would pass for a broken implementation too. Included: sessions are isolated (a second session cannot see the first's state), a wedged cell is killed and `REGISTRY.count()` returns to 0, and `reset` yields a **distinctly named** kernel so "which process answered" is never a guess.

**One real defect the tests exist for.** The first implementation read the child's reply with `proc.stdout.read(4096)`, which **blocks until all 4096 bytes arrive** — so a small reply was never handed over and *every* cell looked like a timeout. Fixing that exposed the other half: the reader must not stop at the first chunk, or a 20 KB cell is truncated. Both are now pinned (`test_stdout_larger_than_one_pipe_read_arrives`). It was found by running it, not by reviewing it.

**How to use it:** it joins `execute_code` in the `code_execution` toolset (`toolsets.py`), so `-t code_execution` gives you both — use `code_kernel` when a later step needs what an earlier one computed, and plain `execute_code` for a one-off snippet.

**Where it stands, honestly:** the commit is in our tree and the toolset wiring is in `toolsets.py`; the tool is **not yet registered in this machine's installed toolset** (`tools/code_kernel.py` is absent from the live install and that tree's `toolsets.py` has no `code_kernel` entry), and the commit is on our local `main` but **not yet on `origin/main`**. So: verified on the repo tree, not yet packaged. Flagging that rather than calling it shipped.
