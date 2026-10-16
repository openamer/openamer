---
name: codebase-index
description: "Use before grepping blindly: query the persistent symbol index."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [code, index, symbols, navigation, context, performance]
    related_skills: [code-intelligence, codebase-inspection, web-research]
---

# Codebase Index — ask the index before grepping everything

A persistent, symbol-level index of a repository plus a query that answers
"which files and symbols matter for this task". Built because a bare grep over a
large repo answers with hundreds of irrelevant lines, and because every prompt
should start from the code that actually matters.

## When to use it

- **Before a blind `grep` sweep** in an unfamiliar or large repo.
- When you need to find *where a symbol is defined* rather than every mention
  of a word.
- When you are about to read a directory to "get an overview".
- After pulling/rebasing, so the index reflects the current tree.

Do **not** use it as a substitute for reading the code: the index tells you
where to look, never what the code does.

## Commands

```bash
openamer index build --repo .              # build or update (incremental)
openamer index query "session budget"      # ranked files + symbols
openamer index query "session budget" --json
openamer index stats --repo .
```

`--repo` defaults to the current directory. The index lives in the target repo
at `.openamer/index/code-index.json` — it belongs to that repo, not to
`OPENAMER_HOME`.

## How to read the output

Each hit carries a `source` field:

- `ast` — the file was parsed with Python's `ast`: classes, functions, methods
  and the first line of their docstring are **exact**.
- `heuristic` — a regex scan, used for other languages. **Approximate.** It
  finds likely declarations, not a real parse.

Never present a `heuristic` hit as if it were a parsed fact. If precision
matters for a non-Python file, open it.

## Limits you must know (measured, not guessed)

- **Python and the languages with `ast` are exact; everything else is a
  heuristic** that can miss declarations and can report a comment as a symbol.
- **The result can be `partial`.** Two separate caps bound a build: a file cap
  and a per-file symbol cap. When either is hit the build says so —
  `WARNING: file cap reached — the index is partial`. A partial index is still
  useful, but "the symbol is not in the index" is then **not** evidence that it
  does not exist.
- **A build is incremental** over `(mtime, size)`: an unchanged file is never
  reopened. That makes the second run cheap, so re-running after a pull is
  normal rather than expensive.
- **The wall-clock budget bounds the scan, not the whole command.** The index
  write happens after the scan and adds its own time, so the total can exceed
  the budget. Do not promise a caller a hard upper bound on wall time.
- Binary files, very large files and the usual dependency/build directories
  (`.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`) are skipped
  by design.

## Pitfalls

- **A stale index is worse than none.** If the query returns nothing for
  something you know exists, rebuild before concluding anything.
- **Do not commit the index.** It is generated output under the repo's
  `.openamer/` directory.
- **The index is a starting point, not a source of truth.** Cite the file and
  line, then read them.
