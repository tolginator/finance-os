"""Knowledge graph service — entity extraction, ingestion, and graph queries.

Process-level graph store: the KnowledgeGraph persists across requests
within the same process (like a database connection), unlike agent services
which are fresh per request.
"""

from src.application.contracts.knowledge_graph import (
    EntityModel,
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
    KGStatsResponse,
    QueryRelatedRequest,
    QueryRelatedResponse,
    QuerySharedRisksRequest,
    QuerySharedRisksResponse,
    QuerySupplyChainRequest,
    QuerySupplyChainResponse,
    RelationshipModel,
)
from src.core.entity_extraction import extract_entities, extract_relationships
from src.core.knowledge_graph import Entity, KnowledgeGraph, Relationship


def _entity_to_model(entity: Entity) -> EntityModel:
    """Convert core Entity to API model."""
    return EntityModel(
        entity_id=entity.entity_id,
        name=entity.name,
        entity_type=entity.entity_type.value,
        ticker=entity.ticker,
        cik=entity.cik,
        metadata=entity.metadata,
    )


def _rel_to_model(rel: Relationship) -> RelationshipModel:
    """Convert core Relationship to API model."""
    return RelationshipModel(
        source_id=rel.source_id,
        target_id=rel.target_id,
        rel_type=rel.rel_type.value,
        evidence=rel.evidence,
        source_doc=rel.source_doc,
        confidence=str(rel.confidence),
        metadata=rel.metadata,
    )


class KnowledgeGraphService:
    """Service layer for knowledge graph operations.

    Wraps a KnowledgeGraph instance and provides typed contract-based
    methods for extraction, querying, and statistics.
    """

    def __init__(self, graph: KnowledgeGraph | None = None) -> None:
        self._graph = graph or KnowledgeGraph()

    @property
    def graph(self) -> KnowledgeGraph:
        """Access the underlying graph (for testing/inspection)."""
        return self._graph

    def extract_and_ingest(self, request: ExtractEntitiesRequest) -> ExtractEntitiesResponse:
        """Extract entities and relationships from text and add them to the graph.

        Args:
            request: Extraction request with text and provenance info.

        Returns:
            Response with extracted entities and relationships.
        """
        entities = extract_entities(request.text, source_doc=request.source_doc)

        # If a ticker is provided, try to associate it with the first company entity
        if request.ticker:
            promoted: list[Entity] = []
            ticker_assigned = False
            for ent in entities:
                if ent.entity_type.value == "company" and not ticker_assigned and not ent.ticker:
                    promoted.append(Entity(
                        name=ent.name,
                        entity_type=ent.entity_type,
                        ticker=request.ticker.upper(),
                        cik=ent.cik,
                        metadata=ent.metadata,
                    ))
                    ticker_assigned = True
                else:
                    promoted.append(ent)
            entities = promoted

        # Add entities to graph
        entity_ids: dict[str, str] = {}
        for ent in entities:
            eid = self._graph.add_entity(ent)
            entity_ids[ent.entity_id] = eid

        # Extract and add relationships
        relationships = extract_relationships(
            request.text, entities, source_doc=request.source_doc,
        )

        added_rels: list[Relationship] = []
        for rel in relationships:
            src = entity_ids.get(rel.source_id, rel.source_id)
            tgt = entity_ids.get(rel.target_id, rel.target_id)
            mapped_rel = Relationship(
                source_id=src,
                target_id=tgt,
                rel_type=rel.rel_type,
                evidence=rel.evidence,
                source_doc=rel.source_doc,
                confidence=rel.confidence,
                metadata=rel.metadata,
            )
            try:
                self._graph.add_relationship(mapped_rel)
            except ValueError:
                continue
            added_rels.append(mapped_rel)

        entity_models = [_entity_to_model(e) for e in entities]
        rel_models = [_rel_to_model(r) for r in added_rels]

        return ExtractEntitiesResponse(
            entities=entity_models,
            relationships=rel_models,
            entity_count=len(entity_models),
            relationship_count=len(rel_models),
        )

    def query_related(self, request: QueryRelatedRequest) -> QueryRelatedResponse:
        """Find entities related to a given entity."""
        related = self._graph.find_related(request.entity_id, max_depth=request.max_depth)
        models = [_entity_to_model(e) for e in related]
        return QueryRelatedResponse(
            entity_id=request.entity_id,
            related=models,
            count=len(models),
        )

    def query_supply_chain(self, request: QuerySupplyChainRequest) -> QuerySupplyChainResponse:
        """Trace the supply chain from an entity."""
        chain = self._graph.trace_supply_chain(
            request.entity_id, direction=request.direction,
        )
        models = [_entity_to_model(e) for e in chain]
        return QuerySupplyChainResponse(
            entity_id=request.entity_id,
            direction=request.direction,
            chain=models,
            count=len(models),
        )

    def query_shared_risks(self, request: QuerySharedRisksRequest) -> QuerySharedRisksResponse:
        """Find risks shared across multiple entities."""
        shared = self._graph.find_shared_risks(request.entity_ids)
        models = [_entity_to_model(e) for e in shared]
        return QuerySharedRisksResponse(
            entity_ids=request.entity_ids,
            shared_risks=models,
            count=len(models),
        )

    def get_stats(self) -> KGStatsResponse:
        """Get summary statistics of the knowledge graph."""
        s = self._graph.stats()
        return KGStatsResponse(
            entity_count=s["entity_count"],
            relationship_count=s["relationship_count"],
            entities_by_type=s["entities_by_type"],
            relationships_by_type=s["relationships_by_type"],
        )
