"""Tests for the vector memory module."""

from __future__ import annotations

import pytest

from src.core.memory import (
    Document,
    DocumentMetadata,
    SearchResult,
    chunk_text,
    generate_doc_id,
)

# ---------------------------------------------------------------------------
# Pure function tests (always run — no ChromaDB required)
# ---------------------------------------------------------------------------


class TestChunkText:
    """Tests for the chunk_text utility."""

    def test_empty_string_returns_empty_list(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert chunk_text("   \n\t  ") == []

    def test_short_text_returns_single_chunk(self) -> None:
        text = "This is a short sentence."
        result = chunk_text(text, chunk_size=500)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_produces_multiple_chunks(self) -> None:
        # 20 words × ~6 chars = ~120 chars; chunk_size=50 should force splits
        text = " ".join(f"word{i}" for i in range(30))
        result = chunk_text(text, chunk_size=50, overlap=10)
        assert len(result) > 1
        # Every chunk should be within a reasonable range of chunk_size
        for chunk in result[:-1]:
            assert len(chunk) <= 60  # allow slight overshoot from whole words

    def test_overlap_between_chunks(self) -> None:
        words = [f"word{i}" for i in range(40)]
        text = " ".join(words)
        result = chunk_text(text, chunk_size=50, overlap=20)
        assert len(result) >= 2
        # Consecutive chunks should share some words
        for i in range(len(result) - 1):
            words_a = set(result[i].split())
            words_b = set(result[i + 1].split())
            assert words_a & words_b, "Consecutive chunks should overlap"

    def test_respects_word_boundaries(self) -> None:
        text = "abcdefghij " * 10  # 10-char words + spaces
        result = chunk_text(text, chunk_size=25, overlap=5)
        for chunk in result:
            # No partial words — every token should be a full word
            for token in chunk.split():
                assert token == "abcdefghij"

    def test_single_very_long_word(self) -> None:
        text = "a" * 1000
        result = chunk_text(text, chunk_size=50, overlap=10)
        # A single word that exceeds chunk_size still gets included
        assert len(result) >= 1
        assert "a" * 1000 in result[0]


class TestGenerateDocId:
    """Tests for the generate_doc_id utility."""

    def test_deterministic(self) -> None:
        meta = DocumentMetadata(ticker="AAPL", date="2024-01-15", source="edgar")
        id1 = generate_doc_id("Hello world", meta)
        id2 = generate_doc_id("Hello world", meta)
        assert id1 == id2

    def test_different_content_different_id(self) -> None:
        meta = DocumentMetadata(ticker="AAPL")
        id1 = generate_doc_id("Content A", meta)
        id2 = generate_doc_id("Content B", meta)
        assert id1 != id2

    def test_different_metadata_different_id(self) -> None:
        content = "Same content"
        id1 = generate_doc_id(content, DocumentMetadata(ticker="AAPL"))
        id2 = generate_doc_id(content, DocumentMetadata(ticker="MSFT"))
        assert id1 != id2

    def test_id_length(self) -> None:
        doc_id = generate_doc_id("text", DocumentMetadata())
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)


# ---------------------------------------------------------------------------
# VectorMemory integration tests (skip when chromadb is not installed)
# ---------------------------------------------------------------------------


class TestVectorMemory:
    """Integration tests for VectorMemory — skipped if chromadb is missing."""

    @pytest.fixture(autouse=True)
    def _require_chromadb(self) -> None:
        pytest.importorskip("chromadb")

    @pytest.fixture()
    def memory(self) -> object:
        """Create a fresh in-memory VectorMemory instance."""
        from src.core.memory import VectorMemory

        return VectorMemory(collection_name=f"test_{id(self)}")

    def test_ingest_and_search(self, memory: object) -> None:
        from src.core.memory import VectorMemory

        assert isinstance(memory, VectorMemory)
        doc = Document(
            content=(
                "Apple reported record revenue in Q4 2024. "
                "The iPhone segment grew 12% year over year. "
                "Services revenue also set a new quarterly record."
            ),
            metadata=DocumentMetadata(ticker="AAPL", source="transcript"),
        )
        chunk_ids = memory.ingest_document(doc)
        assert len(chunk_ids) >= 1
        assert memory.count() >= 1

        results = memory.search("Apple revenue growth")
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].relevance_score >= 0.0

    def test_metadata_filtering(self, memory: object) -> None:
        from src.core.memory import VectorMemory

        assert isinstance(memory, VectorMemory)
        doc_aapl = Document(
            content="Apple financial results for fiscal year 2024 were strong.",
            metadata=DocumentMetadata(ticker="AAPL", source="edgar"),
        )
        doc_msft = Document(
            content="Microsoft cloud revenue exceeded expectations in 2024.",
            metadata=DocumentMetadata(ticker="MSFT", source="edgar"),
        )
        memory.ingest_document(doc_aapl)
        memory.ingest_document(doc_msft)

        results = memory.search("revenue", metadata_filter={"ticker": "AAPL"})
        for r in results:
            assert r.metadata.ticker == "AAPL"

    def test_delete_document(self, memory: object) -> None:
        from src.core.memory import VectorMemory

        assert isinstance(memory, VectorMemory)
        doc = Document(
            content="Some financial data to be deleted later.",
            metadata=DocumentMetadata(ticker="TSLA"),
            doc_id="delete-me",
        )
        memory.ingest_document(doc)
        assert memory.count() >= 1

        deleted = memory.delete_document("delete-me")
        assert deleted >= 1
        assert memory.count() == 0

    def test_empty_search_returns_empty_list(self, memory: object) -> None:
        from src.core.memory import VectorMemory

        assert isinstance(memory, VectorMemory)
        results = memory.search("anything")
        assert results == []

    def test_import_error_without_chromadb(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VectorMemory raises a clear ImportError when chromadb is missing."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "chromadb":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        from src.core.memory import VectorMemory as VectorMemoryClass

        with pytest.raises(ImportError, match="chromadb is required"):
            VectorMemoryClass()
