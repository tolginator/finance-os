"""Tests for the knowledge graph service layer."""

from src.application.contracts.knowledge_graph import (
    ExtractEntitiesRequest,
    QueryRelatedRequest,
    QuerySharedRisksRequest,
    QuerySupplyChainRequest,
)
from src.application.services.kg_service import KnowledgeGraphService
from src.core.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    Relationship,
    RelationshipType,
)


def _seeded_service() -> KnowledgeGraphService:
    """Create a service with a pre-populated graph for query tests."""
    graph = KnowledgeGraph()
    apple = Entity(name="Apple Inc.", entity_type=EntityType.COMPANY, ticker="AAPL")
    intel = Entity(name="Intel Corp.", entity_type=EntityType.COMPANY, ticker="INTC")
    msft = Entity(name="Microsoft Corp.", entity_type=EntityType.COMPANY, ticker="MSFT")
    cyber = Entity(name="cybersecurity", entity_type=EntityType.RISK)

    graph.add_entity(apple)
    graph.add_entity(intel)
    graph.add_entity(msft)
    graph.add_entity(cyber)

    graph.add_relationship(Relationship(
        source_id="ticker:INTC", target_id="ticker:AAPL",
        rel_type=RelationshipType.SUPPLIER, evidence="Intel supplies to Apple",
    ))
    graph.add_relationship(Relationship(
        source_id="ticker:AAPL", target_id="name:cybersecurity",
        rel_type=RelationshipType.REGULATORY,
    ))
    graph.add_relationship(Relationship(
        source_id="ticker:MSFT", target_id="name:cybersecurity",
        rel_type=RelationshipType.REGULATORY,
    ))
    return KnowledgeGraphService(graph)


# ── Extract & Ingest ──────────────────────────────────────────


class TestExtractAndIngest:
    def test_extracts_entities_from_text(self) -> None:
        svc = KnowledgeGraphService()
        req = ExtractEntitiesRequest(
            text="Apple Inc. is facing cybersecurity concerns.",
            source_doc="10-K-2024",
        )
        resp = svc.extract_and_ingest(req)
        assert resp.entity_count >= 1
        assert len(resp.entities) == resp.entity_count

    def test_ingested_entities_persist_in_graph(self) -> None:
        svc = KnowledgeGraphService()
        req = ExtractEntitiesRequest(
            text="Microsoft Corp. invests in artificial intelligence.",
        )
        svc.extract_and_ingest(req)
        assert svc.graph.entity_count >= 1

    def test_ticker_associated_with_first_company(self) -> None:
        svc = KnowledgeGraphService()
        req = ExtractEntitiesRequest(
            text="Apple Inc. reported record revenue.",
            ticker="AAPL",
        )
        resp = svc.extract_and_ingest(req)
        apple_entities = [e for e in resp.entities if "Apple" in e.name]
        assert len(apple_entities) >= 1
        assert apple_entities[0].ticker == "AAPL"

    def test_empty_text_rejected(self) -> None:
        import pydantic
        try:
            ExtractEntitiesRequest(text="")
            assert False, "Should have raised validation error"
        except pydantic.ValidationError:
            pass

    def test_extract_with_relationships(self) -> None:
        svc = KnowledgeGraphService()
        req = ExtractEntitiesRequest(
            text="Intel Corp. supplies processors to Apple Inc. for their products.",
        )
        resp = svc.extract_and_ingest(req)
        # Should have at least entities; relationships depend on pattern matching
        assert resp.entity_count >= 2

    def test_multiple_extractions_accumulate(self) -> None:
        svc = KnowledgeGraphService()
        svc.extract_and_ingest(ExtractEntitiesRequest(
            text="Apple Inc. is a technology company.",
        ))
        svc.extract_and_ingest(ExtractEntitiesRequest(
            text="Microsoft Corp. is also a technology company.",
        ))
        assert svc.graph.entity_count >= 2


# ── Query Related ─────────────────────────────────────────────


class TestQueryRelated:
    def test_query_related_returns_neighbors(self) -> None:
        svc = _seeded_service()
        resp = svc.query_related(QueryRelatedRequest(
            entity_id="ticker:AAPL", max_depth=1,
        ))
        assert resp.count >= 1
        ids = {e.entity_id for e in resp.related}
        assert "ticker:INTC" in ids

    def test_query_related_nonexistent_entity(self) -> None:
        svc = _seeded_service()
        resp = svc.query_related(QueryRelatedRequest(
            entity_id="ticker:FAKE", max_depth=1,
        ))
        assert resp.count == 0
        assert resp.related == []

    def test_query_related_empty_id_rejected(self) -> None:
        import pydantic
        try:
            QueryRelatedRequest(entity_id="")
            assert False, "Should have raised validation error"
        except pydantic.ValidationError:
            pass


# ── Query Supply Chain ────────────────────────────────────────


class TestQuerySupplyChain:
    def test_upstream_supply_chain(self) -> None:
        svc = _seeded_service()
        resp = svc.query_supply_chain(QuerySupplyChainRequest(
            entity_id="ticker:AAPL", direction="upstream",
        ))
        ids = [e.entity_id for e in resp.chain]
        assert "ticker:INTC" in ids

    def test_supply_chain_nonexistent_entity(self) -> None:
        svc = _seeded_service()
        resp = svc.query_supply_chain(QuerySupplyChainRequest(
            entity_id="ticker:FAKE",
        ))
        assert resp.count == 0

    def test_invalid_direction_rejected(self) -> None:
        import pydantic
        try:
            QuerySupplyChainRequest(entity_id="ticker:AAPL", direction="sideways")
            assert False, "Should have raised validation error"
        except pydantic.ValidationError:
            pass


# ── Query Shared Risks ───────────────────────────────────────


class TestQuerySharedRisks:
    def test_finds_shared_risks(self) -> None:
        svc = _seeded_service()
        resp = svc.query_shared_risks(QuerySharedRisksRequest(
            entity_ids=["ticker:AAPL", "ticker:MSFT"],
        ))
        assert resp.count >= 1
        risk_names = {r.name for r in resp.shared_risks}
        assert "cybersecurity" in risk_names

    def test_no_shared_risks(self) -> None:
        svc = _seeded_service()
        resp = svc.query_shared_risks(QuerySharedRisksRequest(
            entity_ids=["ticker:AAPL", "ticker:INTC"],
        ))
        assert resp.count == 0

    def test_fewer_than_two_entities_rejected(self) -> None:
        import pydantic
        try:
            QuerySharedRisksRequest(entity_ids=["ticker:AAPL"])
            assert False, "Should have raised validation error"
        except pydantic.ValidationError:
            pass


# ── Stats ─────────────────────────────────────────────────────


class TestGetStats:
    def test_stats_reflects_graph(self) -> None:
        svc = _seeded_service()
        resp = svc.get_stats()
        assert resp.entity_count == 4
        assert resp.relationship_count == 3
        assert resp.entities_by_type["company"] == 3
        assert resp.entities_by_type["risk"] == 1

    def test_stats_empty_graph(self) -> None:
        svc = KnowledgeGraphService()
        resp = svc.get_stats()
        assert resp.entity_count == 0
        assert resp.relationship_count == 0
