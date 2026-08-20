"""
RAG Pipeline
============

A lightweight Retrieval-Augmented Generation pipeline for OpenAmer.

Provides:

- ``Document`` dataclass for representing text documents with metadata
- ``ChunkingStrategy`` enum: FIXED_SIZE, PARAGRAPH, RECURSIVE
- ``RagPipeline`` class with ingest, retrieve, and query methods
- Uses TF-IDF vectorization (no external vector DB required)
- CLI integration via ``openamer rag ingest`` and ``openamer rag query``
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

RAG_INDEX_DIR = Path.home() / ".openamer" / "rag_index"

# ── Document Dataclass ────────────────────────────────────────────────────────


@dataclass
class Document:
    """A document to be ingested into the RAG pipeline.

    Attributes:
        text: The document's text content.
        metadata: Arbitrary key-value metadata.
        source: Original source (file path, URL, etc.).
        doc_id: Unique identifier (auto-generated if not provided).
    """

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    doc_id: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            self.doc_id = hashlib.md5(self.text.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata,
            "source": self.source,
            "doc_id": self.doc_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        return cls(
            text=data["text"],
            metadata=data.get("metadata", {}),
            source=data.get("source", ""),
            doc_id=data.get("doc_id", ""),
        )


# ── ChunkingStrategy ──────────────────────────────────────────────────────────


class ChunkingStrategy(str, enum.Enum):
    """Strategy for splitting documents into chunks."""

    FIXED_SIZE = "fixed_size"
    PARAGRAPH = "paragraph"
    RECURSIVE = "recursive"


# ── Chunk ─────────────────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A single chunk of text with metadata."""

    text: str
    doc_id: str = ""
    source: str = ""
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_id}_{self.chunk_index}"


# ── SearchResult ──────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """Result of a retrieval query."""

    chunk: Chunk
    score: float = 0.0
    rank: int = 0


# ── TF-IDF Vectorizer ─────────────────────────────────────────────────────────


class TfidfVectorizer:
    """Simple pure-Python TF-IDF vectorizer.

    No external dependencies — uses standard library only.
    """

    def __init__(self) -> None:
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._doc_count: int = 0
        self._doc_vectors: List[Tuple[str, Counter]] = []  # (doc_id, term_freqs)

    def fit(self, chunks: List[Chunk]) -> None:
        """Build vocabulary and IDF from a list of chunks."""
        self._doc_vectors = []
        doc_freq: Counter = Counter()

        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            tf = Counter(tokens)
            self._doc_vectors.append((chunk.chunk_id, tf))
            for token in set(tokens):
                doc_freq[token] += 1

        self._doc_count = len(chunks)
        self._vocab = {token: idx for idx, token in enumerate(doc_freq.keys())}

        # IDF: log((N + 1) / (df + 1)) + 1 (smooth IDF)
        for token, df in doc_freq.items():
            self._idf[token] = math.log((self._doc_count + 1) / (df + 1)) + 1

        logger.info(
            "TF-IDF fitted on %d chunks with %d unique tokens",
            self._doc_count,
            len(self._vocab),
        )

    def transform(self, text: str) -> Counter:
        """Transform text into TF-IDF-weighted term frequency vector."""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        weighted: Counter = Counter()
        for token, count in tf.items():
            if token in self._idf:
                weighted[token] = count * self._idf[token]
        return weighted

    def similarity(self, query_vector: Counter, doc_idx: int) -> float:
        """Compute cosine similarity between a query vector and a document."""
        _chunk_id, doc_tf = self._doc_vectors[doc_idx]
        dot = 0.0
        norm_q = 0.0
        norm_d = 0.0

        # Query vector terms
        for token, weight in query_vector.items():
            norm_q += weight * weight
            if token in doc_tf:
                doc_weight = doc_tf[token] * self._idf.get(token, 1.0)
                dot += weight * doc_weight

        # Document vector norm (only terms not in query)
        for token, count in doc_tf.items():
            if token not in query_vector:
                doc_weight = count * self._idf.get(token, 1.0)
                norm_d += doc_weight * doc_weight

        norm_q = math.sqrt(norm_q)
        norm_d = math.sqrt(norm_d)
        if norm_q == 0 or norm_d == 0:
            return 0.0
        return dot / (norm_q * norm_d)

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """Search the fitted corpus and return top_k (doc_idx, score) pairs."""
        query_vec = self.transform(query)
        scores: List[Tuple[int, float]] = []

        for idx in range(len(self._doc_vectors)):
            sim = self.similarity(query_vec, idx)
            if sim > 0:
                scores.append((idx, sim))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    def save(self, path: Path) -> None:
        """Persist the vectorizer state to disk."""
        data = {
            "vocab": self._vocab,
            "idf": {k: v for k, v in self._idf.items()},
            "doc_count": self._doc_count,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self, path: Path) -> None:
        """Load vectorizer state from disk."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._vocab = data["vocab"]
        self._idf = {k: float(v) for k, v in data["idf"].items()}
        self._doc_count = data["doc_count"]
        # doc_vectors must be restored separately from saved chunks
        self._doc_vectors = []

    def restore_doc_vectors(self, chunks: List[Chunk]) -> None:
        """Recompute document vectors from chunks (needed after load)."""
        self._doc_vectors = []
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            tf = Counter(tokens)
            self._doc_vectors.append((chunk.chunk_id, tf))

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric tokens."""
        text = text.lower()
        tokens = re.findall(r"[a-z0-9]+", text)
        # Filter very short and very long tokens
        return [t for t in tokens if 2 <= len(t) <= 50]


