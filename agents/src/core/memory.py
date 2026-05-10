"""Memory utilities for document chunking and identification.

Provides document ingestion helpers (chunking, ID generation) and
data classes for structured document metadata and search results.
"""


import hashlib
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DocumentMetadata:
    """Metadata associated with an ingested document.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        date: ISO-8601 date string (e.g. "2024-01-15").
        source: Origin system — "edgar", "transcript", or "research".
        doc_type: Filing type — "10-K", "10-Q", "8-K", "earnings_call".
        section: Document section — "risk-factors", "mda", "q&a".
    """

    ticker: str | None = None
    date: str | None = None
    source: str | None = None
    doc_type: str | None = None
    section: str | None = None


@dataclass
class Document:
    """A document to be ingested into the vector store.

    Args:
        content: The full text content of the document.
        metadata: Structured metadata for filtering and provenance.
        doc_id: Optional deterministic identifier. Auto-generated if not provided.
    """

    content: str
    metadata: DocumentMetadata
    doc_id: str | None = None


@dataclass
class SearchResult:
    """A single result returned from a semantic search.

    Args:
        content: The chunk text that matched.
        metadata: Metadata inherited from the parent document.
        relevance_score: Similarity score in [0, 1], higher is better.
        doc_id: Identifier of the parent document.
    """

    content: str
    metadata: DocumentMetadata
    relevance_score: float
    doc_id: str


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split *text* into chunks of approximately *chunk_size* characters.

    Splitting respects word boundaries — a chunk will never break in the
    middle of a word.  Consecutive chunks share *overlap* characters of
    context so that information at chunk boundaries is not lost.

    Args:
        text: The input text to chunk.
        chunk_size: Target maximum number of characters per chunk.
        overlap: Number of characters of overlap between consecutive chunks.

    Returns:
        A list of text chunks.  Returns an empty list when *text* is empty
        or contains only whitespace.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current_chunk_words: list[str] = []
    current_length = 0

    for word in words:
        word_len = len(word)
        # +1 accounts for the space separator (except for the very first word)
        addition = word_len if not current_chunk_words else word_len + 1

        if current_length + addition > chunk_size and current_chunk_words:
            chunk_text_str = " ".join(current_chunk_words)
            chunks.append(chunk_text_str)

            # Walk backward to build the overlap seed
            overlap_words: list[str] = []
            overlap_len = 0
            for w in reversed(current_chunk_words):
                candidate = len(w) if not overlap_words else len(w) + 1
                if overlap_len + candidate > overlap:
                    break
                overlap_words.insert(0, w)
                overlap_len += candidate

            current_chunk_words = overlap_words
            current_length = sum(len(w) for w in current_chunk_words)
            if len(current_chunk_words) > 1:
                current_length += len(current_chunk_words) - 1

        current_chunk_words.append(word)
        current_length = (
            sum(len(w) for w in current_chunk_words) + max(len(current_chunk_words) - 1, 0)
        )

    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))

    return chunks


def generate_doc_id(content: str, metadata: DocumentMetadata) -> str:
    """Create a deterministic document ID from content and metadata.

    The ID is the first 16 hex characters of the SHA-256 hash of a
    canonical string built from *content* and *metadata* fields.

    Args:
        content: Document text.
        metadata: Document metadata.

    Returns:
        A 16-character lowercase hex string.
    """
    canonical = (
        f"{content}|{metadata.ticker}|{metadata.date}|"
        f"{metadata.source}|{metadata.doc_type}|{metadata.section}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _metadata_to_dict(metadata: DocumentMetadata) -> dict[str, str]:
    """Convert a DocumentMetadata to a flat dict, omitting None values."""
    result: dict[str, str] = {}
    if metadata.ticker is not None:
        result["ticker"] = metadata.ticker
    if metadata.date is not None:
        result["date"] = metadata.date
    if metadata.source is not None:
        result["source"] = metadata.source
    if metadata.doc_type is not None:
        result["doc_type"] = metadata.doc_type
    if metadata.section is not None:
        result["section"] = metadata.section
    return result
