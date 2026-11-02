# Portable ASI script resolution

The ASI wrappers and `ASICore` resolve each script through one profile-scoped
resolver (`tools/asi/_training.py`):

1. `get_openamer_home()/scripts/training/<module>.py` — an explicit runtime copy.
2. `get_openamer_home()/scripts/<module>.py` — an explicit runtime helper script.
3. The same two sub-trees inside the running checkout — the code that ships with
   the installation.

Order matters in two directions: the profile's runtime copy wins over the
checkout copy of the same sub-tree, and the sub-tree the caller asked for wins
over the other one. Runtime code in `scripts/` is never shadowed by a checkout
module of the same name in `scripts/training/`, and vice versa.

Only code falls back. No runtime script, model, credential or private state is
copied into the checkout. Another profile and a guessed `openamer-repo`
directory are not code sources.

## Module identity and isolation

Every load runs under a private module name derived from the canonical home
and the source path, so two profiles on one machine never share a module
object. Bare legacy sibling imports use the same resolver — including imports
that happen inside a function body — and a public wrapper module of the same
name can never satisfy them. After execution the module reports its plain
script name, so callers that inspect `__name__` keep working.

Scripts receive `OPENAMER_HOME` for the active profile through a local `os`
view; the process environment is never mutated. Legacy scripts that resolve
their own home at import time and fall back to the machine's default install
have their store constants rebound to the loading profile, so a load for one
profile cannot write into another profile's data. Import-time path insertions
are restored.

This is compatibility loading, not a security sandbox for untrusted code.

## Honest limits

- An existing runtime module that fails to import is an error, not a reason to
  silently use different checkout code. The error names the selected source and
  keeps the original exception as its cause.
- Optional model/embedding servers and extra dependencies still have to be
  installed and configured. Resolving Python source does not make those
  services available.
- Missing legacy entry points remain honest errors. This change does not
  upgrade old scripts to newer private runtime APIs.
- Subprocess-run scripts keep their own internal behaviour; the core passes the
  canonical home explicitly.

Regression coverage: `tests/tools/test_asi_training_resolution.py` — real
imports and calls against empty temporary homes, runtime precedence, profile
isolation, sibling-import scoping and a loud failure for a broken runtime copy.
