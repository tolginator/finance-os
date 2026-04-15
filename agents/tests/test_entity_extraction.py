"""Tests for entity and relationship extraction from financial text."""

from src.core.entity_extraction import extract_entities, extract_relationships
from src.core.knowledge_graph import EntityType, RelationshipType

# ── Entity Extraction ─────────────────────────────────────────


class TestCompanyExtraction:
    def test_extracts_company_with_suffix(self) -> None:
        text = "Apple Inc. reported strong earnings this quarter."
        entities = extract_entities(text)
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        assert len(companies) >= 1
        names = {e.name for e in companies}
        assert any("Apple" in n for n in names)

    def test_extracts_multiple_companies(self) -> None:
        text = "Apple Inc. competes with Microsoft Corp. in the cloud market."
        entities = extract_entities(text)
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        assert len(companies) >= 2

    def test_no_companies_in_plain_text(self) -> None:
        text = "The weather is nice today and the birds are singing."
        entities = extract_entities(text)
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        assert len(companies) == 0


class TestRiskExtraction:
    def test_extracts_risk_keywords(self) -> None:
        text = "The company faces significant cybersecurity and regulatory risk."
        entities = extract_entities(text)
        risks = [e for e in entities if e.entity_type == EntityType.RISK]
        assert len(risks) >= 1
        names = {e.name for e in risks}
        assert "cybersecurity" in names or "regulatory risk" in names

    def test_risk_has_category_metadata(self) -> None:
        text = "Supply chain disruption poses a major threat."
        entities = extract_entities(text)
        risks = [e for e in entities if e.entity_type == EntityType.RISK]
        assert len(risks) >= 1
        risk = risks[0]
        assert risk.metadata.get("category") == "supply_chain"

    def test_no_risks_in_clean_text(self) -> None:
        text = "Revenue grew 15% year over year."
        entities = extract_entities(text)
        risks = [e for e in entities if e.entity_type == EntityType.RISK]
        assert len(risks) == 0


class TestTechnologyExtraction:
    def test_extracts_technology_keywords(self) -> None:
        text = "The company is investing heavily in artificial intelligence and cloud computing."
        entities = extract_entities(text)
        techs = [e for e in entities if e.entity_type == EntityType.TECHNOLOGY]
        assert len(techs) >= 1
        names = {e.name.lower() for e in techs}
        assert "artificial intelligence" in names or "cloud computing" in names

    def test_no_tech_in_non_tech_text(self) -> None:
        text = "The company sells shoes and clothing."
        entities = extract_entities(text)
        techs = [e for e in entities if e.entity_type == EntityType.TECHNOLOGY]
        assert len(techs) == 0


class TestEntityProvenance:
    def test_source_doc_propagated(self) -> None:
        text = "Apple Inc. is a major technology company."
        entities = extract_entities(text, source_doc="10-K-2024")
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        assert len(companies) >= 1
        assert companies[0].metadata.get("source_doc") == "10-K-2024"

    def test_evidence_captured(self) -> None:
        text = "Apple Inc. reported record revenue."
        entities = extract_entities(text)
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        assert len(companies) >= 1
        assert companies[0].metadata.get("evidence") is not None
        assert len(companies[0].metadata["evidence"]) > 0


class TestEntityDeduplication:
    def test_same_entity_mentioned_twice_deduped(self) -> None:
        text = "Apple Inc. is growing. Apple Inc. reported earnings."
        entities = extract_entities(text)
        companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
        apple_count = sum(1 for c in companies if "Apple" in c.name)
        assert apple_count == 1


# ── Relationship Extraction ──────────────────────────────────


class TestRelationshipExtraction:
    def test_supplier_relationship(self) -> None:
        text = "Intel Corp. supplies chips to Apple Inc. for their devices."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        supplier_rels = [r for r in rels if r.rel_type == RelationshipType.SUPPLIER]
        assert len(supplier_rels) >= 1

    def test_competitor_relationship(self) -> None:
        text = "Apple Inc. competes with Microsoft Corp. in the tablet market."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        competitor_rels = [r for r in rels if r.rel_type == RelationshipType.COMPETITOR]
        assert len(competitor_rels) >= 1

    def test_no_relationships_with_single_entity(self) -> None:
        text = "Apple Inc. is a great company."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        assert len(rels) == 0

    def test_no_relationships_without_indicators(self) -> None:
        text = "Apple Inc. and Microsoft Corp. are both in technology."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        # "and" is not a relationship indicator
        assert len(rels) == 0

    def test_relationship_has_evidence(self) -> None:
        text = "Intel Corp. supplies processors to Apple Inc. every quarter."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        assert len(rels) >= 1
        assert rels[0].evidence != ""
        assert len(rels[0].evidence) > 0

    def test_relationship_source_doc_propagated(self) -> None:
        text = "Intel Corp. supplies chips to Apple Inc. for production."
        entities = extract_entities(text, source_doc="10-K")
        rels = extract_relationships(text, entities, source_doc="10-K")
        assert len(rels) >= 1
        assert rels[0].source_doc == "10-K"

    def test_subsidiary_relationship(self) -> None:
        text = "YouTube LLC is a subsidiary of Alphabet Inc. since 2006."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        sub_rels = [r for r in rels if r.rel_type == RelationshipType.SUBSIDIARY]
        assert len(sub_rels) >= 1

    def test_empty_text_yields_no_entities(self) -> None:
        entities = extract_entities("")
        assert len(entities) == 0

    def test_empty_text_yields_no_relationships(self) -> None:
        rels = extract_relationships("", [])
        assert len(rels) == 0
