"""Vector store / memory module for RAG-based agent context retrieval.

Provides document ingestion, chunking, and semantic search using ChromaDB
as the vector store backend. ChromaDB is an optional dependency — the pure
utility functions (chunk_text, generate_doc_id) work without it, but
VectorMemory requires chromadb to be installed.
"""

from __future__ import annotations

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
# VectorMemory (requires chromadb)
# ---------------------------------------------------------------------------


class VectorMemory:
    """Semantic vector store backed by ChromaDB.

    Provides document ingestion (with automatic chunking), similarity
    search with optional metadata filtering, and document deletion.

    ChromaDB is imported lazily at instantiation time so that the rest of
    the module remains usable without the ``chromadb`` package installed.

    Args:
        collection_name: Name of the ChromaDB collection to use.
        persist_directory: If provided, ChromaDB will persist data to this
            directory.  Otherwise an ephemeral in-memory client is used.
    """

    def __init__(
        self,
        collection_name: str = "finance_os",
        persist_directory: str | None = None,
    ) -> None:
        try:
            import chromadb  # noqa: F811
        except ImportError as exc:
            raise ImportError(
                "chromadb is required for VectorMemory but is not installed. "
                "Install it with:  pip install 'finance-os-agents[rag]'"
            ) from exc

        if persist_directory is not None:
            self._client = chromadb.PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.Client()

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_document(self, document: Document) -> list[str]:
        """Chunk, embed, and store a document.

        Args:
            document: The document to ingest.

        Returns:
            A list of chunk IDs that were stored.
        """
        doc_id = document.doc_id or generate_doc_id(document.content, document.metadata)
        chunks = chunk_text(document.content)

        if not chunks:
            return []

        chunk_ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []

        meta_dict = _metadata_to_dict(document.metadata)
        meta_dict["doc_id"] = doc_id

        for idx, chunk in enumerate(chunks):
            cid = f"{doc_id}_chunk_{idx}"
            chunk_ids.append(cid)
            documents.append(chunk)
            metadatas.append({**meta_dict, "chunk_index": str(idx)})

        self._collection.add(
            ids=chunk_ids,
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

        return chunk_ids

    def search(
        self,
        query: str,
        n_results: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """Run a semantic search over ingested chunks.

        Args:
            query: Natural-language query string.
            n_results: Maximum number of results to return.
            metadata_filter: Optional key-value pairs to filter on metadata
                fields (e.g. ``{"ticker": "AAPL"}``).

        Returns:
            A list of :class:`SearchResult` objects ordered by relevance.
        """
        where: dict[str, str] | None = None
        if metadata_filter:
            where = {k: v for k, v in metadata_filter.items()}

        kwargs: dict[str, object] = {
            "query_texts": [query],
            "n_results": min(n_results, self._collection.count() or n_results),
        }
        if where:
            kwargs["where"] = where

        if self._collection.count() == 0:
            return []

        results = self._collection.query(**kwargs)  # type: ignore[arg-type]

        search_results: list[SearchResult] = []
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        for doc, meta_raw, distance in zip(documents, metadatas, distances):
            meta = dict(meta_raw) if meta_raw else {}
            doc_id = meta.pop("doc_id", "")
            meta.pop("chunk_index", None)

            metadata = DocumentMetadata(
                ticker=meta.get("ticker"),
                date=meta.get("date"),
                source=meta.get("source"),
                doc_type=meta.get("doc_type"),
                section=meta.get("section"),
            )

            # ChromaDB cosine distance is in [0, 2]; convert to [0, 1] score.
            relevance = max(0.0, min(1.0, 1.0 - distance))

            search_results.append(
                SearchResult(
                    content=doc,
                    metadata=metadata,
                    relevance_score=round(relevance, 6),
                    doc_id=doc_id,
                )
            )

        return search_results

    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document.

        Args:
            doc_id: The document identifier whose chunks should be removed.

        Returns:
            The number of chunks that were deleted.
        """
        existing = self._collection.get(where={"doc_id": doc_id})
        ids_to_delete = existing["ids"]

        if not ids_to_delete:
            return 0

        self._collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    def count(self) -> int:
        """Return the total number of chunks stored in the collection.

        Returns:
            Chunk count.
        """
        return self._collection.count()  # type: ignore[return-value]


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
