"""
Vector Memory Store — unbegrenztes semantisches Gedächtnis für OpenAmer.

Ersetzt die 2200-Zeichen-Memory-Grenze durch einen TF-IDF-basierten
Vector Store mit Cosine-Similarity-Suche. Keine externen Dependencies
ausser numpy (das sowieso installiert ist).

Speicher-Struktur unter ~/.openamer/vector_memory/:
  - index.json       : Metadaten (keys, timestamps, doc_ids)
  - vectors.npy      : numpy-Array der TF-IDF Vektoren
  - documents.json   : die rohen Text-Dokumente
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
VECTOR_DIR = HOME / "vector_memory"
INDEX_FILE = VECTOR_DIR / "index.json"
VECTORS_FILE = VECTOR_DIR / "vectors.npy"
DOCUMENTS_FILE = VECTOR_DIR / "documents.json"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """Ein einzelner Memory-Eintrag."""

    id: str
    key: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 0


# ---------------------------------------------------------------------------
# TF-IDF Core (pure Python, kein sklearn)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Einfaches Tokenizing: Lowercase, split auf Nicht-Wortzeichen."""
    return re.findall(r"\w+", text.lower())


def _idf(corpus: list[list[str]]) -> dict[str, float]:
    """Berechne IDF für jedes Token im Corpus."""
    n_docs = len(corpus)
    df: Counter[str] = Counter()
    for tokens in corpus:
        df.update(set(tokens))
    return {token: math.log((n_docs + 1) / (count + 1)) + 1 for token, count in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> np.ndarray:
    """Erzeuge einen TF-IDF Vektor (sortiert nach idf-Schlüsseln)."""
    tf = Counter(tokens)
    n_total = len(tokens)
    if n_total == 0:
        return np.zeros(len(idf), dtype=np.float32)
    terms = list(idf.keys())
    vec = np.zeros(len(terms), dtype=np.float32)
    for i, term in enumerate(terms):
        tf_val = tf.get(term, 0) / n_total
        vec[i] = tf_val * idf.get(term, 1.0)
    return vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine-Similarity zwischen zwei Vektoren."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Vector Memory Store
# ---------------------------------------------------------------------------


class VectorMemoryStore:
    """Der Haupt-Store: persistiert als JSON + numpy unter ~/.openamer/vector_memory/."""

    def __init__(self, vector_dir: Path = VECTOR_DIR):
        self.vector_dir = vector_dir
        self.vector_dir.mkdir(parents=True, exist_ok=True)

        self.entries: list[MemoryEntry] = []
        self.vectors: np.ndarray = np.empty((0, 0), dtype=np.float32)
        self.idf: dict[str, float] = {}
        self._loaded = False

    # ---- Persistenz ----

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load()

    def _load(self) -> None:
        """Lade Store von Disk."""
        idx_file = self.vector_dir / "index.json"
        vec_file = self.vector_dir / "vectors.npy"
        doc_file = self.vector_dir / "documents.json"

        if idx_file.exists():
            with open(idx_file, encoding="utf-8") as f:
                data = json.load(f)
            self.idf = data.get("idf", {})
            # Lade Vektoren
            if vec_file.exists():
                self.vectors = np.load(vec_file)
            else:
                self.vectors = np.empty((0, len(self.idf) or 1), dtype=np.float32)
            # Lade Dokumente
            if doc_file.exists():
                with open(doc_file, encoding="utf-8") as f:
                    docs = json.load(f)
                self.entries = [MemoryEntry(**e) for e in docs]
        self._loaded = True

    def _save(self) -> None:
        """Speichere Store auf Disk."""
        idx_file = self.vector_dir / "index.json"
        vec_file = self.vector_dir / "vectors.npy"
        doc_file = self.vector_dir / "documents.json"
        # Index
        with open(idx_file, "w", encoding="utf-8") as f:
            json.dump({"idf": self.idf, "count": len(self.entries), "updated": datetime.now(timezone.utc).isoformat()}, f)
        # Vektoren
        np.save(vec_file, self.vectors)
        # Dokumente
        with open(doc_file, "w", encoding="utf-8") as f:
            json.dump([e.__dict__ for e in self.entries], f, ensure_ascii=False)

    # ---- CRUD ----

    def store(self, key: str, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        """Speichere einen neuen Memory-Eintrag."""
        self._ensure_loaded()
        entry = MemoryEntry(
            id=f"mem_{int(time.time())}_{len(self.entries)}",
            key=key,
            content=content,
            metadata=metadata or {},
        )

        # Den Eintrag erstmal hinzufügen
        self.entries.append(entry)

        # Alle Vektoren NEU berechnen (IDF hat sich geändert)
        corpus = [_tokenize(e.content) for e in self.entries]
        self.idf = _idf(corpus)
        new_vectors = [_tfidf_vector(t, self.idf) for t in corpus]
        self.vectors = np.array(new_vectors, dtype=np.float32)

        self._save()
        return entry

    def search(self, query: str, top_k: int = 5, score_threshold: float = 0.0) -> list[tuple[MemoryEntry, float]]:
        """Semantische Suche über alle Einträge. Gibt (Entry, Score) sorted by Score DESC."""
        self._ensure_loaded()
        if len(self.entries) == 0:
            return []

        query_tokens = _tokenize(query)
        query_vec = _tfidf_vector(query_tokens, self.idf)

        scores = [cosine_similarity(query_vec, v) for v in self.vectors]

        # Sortieren
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed:
            if score < score_threshold:
                continue
            self.entries[idx].access_count += 1
            self.entries[idx].last_accessed = datetime.now(timezone.utc).isoformat()
            results.append((self.entries[idx], round(score, 4)))
            if len(results) >= top_k:
                break

        if results:
            self._save()  # access_count aktualisieren
        return results

    def get_stats(self) -> dict[str, Any]:
        """Statistiken über den Store."""
        self._ensure_loaded()
        return {
            "total_entries": len(self.entries),
            "vector_dimensions": self.vectors.shape[1] if self.vectors.ndim > 1 and self.vectors.shape[1] > 0 else 0,
            "idf_vocab_size": len(self.idf),
            "storage_path": str(self.vector_dir),
            "last_updated": INDEX_FILE.exists() and json.load(open(INDEX_FILE, encoding="utf-8")).get("updated", "never"),
        }

    def get_all_entries(self) -> list[MemoryEntry]:
        """Alle Einträge abrufen."""
        self._ensure_loaded()
        return sorted(self.entries, key=lambda e: e.created_at, reverse=True)

    def delete_entry(self, entry_id: str) -> bool:
        """Lösche einen Eintrag per ID."""
        self._ensure_loaded()
        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                self.entries.pop(i)
                self.vectors = np.delete(self.vectors, i, axis=0)
                # IDF neu berechnen
                corpus = [_tokenize(e.content) for e in self.entries]
                self.idf = _idf(corpus) if corpus else {}
                # Vektoren neu berechnen
                if self.entries:
                    new_vectors = [_tfidf_vector(t, self.idf) for t in corpus]
                    self.vectors = np.array(new_vectors, dtype=np.float32)
                else:
                    self.vectors = np.empty((0, 0), dtype=np.float32)
                self._save()
                return True
        return False

    def compress(self, max_entries: int = 1000) -> int:
        """Komprimiere: entferne älteste/lowest-score Einträge wenn über Limit."""
        self._ensure_loaded()
        if len(self.entries) <= max_entries:
            return 0

        # Sortiere nach last_accessed (älteste zuerst)
        sorted_entries = sorted(self.entries, key=lambda e: e.last_accessed)
        to_remove = len(self.entries) - max_entries

        removed_ids = {e.id for e in sorted_entries[:to_remove]}
        self.entries = [e for e in self.entries if e.id not in removed_ids]

        # Vektoren + IDF neu aufbauen
        corpus = [_tokenize(e.content) for e in self.entries]
        self.idf = _idf(corpus) if corpus else {}
        if self.entries:
            new_vectors = [_tfidf_vector(t, self.idf) for t in corpus]
            self.vectors = np.array(new_vectors, dtype=np.float32)
        else:
            self.vectors = np.empty((0, 0), dtype=np.float32)

        self._save()
        return len(removed_ids)


# ---------------------------------------------------------------------------
# Singleton + Public API
# ---------------------------------------------------------------------------

_store: VectorMemoryStore | None = None


def get_store() -> VectorMemoryStore:
    """Hole den Singleton-Store."""
    global _store
    if _store is None:
        _store = VectorMemoryStore()
    return _store


def vector_store(key: str, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
    """Kurzform: speichere einen Memory-Eintrag."""
    return get_store().store(key, content, metadata)


def vector_search(query: str, top_k: int = 5) -> list[tuple[MemoryEntry, float]]:
    """Kurzform: suche über Memory-Einträge."""
    return get_store().search(query, top_k=top_k)


def vector_stats() -> dict[str, Any]:
    """Kurzform: Store-Statistiken."""
    return get_store().get_stats()


def vector_compress(max_entries: int = 1000) -> int:
    """Kurzform: komprimiere den Store."""
    return get_store().compress(max_entries=max_entries)


def vector_list() -> list[dict[str, Any]]:
    """Alle Einträge als Dicts (für CLI)."""
    return [e.__dict__ for e in get_store().get_all_entries()]