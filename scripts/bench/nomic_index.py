#!/usr/bin/env python3
"""Build a true-semantic embedding index for the episodic store.

Why a second index instead of a rewrite
--------------------------------------
`scripts/embeddings.py` is a character-n-gram hasher: it encodes *shape*, not
meaning, so a paraphrased question shares almost no vector with its own episode
(measured 2026-11-24: recall@5 = 7/50, semantic-only questions 3/45). A real
embedding model fixes the cause, but rewriting `longterm_episodes.jsonl` would
destroy 8326 stored vectors to prove a point.

This script is strictly additive: it reads the store, never writes it, and keeps
the vectors in `memory/embeddings-nomic.npz` keyed by the sha1[:12] of the
episode text. Deleting that one file rolls the whole thing back.

Model
-----
`nomic-embed-text` via the local Ollama API (768 dims, ~60 ms warm, no network,
no download - the model is already on this disk). Documents are embedded with
the `search_document: ` task prefix the model was trained with.

Resumable
---------
The index is rewritten every `--checkpoint` documents, so a killed run keeps
what it already earned and the next run continues where it stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

# The store, the index and the delta all live in the INSTALL HOME, not next to
# this file. `Path(__file__).parents[2]` is only correct while the script sits in
# `<home>/scripts/bench/`; once it is published (or run from a checkout) it
# resolves to the repo root and looks for a store that is not there. Resolve the
# home explicitly, the same way scripts/bench/memory_eval.py does.
BASE = (
    Path(os.environ["OPENAMER_HOME"]).resolve()
    if os.environ.get("OPENAMER_HOME")
    else (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
)
STORE = BASE / "memory" / "longterm_episodes.jsonl"
INDEX = BASE / "memory" / "embeddings-nomic.npz"
DELTA = BASE / "memory" / "embeddings-nomic-delta.jsonl"
OLLAMA = "http://127.0.0.1:11434/api/embed"
MODEL = "nomic-embed-text"
PREFIX = "search_document: "


def text_hash(text: str) -> str:
    return hashlib.sha1(text.strip().encode()).hexdigest()[:12]


def embed_batch(texts: list[str], model: str = MODEL, timeout: float = 300.0) -> list[list[float]]:
    body = json.dumps({"model": model, "input": [PREFIX + t for t in texts]}).encode()
    request = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    vectors = payload.get("embeddings")
    if not vectors or len(vectors) != len(texts):
        raise RuntimeError(f"ollama returned {0 if not vectors else len(vectors)} vectors for {len(texts)} inputs")
    return vectors


def load_store() -> list[tuple[str, str]]:
    """(hash, text) pairs, deduplicated by hash, in store order."""
    seen: dict[str, str] = {}
    with open(STORE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (record.get("text") or "").strip()
            if text:
                seen.setdefault(text_hash(text), text)
    return list(seen.items())


def load_index() -> tuple[list[str], np.ndarray]:
    if not INDEX.exists():
        return [], np.zeros((0, 768), dtype=np.float32)
    data = np.load(INDEX, allow_pickle=False)
    return list(data["hashes"]), data["vectors"]


def save_index(hashes: list[str], vectors: np.ndarray) -> None:
    tmp = INDEX.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, hashes=np.array(hashes, dtype="U12"), vectors=vectors.astype(np.float32))
    tmp.replace(INDEX)


def fold_delta(hashes: list[str], vectors: np.ndarray) -> tuple[list[str], np.ndarray, int]:
    """Merge the append-only delta into the main index.

    `add_episode` appends one vector per new memory to the delta so the memory is
    retrievable immediately; without this fold the delta would grow forever and be
    re-read on every query. Existing hashes are UPDATED (the delta is newer), new
    ones are appended. Returns the folded count so the caller can decide whether
    to truncate - and truncation only happens after a successful save.
    """
    if not DELTA.exists() or DELTA.stat().st_size == 0:
        return hashes, vectors, 0
    position = {digest: index for index, digest in enumerate(hashes)}
    updates: dict[int, np.ndarray] = {}
    additions: list[tuple[str, np.ndarray]] = []
    folded = 0
    with DELTA.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                digest = str(record["h"])
                vector = np.asarray(record["v"], dtype=np.float32)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # a half-written line from a killed process is not fatal
            folded += 1
            if digest in position:
                updates[position[digest]] = vector
            else:
                additions.append((digest, vector))

    if updates:
        vectors = vectors.copy()
        for index, vector in updates.items():
            vectors[index] = vector
    if additions:
        hashes = hashes + [digest for digest, _v in additions]
        rows = [vector for _h, vector in additions]
        vectors = np.vstack([vectors, *rows]) if len(vectors) else np.vstack(rows)
    return hashes, vectors, folded



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--checkpoint", type=int, default=400)
    parser.add_argument("--limit", type=int, default=0, help="only embed the first N missing documents (0 = all)")
    args = parser.parse_args()

    documents = load_store()
    hashes, vectors, folded = fold_delta(*load_index())
    try:
        delta_size_before = DELTA.stat().st_size
    except OSError:
        delta_size_before = 0
    known = set(hashes)
    missing = [(h, t) for h, t in documents if h not in known]
    if args.limit:
        missing = missing[: args.limit]
    print(f"store={len(documents)} indexed={len(known)} missing={len(missing)} delta_folded={folded}", flush=True)
    if not missing:
        if folded:
            save_index(hashes, vectors)
            DELTA.write_text("", encoding="utf-8")
        print(f"index is complete ({len(hashes)} vectors)")
        return 0

    vectors = np.asarray(vectors, dtype=np.float32)
    started = time.perf_counter()
    for offset in range(0, len(missing), args.batch):
        chunk = missing[offset: offset + args.batch]
        try:
            embedded = embed_batch([text for _h, text in chunk])
        except (urllib.error.URLError, RuntimeError, TimeoutError) as error:
            print(f"FAILED at offset {offset}: {error}", file=sys.stderr, flush=True)
            print(f"kept {len(hashes)} vectors; re-run to continue", file=sys.stderr)
            save_index(hashes, vectors)
            return 1
        hashes.extend(h for h, _t in chunk)
        batch = np.asarray(embedded, dtype=np.float32)
        vectors = np.vstack([vectors, batch]) if len(vectors) else batch
        processed = offset + len(chunk)
        if processed % args.checkpoint < args.batch or processed == len(missing):
            save_index(hashes, vectors)
            rate = processed / max(time.perf_counter() - started, 1e-6)
            eta = (len(missing) - processed) / rate if rate else 0
            print(f"  {processed}/{len(missing)}  {rate:.1f} docs/s  eta {eta:.0f}s", flush=True)

    save_index(hashes, vectors)
    # Truncate the delta only if nothing was appended while we were working;
    # otherwise the new rows would be lost with the truncation.
    if folded:
        try:
            if DELTA.stat().st_size == delta_size_before:
                DELTA.write_text("", encoding="utf-8")
        except OSError:
            pass
    print(f"done: {len(hashes)} vectors, dim={vectors.shape[1]}, delta_folded={folded}, file={INDEX} ({INDEX.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
