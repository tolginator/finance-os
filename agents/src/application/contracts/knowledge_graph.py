"""Pydantic request/response contracts for the knowledge graph.

Contracts for entity extraction, graph queries, and graph statistics.
"""

from pydantic import BaseModel, Field

# ── Entity / Relationship serialization ──────────────────────


class EntityModel(BaseModel):
    """Serialized entity for API responses."""

    entity_id: str
    name: str
    entity_type: str
    ticker: str | None = None
    cik: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class RelationshipModel(BaseModel):
    """Serialized relationship for API responses."""

    source_id: str
    target_id: str
    rel_type: str
    evidence: str = ""
    source_doc: str = ""
    confidence: str = "0.5"
    metadata: dict[str, object] = Field(default_factory=dict)


# ── Extract ──────────────────────────────────────────────────


class ExtractEntitiesRequest(BaseModel):
    """Request to extract entities and relationships from text."""

    text: str = Field(min_length=1, description="Text to extract entities from")
    source_doc: str = Field(default="", description="Source document identifier for provenance")
    ticker: str | None = Field(
        default=None, description="Company ticker to associate with extraction",
    )


class ExtractEntitiesResponse(BaseModel):
    """Response from entity extraction."""

    entities: list[EntityModel]
    relationships: list[RelationshipModel]
    entity_count: int
    relationship_count: int


# ── Query: Related ───────────────────────────────────────────


class QueryRelatedRequest(BaseModel):
    """Request to find entities related to a given entity."""

    entity_id: str = Field(min_length=1, description="Canonical entity ID to query from")
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum traversal depth")


class QueryRelatedResponse(BaseModel):
    """Response with related entities."""

    entity_id: str
    related: list[EntityModel]
    count: int


# ── Query: Supply Chain ──────────────────────────────────────


class QuerySupplyChainRequest(BaseModel):
    """Request to trace the supply chain from an entity."""

    entity_id: str = Field(min_length=1, description="Canonical entity ID to trace from")
    direction: str = Field(default="upstream", pattern="^(upstream|downstream)$")


class QuerySupplyChainResponse(BaseModel):
    """Response with supply chain trace."""

    entity_id: str
    direction: str
    chain: list[EntityModel]
    count: int


# ── Query: Shared Risks ──────────────────────────────────────


class QuerySharedRisksRequest(BaseModel):
    """Request to find risks shared by multiple entities."""

    entity_ids: list[str] = Field(min_length=2, description="At least two entity IDs")


class QuerySharedRisksResponse(BaseModel):
    """Response with shared risk entities."""

    entity_ids: list[str]
    shared_risks: list[EntityModel]
    count: int


# ── Stats ─────────────────────────────────────────────────────


class KGStatsResponse(BaseModel):
    """Knowledge graph summary statistics."""

    entity_count: int
    relationship_count: int
    entities_by_type: dict[str, int]
    relationships_by_type: dict[str, int]
