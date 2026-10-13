"""Tests for openamer_cli.rag_pipeline — RAG Pipeline."""

import json
import pathlib
import re
import tempfile
from pathlib import Path

import pytest

from openamer_cli.rag_pipeline import (
    Chunk,
    ChunkingStrategy,
    Document,
    RagPipeline,
    SearchResult,
    TfidfVectorizer,
    chunk_by_paragraph,
    chunk_fixed_size,
    chunk_recursive,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_docs():
    return [
        Document(
            text="Paris is the capital of France. It is known for the Eiffel Tower.",
            source="geo.txt",
            metadata={"category": "geography"},
        ),
        Document(
            text="Python is a programming language. It is widely used for AI and web development.",
            source="tech.txt",
            metadata={"category": "technology"},
        ),
        Document(
            text="Berlin is the capital of Germany. It has a rich history.",
            source="geo.txt",
            metadata={"category": "geography"},
        ),
    ]


@pytest.fixture
def pipeline():
    return RagPipeline(chunking_strategy=ChunkingStrategy.PARAGRAPH)


@pytest.fixture
def llm_fn():
    def _llm(prompt: str, model: str = "") -> str:
        # A simple model that extracts a city name if "capital" mentioned
        m = re.search(r"(Paris|Berlin|London|Madrid)", prompt)
        return m.group(1) if m else "I don't know"
    return _llm


# ── Tests for Document ─────────────────────────────────────────────────────────


class TestDocument:
    def test_default_creation(self):
        doc = Document(text="Hello world")
        assert doc.text == "Hello world"
        assert doc.source == ""
        assert len(doc.doc_id) == 16

    def test_with_metadata(self):
        doc = Document(text="Test", source="test.txt", metadata={"key": "val"})
        assert doc.source == "test.txt"
        assert doc.metadata["key"] == "val"

    def test_explicit_doc_id(self):
        doc = Document(text="Test", doc_id="my-id-123")
        assert doc.doc_id == "my-id-123"

    def test_to_dict(self):
        doc = Document(text="Hello", source="f.txt", doc_id="abc")
        d = doc.to_dict()
        assert d["text"] == "Hello"
        assert d["source"] == "f.txt"
        assert d["doc_id"] == "abc"

    def test_from_dict(self):
        d = {"text": "World", "source": "g.txt", "doc_id": "def", "metadata": {}}
        doc = Document.from_dict(d)
        assert doc.text == "World"
        assert doc.source == "g.txt"


# ── Tests for Chunk ────────────────────────────────────────────────────────────


class TestChunk:
    def test_chunk_id(self):
        c = Chunk(text="hello", doc_id="doc1", chunk_index=3)
        assert c.chunk_id == "doc1_3"


# ── Tests for Chunking Strategies ──────────────────────────────────────────────


class TestChunking:
    def test_fixed_size(self):
        text = "Hello world, this is a test of fixed size chunking."
        chunks = chunk_fixed_size(text, chunk_size=15, overlap=5)
        assert len(chunks) >= 2
        assert all(isinstance(c, str) for c in chunks)

    def test_fixed_size_empty(self):
        assert chunk_fixed_size("") == []

    def test_paragraph(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_by_paragraph(text)
        assert len(chunks) >= 3

    def test_paragraph_no_separator(self):
        text = "Single paragraph."
        chunks = chunk_by_paragraph(text)
        assert len(chunks) == 1

    def test_recursive(self):
        text = "Sentence one. Sentence two. Sentence three. " * 20
        chunks = chunk_recursive(text, max_chunk_size=100, min_chunk_size=20)
        assert len(chunks) >= 2
        assert all(len(c) >= 20 for c in chunks)

    def test_recursive_empty(self):
        assert chunk_recursive("") == []

    def test_recursive_short(self):
        text = "Short text that is long enough to pass the minimum chunk size filter."
        chunks = chunk_recursive(text, max_chunk_size=200, min_chunk_size=10)
        assert len(chunks) >= 1


# ── Tests for TfidfVectorizer ─────────────────────────────────────────────────


class TestTfidfVectorizer:
    def test_fit_and_search(self):
        chunks = [
            Chunk(text="Paris is the capital of France", doc_id="d1", chunk_index=0),
            Chunk(text="Python is a programming language", doc_id="d2", chunk_index=0),
            Chunk(text="Berlin is the capital of Germany", doc_id="d3", chunk_index=0),
        ]
        vec = TfidfVectorizer()
        vec.fit(chunks)

        results = vec.search("capital of France", top_k=2)
        assert len(results) >= 1
        # Top result should be about France/Paris
        top_idx, top_score = results[0]
        assert top_score > 0

    def test_search_empty(self):
        vec = TfidfVectorizer()
        results = vec.search("hello", top_k=5)
        assert results == []

    def test_save_and_load(self):
        chunks = [
            Chunk(text="test document one", doc_id="d1", chunk_index=0),
            Chunk(text="test document two", doc_id="d2", chunk_index=0),
        ]
        vec = TfidfVectorizer()
        vec.fit(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vec.json"
            vec.save(path)
            assert path.is_file()

            vec2 = TfidfVectorizer()
            vec2.load(path)
            # Restore doc vectors
            vec2.restore_doc_vectors(chunks)
            results = vec2.search("document one", top_k=1)
            assert len(results) >= 1


# ── Tests for RagPipeline ──────────────────────────────────────────────────────


class TestRagPipeline:
    def test_ingest(self, pipeline, sample_docs):
        n = pipeline.ingest(sample_docs)
        assert n > 0
        assert pipeline.stats["chunks"] >= 3
        assert pipeline.stats["fitted"] is True

    def test_ingest_empty(self, pipeline):
        n = pipeline.ingest([])
        assert n == 0

    def test_retrieve(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        results = pipeline.retrieve("capital of France", top_k=3)
        assert len(results) >= 1
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.score > 0
            assert r.rank >= 1

    def test_retrieve_no_index(self, pipeline):
        results = pipeline.retrieve("query")
        assert results == []

    def test_retrieve_empty_query(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        results = pipeline.retrieve("", top_k=3)
        assert isinstance(results, list)

    def test_retrieve_formatted(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        formatted = pipeline.retrieve_formatted("capital of France")
        assert len(formatted) > 0
        assert "[Chunk 1" in formatted

    def test_retrieve_formatted_no_results(self, pipeline):
        formatted = pipeline.retrieve_formatted("anything")
        assert formatted == ""

    def test_query_requires_llm_fn(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        with pytest.raises(ValueError, match="No llm_fn"):
            pipeline.query("What is the capital of France?")

    def test_query_with_llm_fn(self, pipeline, sample_docs, llm_fn):
        pipeline.llm_fn = llm_fn
        pipeline.ingest(sample_docs)
        answer = pipeline.query("What is the capital of France?")
        assert "Paris" in answer

    def test_query_no_context(self, pipeline, llm_fn):
        pipeline.llm_fn = llm_fn
        # No documents ingested
        answer = pipeline.query("Something")
        assert "No relevant context" in answer

    def test_ingest_file(self, pipeline):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("London is the capital of the United Kingdom.")
            n = pipeline.ingest_file(path)
            assert n >= 1

    def test_ingest_file_not_found(self, pipeline):
        n = pipeline.ingest_file(Path("/nonexistent/file.txt"))
        assert n == 0

    def test_ingest_directory(self, pipeline):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.txt").write_text("Document A content here.")
            (d / "b.txt").write_text("Document B content here.")
            (d / "c.md").write_text("# Document C")
            n = pipeline.ingest_directory(d, pattern="*.txt")
            assert n >= 2

    def test_ingest_directory_not_found(self, pipeline):
        n = pipeline.ingest_directory(Path("/nonexistent"))
        assert n == 0

    def test_clear(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        assert pipeline.stats["chunks"] > 0
        pipeline.clear()
        assert pipeline.stats["chunks"] == 0
        assert pipeline.stats["fitted"] is False


# ── Tests for RagPipeline persistence ──────────────────────────────────────────


class TestRagPipelinePersistence:
    def test_save_and_load_index(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        with tempfile.TemporaryDirectory() as tmp:
            index_dir = Path(tmp) / "my_index"
            pipeline.index_dir = index_dir
            saved = pipeline.save_index(name="test")
            assert saved.is_dir()

            new_pipeline = RagPipeline()
            new_pipeline.index_dir = index_dir
            ok = new_pipeline.load_index(name="test")
            assert ok is True
            assert new_pipeline.stats["chunks"] == pipeline.stats["chunks"]
            assert new_pipeline.stats["fitted"] is True

    def test_load_nonexistent(self, pipeline):
        ok = pipeline.load_index(name="nonexistent")
        assert ok is False

    def test_load_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = RagPipeline(index_dir=Path(tmp))
            index_dir = Path(tmp) / "incomplete"
            index_dir.mkdir()
            # Only chunks, no vectorizer
            (index_dir / "chunks.json").write_text("[]")
            ok = pipeline.load_index(name="incomplete")
            assert ok is False


# ── Tests for ChunkingStrategy ────────────────────────────────────────────────


class TestChunkingStrategy:
    def test_strategies(self):
        assert ChunkingStrategy.FIXED_SIZE.value == "fixed_size"
        assert ChunkingStrategy.PARAGRAPH.value == "paragraph"
        assert ChunkingStrategy.RECURSIVE.value == "recursive"


# ── Tests for SearchResult ─────────────────────────────────────────────────────


class TestSearchResult:
    def test_creation(self):
        chunk = Chunk(text="test", doc_id="d1")
        sr = SearchResult(chunk=chunk, score=0.95, rank=1)
        assert sr.score == 0.95
        assert sr.rank == 1
        assert sr.chunk.text == "test"


# ── Tests for pipeline stats ──────────────────────────────────────────────────


class TestPipelineStats:
    def test_empty_stats(self, pipeline):
        stats = pipeline.stats
        assert stats["chunks"] == 0
        assert stats["documents"] == 0
        assert stats["fitted"] is False

    def test_after_ingest(self, pipeline, sample_docs):
        pipeline.ingest(sample_docs)
        stats = pipeline.stats
        assert stats["chunks"] > 0
        assert stats["documents"] == 3
        assert stats["fitted"] is True