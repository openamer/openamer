"""openamer_cli.a2a.selflearn — the autonomous self-learning loop.

Phase 5. The "the organism grows": after a complex task, the agent can distill
a lesson from what happened and -- automatically -- turn it into a signed
:class:`Insight` that it adopts into its own mesh memory AND (opt-in) stages for
the GitHub mesh directory so other nodes can adopt it.

The insight *extraction* is pluggable: :func:`auto_learn` accepts a
``distill` callback (used by the runtime, possibly LLM-backed). The signing +
adopt + publish path is pure local crypto -- fully covered by offline tests.

Delivered as a real module + `openamer a2a meshlearn auto` CLI.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from openamer_cli.a2a.meshlearn import Insight, publish, adopt


def auto_learn(
    *,
    identity_store,
    memory_path: Path,
    learn_from: str,
    topic: str = "general",
    title: Optional[str] = None,
    distill: Optional[Callable[[str, str], tuple[str, str]]] = None,
    publish_dir: Optional[Path] = None,
    skip_publish: bool = True,
) -> dict:
    """Self-loop: distill an insight from an experience, sign it, adopt it.

    Steps (all verified in tests):
      1. ``title, body = distill(learn_from, topic)`` if a distill callback is
         given, else fall back to a deterministic summary.
      2. :class:`Insight.build` signs it with this node's identity.
      3. :func:`adopt` appends it to ``memory_path`` (mesh memory), unless
         already present.
      4. If ``publish_dir`` is set and not skip_publish, stage for the mesh.

    Returns a summary dict for the caller/CLI.
    """
    if distill is not None:
        title, body = distill(learn_from, topic)
    else:
        # Deterministic fallback so `auto` works offline in tests.
        title = title or "Learned from task"
        body = learn_from.strip()[:300] or "(no text)"
        title = title[:60]
    if not body:
        return {"ok": False, "error": "empty distillation"}

    ins = Insight.build(identity_store=identity_store, title=title, body=body, topic=topic)
    adopted = adopt(ins, memory_path, require_verify=True)

    staged = None
    if publish_dir is not None and not skip_publish:
        staged = publish(ins, publish_dir)
        staged = str(staged)

    return {
        "ok": True,
        "signature_ok": ins.verify(),
        "adopted": adopted,
        "insight_path": str(memory_path),
        "staged": staged,
        "source": ins.source,
        "topic": topic,
    }


def parse_mesh_memory(memory_path: Path) -> list[dict]:
    """Return the mesh-learning lines from a memory file as small dicts."""
    out = []
    if not memory_path.exists():
        return out
    for line in memory_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("#mesh:"):
            try:
                topic, rest = line[len("#mesh:"):].split(":", 1)
                title, _, body = rest.partition(" — ")
                out.append({"topic": topic, "title": title.strip(), "body": body.strip()})
            except Exception:
                continue
    return out