# ── Chunkers ──────────────────────────────────────────────────────────────────


def chunk_fixed_size(
    text: str, chunk_size: int = 500, overlap: int = 50
) -> List[str]:
    """Split text into fixed-size chunks with overlap."""
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def chunk_by_paragraph(text: str) -> List[str]:
    """Split text into paragraph-sized chunks (double-newline separated)."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def chunk_recursive(
    text: str,
    max_chunk_size: int = 500,
    min_chunk_size: int = 50,
) -> List[str]:
    """Split text recursively using a hierarchy of separators.

    Tries: double newline → single newline → sentence → word boundary.
    """
    if not text:
        return []

    separators = ["\n\n", "\n", ". ", "! ", "? ", ", ", " "]
    chunks: List[str] = []

    def _split(text: str, sep_idx: int) -> None:
        if sep_idx >= len(separators):
            # Force split at max_chunk_size
            start = 0
            while start < len(text):
                end = min(start + max_chunk_size, len(text))
                chunks.append(text[start:end].strip())
                start = end
            return

        sep = separators[sep_idx]
        if not sep:
            _split(text, sep_idx + 1)
            return

        parts = []
        # Use regex to split while keeping the separator
        raw_parts = re.split(f"({re.escape(sep)})", text)
        i = 0
        while i < len(raw_parts):
            part = raw_parts[i]
            if i + 1 < len(raw_parts):
                part += raw_parts[i + 1]  # reattach separator
                i += 1
            if part.strip():
                parts.append(part.strip())
            i += 1

        current = ""
        for part in parts:
            if len(current) + len(part) <= max_chunk_size or len(current) < min_chunk_size:
                current += part
            else:
                if current:
                    chunks.append(current.strip())
                current = part

        if current and current.strip():
            # If remaining is still too large, recurse
            if len(current) > max_chunk_size and sep_idx < len(separators) - 1:
                _split(current, sep_idx + 1)
            else:
                chunks.append(current.strip())

    _split(text, 0)
    return [c for c in chunks if c and len(c) >= min_chunk_size]


# ── RagPipeline ───────────────────────────────────────────────────────────────


class RagPipeline:
    """A lightweight RAG pipeline using TF-IDF vectorization.

    Example::

        pipeline = RagPipeline()
        pipeline.ingest([
            Document(text="Paris is the capital of France.", source="geo.txt"),
            Document(text="The Eiffel Tower is in Paris.", source="landmarks.txt"),
        ])
        results = pipeline.retrieve("What is the capital of France?")
        answer = pipeline.query("What is the capital of France?", "Answer concisely.")
    """

    def __init__(
        self,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        index_dir: Optional[Path] = None,
        llm_fn: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        self.chunking_strategy = chunking_strategy
        self.index_dir = Path(index_dir) if index_dir else RAG_INDEX_DIR
        self.llm_fn = llm_fn

        self._chunks: List[Chunk] = []
        self._documents: List[Document] = []
        self._vectorizer = TfidfVectorizer()
        self._fitted: bool = False

    # ── Ingestion ─────────────────────────────────────────────────────────

    def ingest(
        self,
        documents: List[Document],
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> int:
        """Chunk and index documents.

        Args:
            documents: List of ``Document`` objects to ingest.
            chunk_size: Max chunk size for FIXED_SIZE and RECURSIVE strategies.
            chunk_overlap: Overlap between chunks for FIXED_SIZE strategy.

        Returns:
            Number of chunks created.
        """
        self._documents.extend(documents)
        new_chunks: List[Chunk] = []

        for doc in documents:
            text_chunks = self._chunk_text(
                doc.text, strategy=self.chunking_strategy,
                chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            )
            for idx, chunk_text in enumerate(text_chunks):
                new_chunks.append(
                    Chunk(
                        text=chunk_text,
                        doc_id=doc.doc_id,
                        source=doc.source,
                        chunk_index=idx,
                        metadata=doc.metadata,
                    )
                )

        self._chunks.extend(new_chunks)

        # Re-fit the vectorizer on all chunks
        if self._chunks:
            self._vectorizer = TfidfVectorizer()
            self._vectorizer.fit(self._chunks)
            self._fitted = True

        logger.info(
            "Ingested %d document(s) — %d total chunk(s)",
            len(documents),
            len(self._chunks),
        )
        return len(new_chunks)

    def ingest_file(
        self,
        path: Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> int:
        """Ingest a single file as a document.

        Supports .txt, .md, .json, .csv, .py, .yaml, .yml files.
        """
        if not path.is_file():
            logger.warning("File not found: %s", path)
            return 0

        text = path.read_text(encoding="utf-8", errors="replace")
        doc = Document(
            text=text,
            source=str(path),
            metadata={"file_path": str(path), "file_size": path.stat().st_size},
        )
        return self.ingest([doc], chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def ingest_directory(
        self,
        directory: Path,
        pattern: str = "*",
        recursive: bool = True,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> int:
        """Ingest all matching files in a directory."""
        if not directory.is_dir():
            logger.warning("Directory not found: %s", directory)
            return 0

        total = 0
        glob_method = directory.rglob if recursive else directory.glob
        for filepath in sorted(glob_method(pattern)):
            if filepath.is_file() and not filepath.name.startswith("."):
                total += self.ingest_file(
                    filepath,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
        return total

    def _chunk_text(
        self,
        text: str,
        strategy: ChunkingStrategy,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """Split text into chunks using the configured strategy."""
        if strategy == ChunkingStrategy.FIXED_SIZE:
            return chunk_fixed_size(text, chunk_size=chunk_size, overlap=chunk_overlap)
        elif strategy == ChunkingStrategy.PARAGRAPH:
            return chunk_by_paragraph(text)
        elif strategy == ChunkingStrategy.RECURSIVE:
            return chunk_recursive(text, max_chunk_size=chunk_size, min_chunk_size=max(20, chunk_size // 10))
        return [text]

    # ── Retrieval ─────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Retrieve the top-k most relevant chunks for a query.

        Args:
            query: The search query.
            top_k: Number of results to return.

        Returns:
            List of ``SearchResult`` objects sorted by relevance.
        """
        if not self._fitted or not self._chunks:
            logger.warning("No indexed data — call ingest() first")
            return []

        results = self._vectorizer.search(query, top_k=top_k)
        search_results: List[SearchResult] = []

        for rank, (doc_idx, score) in enumerate(results, 1):
            if doc_idx < len(self._chunks):
                search_results.append(
                    SearchResult(
                        chunk=self._chunks[doc_idx],
                        score=score,
                        rank=rank,
                    )
                )

        return search_results

    def retrieve_formatted(self, query: str, top_k: int = 5) -> str:
        """Retrieve and format context for use in a prompt.

        Returns a string with the top-k chunks formatted as context.
        """
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return ""

        parts: List[str] = []
        for r in results:
            source = f" (source: {r.chunk.source})" if r.chunk.source else ""
            parts.append(
                f"[Chunk {r.rank} — score {r.score:.3f}{source}]\n{r.chunk.text}"
            )

        return "\n\n".join(parts)

    # ── Full RAG Query ────────────────────────────────────────────────────

    def query(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Execute a full RAG query: retrieve context + generate answer.

        Args:
            query: The user's question.
            system_prompt: Optional system prompt to guide the model.
            model: Model identifier (stored in metadata, not directly used).

        Returns:
            The model's answer as a string.

        Raises:
            ValueError: If no ``llm_fn`` is configured.
        """
        if self.llm_fn is None:
            raise ValueError(
                "No llm_fn configured. Set llm_fn on the pipeline or provide "
                "a model function before calling query()."
            )

        context = self.retrieve_formatted(query, top_k=5)
        if not context:
            return "No relevant context found to answer the query."

        default_sys = (
            "You are a helpful assistant. Answer the user's question based on the "
            "provided context. If the context doesn't contain enough information, "
            "say so — don't make things up."
        )

        full_prompt = f"""{system_prompt or default_sys}

=== CONTEXT ===
{context}

=== QUESTION ===
{query}

Answer based on the context above:"""

        return self.llm_fn(full_prompt, model or "")

    # ── Persistence ───────────────────────────────────────────────────────

    def save_index(self, name: str = "default") -> Path:
        """Save the current index (chunks + vectorizer) to disk."""
        index_dir = self.index_dir / name
        index_dir.mkdir(parents=True, exist_ok=True)

        # Save chunks
        chunks_path = index_dir / "chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "text": c.text,
                        "doc_id": c.doc_id,
                        "source": c.source,
                        "chunk_index": c.chunk_index,
                        "metadata": c.metadata,
                    }
                    for c in self._chunks
                ],
                f,
                ensure_ascii=False,
                indent=2,
            )

        # Save vectorizer
        vec_path = index_dir / "vectorizer.json"
        self._vectorizer.save(vec_path)

        # Save metadata
        meta_path = index_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "chunk_count": len(self._chunks),
                    "chunking_strategy": self.chunking_strategy.value,
                    "doc_count": len(self._documents),
                },
                f,
                ensure_ascii=False,
            )

        logger.info("Index saved to %s (%d chunks)", index_dir, len(self._chunks))
        return index_dir

    def load_index(self, name: str = "default") -> bool:
        """Load a previously saved index from disk."""
        index_dir = self.index_dir / name
        if not index_dir.is_dir():
            logger.warning("No saved index at %s", index_dir)
            return False

        chunks_path = index_dir / "chunks.json"
        vec_path = index_dir / "vectorizer.json"

        if not chunks_path.is_file() or not vec_path.is_file():
            logger.warning("Incomplete index at %s", index_dir)
            return False

        # Load chunks
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        self._chunks = [
            Chunk(
                text=c["text"],
                doc_id=c.get("doc_id", ""),
                source=c.get("source", ""),
                chunk_index=c.get("chunk_index", 0),
                metadata=c.get("metadata", {}),
            )
            for c in chunks_data
        ]

        # Load vectorizer
        self._vectorizer = TfidfVectorizer()
        self._vectorizer.load(vec_path)
        self._vectorizer.restore_doc_vectors(self._chunks)
        self._fitted = True

        # Restore documents (without original text — just placeholders)
        self._documents = [
            Document(
                text="",  # original text not saved; chunks carry the content
                source=chunk.source,
                doc_id=chunk.doc_id,
                metadata=chunk.metadata,
            )
            for chunk in self._chunks
        ]

        logger.info("Index loaded from %s (%d chunks)", index_dir, len(self._chunks))
        return True

    def clear(self) -> None:
        """Clear all indexed data."""
        self._chunks = []
        self._documents = []
        self._vectorizer = TfidfVectorizer()
        self._fitted = False
        logger.info("RAG pipeline cleared")

    # ── Info ──────────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        """Return statistics about the current pipeline state."""
        return {
            "chunks": len(self._chunks),
            "documents": len(self._documents),
            "fitted": self._fitted,
            "chunking_strategy": self.chunking_strategy.value,
        }