"""Tests for core knowledge graph operations."""

from decimal import Decimal

import pytest

from src.core.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    Relationship,
    RelationshipType,
)

# ── Fixtures ──────────────────────────────────────────────────


def _company(name: str, ticker: str | None = None) -> Entity:
    return Entity(name=name, entity_type=EntityType.COMPANY, ticker=ticker)


def _risk(name: str) -> Entity:
    return Entity(name=name, entity_type=EntityType.RISK)


def _relationship(
    src: str, tgt: str, rel_type: RelationshipType, evidence: str = ""
) -> Relationship:
    return Relationship(
        source_id=src, target_id=tgt, rel_type=rel_type, evidence=evidence,
    )


# ── Entity CRUD ───────────────────────────────────────────────


class TestAddEntity:
    def test_add_entity_returns_canonical_id(self) -> None:
        kg = KnowledgeGraph()
        eid = kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        assert eid == "ticker:AAPL"

    def test_add_entity_without_ticker_uses_name(self) -> None:
        kg = KnowledgeGraph()
        eid = kg.add_entity(_risk("supply chain disruption"))
        assert eid.startswith("name:")

    def test_add_entity_increments_count(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_entity(_company("Microsoft Corp.", ticker="MSFT"))
        assert kg.entity_count == 2

    def test_add_duplicate_entity_merges_metadata(self) -> None:
        kg = KnowledgeGraph()
        e1 = Entity(
            name="Apple Inc.", entity_type=EntityType.COMPANY,
            ticker="AAPL", metadata={"source": "10-K"},
        )
        e2 = Entity(
            name="Apple Inc.", entity_type=EntityType.COMPANY,
            ticker="AAPL", metadata={"sector": "tech"},
        )
        kg.add_entity(e1)
        kg.add_entity(e2)
        assert kg.entity_count == 1
        retrieved = kg.get_entity("ticker:AAPL")
        assert retrieved is not None
        assert retrieved.metadata["source"] == "10-K"
        assert retrieved.metadata["sector"] == "tech"

    def test_add_entity_promotes_ticker(self) -> None:
        kg = KnowledgeGraph()
        # First add without ticker (uses name-based ID)
        eid = kg.add_entity(_company("Apple Inc."))
        assert eid == "name:apple inc."
        # Add with ticker — different ID, different node
        eid2 = kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        assert eid2 == "ticker:AAPL"
        assert kg.entity_count == 2


class TestGetEntity:
    def test_get_existing_entity(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        entity = kg.get_entity("ticker:AAPL")
        assert entity is not None
        assert entity.name == "Apple Inc."
        assert entity.entity_type == EntityType.COMPANY

    def test_get_nonexistent_entity_returns_none(self) -> None:
        kg = KnowledgeGraph()
        assert kg.get_entity("ticker:FAKE") is None


class TestFindByName:
    def test_find_by_name_case_insensitive(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        entity = kg.find_by_name("apple inc.")
        assert entity is not None
        assert entity.ticker == "AAPL"

    def test_find_by_ticker(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        entity = kg.find_by_name("AAPL")
        assert entity is not None
        assert entity.name == "Apple Inc."

    def test_find_by_name_not_found(self) -> None:
        kg = KnowledgeGraph()
        assert kg.find_by_name("Nonexistent") is None


class TestFindByType:
    def test_find_companies(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_entity(_company("Microsoft Corp.", ticker="MSFT"))
        kg.add_entity(_risk("regulatory risk"))
        companies = kg.find_by_type(EntityType.COMPANY)
        assert len(companies) == 2
        names = {e.name for e in companies}
        assert "Apple Inc." in names
        assert "Microsoft Corp." in names

    def test_find_by_type_empty(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        assert kg.find_by_type(EntityType.TECHNOLOGY) == []


# ── Relationships ─────────────────────────────────────────────


class TestRelationships:
    def test_add_relationship(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        rel = _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.SUPPLIER)
        kg.add_relationship(rel)
        assert kg.relationship_count == 1

    def test_add_relationship_missing_source_raises(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        rel = _relationship("ticker:FAKE", "ticker:AAPL", RelationshipType.SUPPLIER)
        with pytest.raises(ValueError):
            kg.add_relationship(rel)

    def test_add_relationship_missing_target_raises(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        rel = _relationship("ticker:INTC", "ticker:FAKE", RelationshipType.SUPPLIER)
        with pytest.raises(ValueError):
            kg.add_relationship(rel)

    def test_multiple_relationships_same_pair(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.COMPETITOR),
        )
        assert kg.relationship_count == 2

    def test_get_relationships_outgoing(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.SUPPLIER),
        )
        rels = kg.get_relationships("ticker:INTC", direction="outgoing")
        assert len(rels) == 1
        assert rels[0].target_id == "ticker:AAPL"
        assert rels[0].rel_type == RelationshipType.SUPPLIER

    def test_get_relationships_filtered_by_type(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.COMPETITOR),
        )
        rels = kg.get_relationships(
            "ticker:INTC", rel_type=RelationshipType.SUPPLIER,
        )
        assert len(rels) == 1
        assert rels[0].rel_type == RelationshipType.SUPPLIER

    def test_get_relationships_nonexistent_entity(self) -> None:
        kg = KnowledgeGraph()
        assert kg.get_relationships("ticker:FAKE") == []

    def test_relationship_preserves_provenance(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        rel = Relationship(
            source_id="ticker:INTC",
            target_id="ticker:AAPL",
            rel_type=RelationshipType.SUPPLIER,
            evidence="Intel supplies chips to Apple",
            source_doc="10-K-2024",
            confidence=Decimal("0.9"),
        )
        kg.add_relationship(rel)
        retrieved = kg.get_relationships("ticker:INTC")[0]
        assert retrieved.evidence == "Intel supplies chips to Apple"
        assert retrieved.source_doc == "10-K-2024"
        assert retrieved.confidence == Decimal("0.9")


# ── Graph Queries ─────────────────────────────────────────────


class TestFindRelated:
    def test_find_related_depth_1(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("A Corp.", ticker="A"))
        kg.add_entity(_company("B Corp.", ticker="B"))
        kg.add_entity(_company("C Corp.", ticker="C"))
        kg.add_relationship(
            _relationship("ticker:A", "ticker:B", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:B", "ticker:C", RelationshipType.SUPPLIER),
        )
        related = kg.find_related("ticker:A", max_depth=1)
        ids = {e.entity_id for e in related}
        assert "ticker:B" in ids
        assert "ticker:C" not in ids

    def test_find_related_depth_2(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("A Corp.", ticker="A"))
        kg.add_entity(_company("B Corp.", ticker="B"))
        kg.add_entity(_company("C Corp.", ticker="C"))
        kg.add_relationship(
            _relationship("ticker:A", "ticker:B", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:B", "ticker:C", RelationshipType.SUPPLIER),
        )
        related = kg.find_related("ticker:A", max_depth=2)
        ids = {e.entity_id for e in related}
        assert "ticker:B" in ids
        assert "ticker:C" in ids

    def test_find_related_nonexistent_entity(self) -> None:
        kg = KnowledgeGraph()
        assert kg.find_related("ticker:FAKE") == []


class TestFindSharedRisks:
    def test_shared_risks(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_entity(_company("Microsoft Corp.", ticker="MSFT"))
        kg.add_entity(_risk("cybersecurity"))
        kg.add_entity(_risk("regulatory risk"))
        # Both companies share cybersecurity risk
        kg.add_relationship(
            _relationship("ticker:AAPL", "name:cybersecurity", RelationshipType.REGULATORY),
        )
        kg.add_relationship(
            _relationship("ticker:MSFT", "name:cybersecurity", RelationshipType.REGULATORY),
        )
        # Only Apple has regulatory risk
        kg.add_relationship(
            _relationship("ticker:AAPL", "name:regulatory risk", RelationshipType.REGULATORY),
        )
        shared = kg.find_shared_risks(["ticker:AAPL", "ticker:MSFT"])
        assert len(shared) == 1
        assert shared[0].name == "cybersecurity"

    def test_shared_risks_needs_at_least_two_entities(self) -> None:
        kg = KnowledgeGraph()
        assert kg.find_shared_risks(["ticker:AAPL"]) == []

    def test_shared_risks_no_overlap(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("A Corp.", ticker="A"))
        kg.add_entity(_company("B Corp.", ticker="B"))
        kg.add_entity(_risk("risk_a"))
        kg.add_entity(_risk("risk_b"))
        kg.add_relationship(
            _relationship("ticker:A", "name:risk_a", RelationshipType.REGULATORY),
        )
        kg.add_relationship(
            _relationship("ticker:B", "name:risk_b", RelationshipType.REGULATORY),
        )
        assert kg.find_shared_risks(["ticker:A", "ticker:B"]) == []


class TestTraceSupplyChain:
    def test_trace_upstream(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Raw Materials Inc.", ticker="RAW"))
        kg.add_entity(_company("Components Corp.", ticker="CMP"))
        kg.add_entity(_company("Final Product Co.", ticker="FIN"))
        kg.add_relationship(
            _relationship("ticker:RAW", "ticker:CMP", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:CMP", "ticker:FIN", RelationshipType.SUPPLIER),
        )
        chain = kg.trace_supply_chain("ticker:FIN", direction="upstream")
        ids = [e.entity_id for e in chain]
        assert "ticker:CMP" in ids
        assert "ticker:RAW" in ids

    def test_trace_downstream(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Raw Materials Inc.", ticker="RAW"))
        kg.add_entity(_company("Components Corp.", ticker="CMP"))
        kg.add_entity(_company("Final Product Co.", ticker="FIN"))
        kg.add_relationship(
            _relationship("ticker:RAW", "ticker:CMP", RelationshipType.SUPPLIER),
        )
        kg.add_relationship(
            _relationship("ticker:CMP", "ticker:FIN", RelationshipType.SUPPLIER),
        )
        chain = kg.trace_supply_chain("ticker:RAW", direction="downstream")
        ids = [e.entity_id for e in chain]
        assert "ticker:CMP" in ids
        assert "ticker:FIN" in ids

    def test_trace_nonexistent_entity(self) -> None:
        kg = KnowledgeGraph()
        assert kg.trace_supply_chain("ticker:FAKE") == []

    def test_trace_no_chain(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Isolated Corp.", ticker="ISO"))
        assert kg.trace_supply_chain("ticker:ISO") == []


# ── Serialization ─────────────────────────────────────────────


class TestSerialization:
    def test_roundtrip_to_dict(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg.add_entity(_company("Intel Corp.", ticker="INTC"))
        kg.add_relationship(
            _relationship("ticker:INTC", "ticker:AAPL", RelationshipType.SUPPLIER),
        )
        data = kg.to_dict()
        restored = KnowledgeGraph.from_dict(data)
        assert restored.entity_count == 2
        assert restored.relationship_count == 1
        entity = restored.get_entity("ticker:AAPL")
        assert entity is not None
        assert entity.name == "Apple Inc."

    def test_roundtrip_to_json(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("Apple Inc.", ticker="AAPL"))
        json_str = kg.to_json()
        restored = KnowledgeGraph.from_json(json_str)
        assert restored.entity_count == 1

    def test_serialization_preserves_provenance(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("A Corp.", ticker="A"))
        kg.add_entity(_company("B Corp.", ticker="B"))
        rel = Relationship(
            source_id="ticker:A",
            target_id="ticker:B",
            rel_type=RelationshipType.PARTNER,
            evidence="A partners with B",
            source_doc="annual-report-2024",
            confidence=Decimal("0.8"),
        )
        kg.add_relationship(rel)
        restored = KnowledgeGraph.from_dict(kg.to_dict())
        rels = restored.get_relationships("ticker:A")
        assert len(rels) == 1
        assert rels[0].evidence == "A partners with B"
        assert rels[0].source_doc == "annual-report-2024"


# ── Merge ─────────────────────────────────────────────────────


class TestMerge:
    def test_merge_adds_new_entities(self) -> None:
        kg1 = KnowledgeGraph()
        kg1.add_entity(_company("A Corp.", ticker="A"))
        kg2 = KnowledgeGraph()
        kg2.add_entity(_company("B Corp.", ticker="B"))
        kg1.merge(kg2)
        assert kg1.entity_count == 2

    def test_merge_deduplicates_entities(self) -> None:
        kg1 = KnowledgeGraph()
        kg1.add_entity(_company("Apple Inc.", ticker="AAPL"))
        kg2 = KnowledgeGraph()
        kg2.add_entity(
            Entity(
                name="Apple Inc.", entity_type=EntityType.COMPANY,
                ticker="AAPL", metadata={"extra": "data"},
            ),
        )
        kg1.merge(kg2)
        assert kg1.entity_count == 1
        entity = kg1.get_entity("ticker:AAPL")
        assert entity is not None
        assert entity.metadata.get("extra") == "data"

    def test_merge_deduplicates_edges(self) -> None:
        kg1 = KnowledgeGraph()
        kg1.add_entity(_company("A Corp.", ticker="A"))
        kg1.add_entity(_company("B Corp.", ticker="B"))
        rel = _relationship("ticker:A", "ticker:B", RelationshipType.SUPPLIER, evidence="same")
        kg1.add_relationship(rel)

        kg2 = KnowledgeGraph()
        kg2.add_entity(_company("A Corp.", ticker="A"))
        kg2.add_entity(_company("B Corp.", ticker="B"))
        kg2.add_relationship(rel)

        kg1.merge(kg2)
        assert kg1.relationship_count == 1


# ── Stats ─────────────────────────────────────────────────────


class TestStats:
    def test_stats_counts(self) -> None:
        kg = KnowledgeGraph()
        kg.add_entity(_company("A Corp.", ticker="A"))
        kg.add_entity(_risk("cybersecurity"))
        kg.add_entity(_company("B Corp.", ticker="B"))
        kg.add_relationship(
            _relationship("ticker:A", "ticker:B", RelationshipType.COMPETITOR),
        )
        stats = kg.stats()
        assert stats["entity_count"] == 3
        assert stats["relationship_count"] == 1
        assert stats["entities_by_type"]["company"] == 2
        assert stats["entities_by_type"]["risk"] == 1
        assert stats["relationships_by_type"]["competitor"] == 1

    def test_stats_empty_graph(self) -> None:
        kg = KnowledgeGraph()
        stats = kg.stats()
        assert stats["entity_count"] == 0
        assert stats["relationship_count"] == 0
        assert stats["entities_by_type"] == {}
        assert stats["relationships_by_type"] == {}
