"""openamer_cli.a2a.braindata — collect learning material for a future OpenAmer model.

Phase 6. Every agent, sub-agent and A2A node feeds the collective brain: gather
learning material from proven sources and write a standardized ChatML/ShareGPT
JSONL training set usable by a future OpenAmer fine-tune:

  1. Trajectories — OpenAmer records success/failed trajectories in
     trajectory_samples.jsonl / failed_trajectories.jsonl (ShareGPT, see
     agent/trajectory.py.save_trajectory).
  2. Mesh memory — adopted mesh-learn Insights (a2a.meshlearn).
  3. Skills — signed skill manifests (a2a.skillshare).

Only stdlib; emission is fully offline (no LLM needed to build the dataset).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


@dataclass
class Record:
    engine: str        # trajectory | insight | skill
    messages: list     # ChatML [{"role","content"}]
    topic: str = ""

    def to_jsonl(self) -> str:
        d = {"messages": self.messages, "engine": self.engine}
        if self.topic:
            d["topic"] = self.topic
        return json.dumps(d, ensure_ascii=False)

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.messages, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _chat(system: str, user: str, assistant: Optional[str] = None) -> list:
    msgs = [{"role": "system", "content": system}]
    msgs.append({"role": "user", "content": user})
    if assistant is not None:
        msgs.append({"role": "assistant", "content": assistant})
    return msgs


def iter_trajectory_files(paths: Iterable[Path]) -> Iterator[list]:
    """Yield ShareGPT chat-lists from OpenAmer trajectory JSONL files (deduped)."""
    seen = set()
    for p in paths:
        if not p.exists() or p.suffix != ".jsonl":
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msgs = obj.get("messages") or obj.get("conversation")
            if not isinstance(msgs, list) or not msgs:
                continue
            key = json.dumps(msgs, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            yield msgs


def insight_records(memory_path: Path) -> Iterator[Record]:
    """Convert mesh-memory '#mesh:topic: Title — body' lines to training turns."""
    if not memory_path.exists():
        return
    pat = re.compile(r"^#mesh:([^:]+):\s*(.+?)\s*(?:[—–-]{1,2})\s*(.*)$")
    for line in memory_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        topic, title, body = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        msgs = _chat("You are OpenAmer, a capable autonomous AI agent.",
                     f"Share a lesson you learned: {title}", body)
        yield Record(engine="insight", messages=msgs, topic=topic)


def skill_records(manifest_files: Iterable[Path]) -> Iterator[Record]:
    """Turn signed skill manifests into provenance-oriented training turns."""
    for p in manifest_files:
        if not p.exists() or not p.name.endswith(".json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        name = d.get("name")
        if not name:
            continue
        msgs = _chat(
            "You are OpenAmer.", 
            f"Describe the skill '{name}' and its publisher.",
            f"Skill '{name}' published by {d.get('publisher', 'unknown')}, "
            f"{len(d.get('files', {}))} files; verify provenance with "
            f"`openamer a2a skill verify`.",
        )
        yield Record(engine="skill", messages=msgs)  # topic stays ""


def build_dataset(*, trajectories: list[Path], insights: Path, out: Path,
                  skills: Optional[Iterable[Path]] = None,
                  clamp_trajectory: int = 50) -> dict:
    """Assemble a Chat-based JSONL training set from all sources (deduped)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    records: list[Record] = []
    for msgs in iter_trajectory_files(trajectories):
        records.append(Record(engine="trajectory", messages=msgs[:clamp_trajectory]))
    records.extend(insight_records(insights))
    if skills:
        records.extend(skill_records(skills))

    seen, uniq = set(), []
    for rec in records:
        d = rec.digest()
        if d in seen:
            continue
        seen.add(d)
        uniq.append(rec)

    with open(out, "w", encoding="utf-8") as fh:
        for rec in uniq:
            fh.write(rec.to_jsonl() + "\n")

    counts = {"trajectory": 0, "insight": 0, "skill": 0}
    for rec in uniq:
        counts[rec.engine] = counts.get(rec.engine, 0) + 1
    return {"records": len(uniq), "sources": counts, "path": str(out)}