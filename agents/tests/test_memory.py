"""Tests for the memory utilities module."""


from src.core.memory import (
    DocumentMetadata,
    chunk_text,
    generate_doc_id,
)

# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------
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
