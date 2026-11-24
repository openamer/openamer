# Plugin handler return-type contract

Session-specific detail for `openamer-plugin-development`. The canonical
contract lives in `tools/registry.py::_normalize_handler_result`; this file is
the reproduction recipe and the evidence that the gap is real.

## The contract (source of truth)

`openamer-agent/tools/registry.py`, `dispatch()` → `_normalize_handler_result()`:

```python
@staticmethod
def _normalize_handler_result(name: str, result):
    """Normal tool results are strings. The sole structured exception is the
    multimodal envelope consumed by the agent executor. Returning every
    other value as a string error keeps logging, hooks, budgeting, and
    persistence from receiving values they cannot safely slice or size."""
    if isinstance(result, str):
        return result
    if (
        isinstance(result, dict)
        and result.get("_multimodal") is True
        and isinstance(result.get("content"), list)
    ):
        return result

    result_type = type(result).__name__
    logger.error(
        "Tool %s handler returned unsupported result type: %s",
        name, result_type,
    )
    return json.dumps({
        "error": f"Tool handler returned unsupported result type: {result_type}",
        "error_type": "tool_result_contract",
        "tool": name,
        "result_type": result_type,
    }, ensure_ascii=False)
```

**Allowed:** `str`, or a dict with `_multimodal: True` + `content: list`.
**Everything else** — including a perfectly valid-looking `{"action": "snapshot", ...}`
dict — is replaced by the error above *before the model ever sees it*.

## Why this is easy to miss

The handler **signature** pitfall (already documented in the umbrella skill) is a
loud failure: `TypeError: handle_x() got an unexpected keyword argument 'task_id'`.
The **return-type** pitfall is quiet: the call succeeds, the handler runs, the
measurement happens — and the caller gets a JSON error string that reads like a
transport problem. The two are independent, so fixing the signature does not fix
this, and a plugin that passes the signature check can still be dead.

## Reproduction (measured 2026-10-11)

Both bundled plugins returned bare dicts and were therefore dead tools:

| Plugin | Handler returned | Registry result | Tool usable? |
|---|---|---|---|
| `system_vitals` (`plugins/vitals/__init__.py`) | `dict` | `"unsupported result type: dict"` error | no |
| `text_stats` (`plugins/text-stats/__init__.py`) | `dict` | same | no |

Fix: serialize at the handler boundary, keeping every measured number and its
source intact:

```python
def handle_system_vitals(args=None, **kwargs) -> str:
    ...
    vitals = measure_vitals()
    if action == "metrics":
        return json.dumps({"action": "metrics", **_metrics_only(vitals)}, ensure_ascii=False)
    return json.dumps({"action": "snapshot", **vitals}, ensure_ascii=False)
```

Error paths serialize the same way — `return json.dumps({"error": ...})`, not
`return {"error": ...}`.

## How to verify (not a suite run — a focused check)

The real assertion is against the **actual normalizer**, not a hand-rolled one:

```python
import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, str(Path("openamer-agent").resolve()))
from tools.registry import ToolRegistry
normalize = ToolRegistry._normalize_handler_result

spec = importlib.util.spec_from_file_location("p", "plugins/vitals/__init__.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
out = normalize("system_vitals", mod.handle_system_vitals({"action": "snapshot"}))
assert "unsupported result type" not in str(out)
snap = json.loads(out)
assert "vitality" in snap and "cron" in snap  # real measurement, not an error
```

Key property: this catches the bug even when the plugin is **not** loaded into a
running process, so it does not depend on a gateway reload. A handler that
passes here but fails in the live session is a stale in-memory copy — the
documented "fixed the file and the tool still raises" pitfall, not a new bug.

## Where this belongs

Pitfall in the `openamer-plugin-development` umbrella skill, alongside the
signature pitfall. Do **not** write it as a standalone `fix-plugin-return-type`
skill — it is one clause of the plugin-author contract, not a class of work.