"""Entity and relationship extraction from financial text.

v1 uses high-precision regex patterns and keyword taxonomies.
Designed for low recall, high precision — every extraction carries
provenance (evidence text and source document).
"""

import re
from decimal import Decimal

from src.core.knowledge_graph import (
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
)

# ── Company patterns ─────────────────────────────────────────

_COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z&\s]+?)"
    r"\s*(?:Inc\.?|Corp\.?|Corporation|Ltd\.?|LLC|Company|Co\.|Group|Holdings|Enterprises)"
    r"(?:\b|(?=\s|$|,|;))",
)

# ── Risk taxonomy ─────────────────────────────────────────────

_RISK_KEYWORDS: dict[str, str] = {
    "supply chain disruption": "supply_chain",
    "supply chain risk": "supply_chain",
    "cybersecurity": "cybersecurity",
    "cyber risk": "cybersecurity",
    "data breach": "cybersecurity",
    "regulatory risk": "regulatory",
    "regulatory change": "regulatory",
    "compliance risk": "regulatory",
    "interest rate risk": "market",
    "currency risk": "market",
    "foreign exchange risk": "market",
    "inflation risk": "market",
    "credit risk": "credit",
    "counterparty risk": "credit",
    "litigation risk": "legal",
    "legal proceedings": "legal",
    "geopolitical risk": "geopolitical",
    "climate risk": "environmental",
    "environmental risk": "environmental",
    "concentration risk": "concentration",
    "liquidity risk": "liquidity",
}

_RISK_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _RISK_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ── Technology patterns ───────────────────────────────────────

_TECH_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "cloud computing",
    "blockchain",
    "5G",
    "IoT",
    "quantum computing",
    "edge computing",
    "SaaS",
    "PaaS",
    "IaaS",
    "ERP",
    "CRM",
    "API",
    "microservices",
]

_TECH_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _TECH_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ── Relationship patterns ────────────────────────────────────

_RELATIONSHIP_PATTERNS: list[tuple[re.Pattern[str], RelationshipType, str]] = [
    (
        re.compile(r"(?:supplier|supplies|supply)\s+\w*\s*(?:to|of|for)\b", re.IGNORECASE),
        RelationshipType.SUPPLIER,
        "outgoing",
    ),
    (
        re.compile(r"(?:sourced?|procured?|purchased?)\s+from\b", re.IGNORECASE),
        RelationshipType.SUPPLIER,
        "incoming",
    ),
    (
        re.compile(r"\bcompete[sd]?\s+with\b", re.IGNORECASE),
        RelationshipType.COMPETITOR,
        "outgoing",
    ),
    (
        re.compile(r"\bcustomer\s+of\b", re.IGNORECASE),
        RelationshipType.CUSTOMER,
        "outgoing",
    ),
    (
        re.compile(r"\bsubsidiary\s+of\b", re.IGNORECASE),
        RelationshipType.SUBSIDIARY,
        "outgoing",
    ),
    (
        re.compile(r"\bacquired?\b", re.IGNORECASE),
        RelationshipType.SUBSIDIARY,
        "incoming",
    ),
    (
        re.compile(r"\bpartner(?:ship|ed|s)?\s+with\b", re.IGNORECASE),
        RelationshipType.PARTNER,
        "outgoing",
    ),
    (
        re.compile(r"\buses?\b.*\b(?:technology|platform|software|system)\b", re.IGNORECASE),
        RelationshipType.TECHNOLOGY_USER,
        "outgoing",
    ),
    (
        re.compile(r"\bsubject\s+to\b.*\bregulat", re.IGNORECASE),
        RelationshipType.REGULATORY,
        "outgoing",
    ),
]


def _context_window(text: str, start: int, end: int, window: int = 100) -> str:
    """Extract surrounding context for provenance."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    return text[ctx_start:ctx_end].strip()


def extract_entities(text: str, source_doc: str = "") -> list[Entity]:
    """Extract entities from financial text.

    High-precision, low-recall: only extracts entities matching
    well-defined patterns.

    Args:
        text: The text to extract from.
        source_doc: Source document identifier for provenance.

    Returns:
        Deduplicated list of extracted entities.
    """
    seen: dict[str, Entity] = {}

    # Companies via suffix pattern (e.g., "Apple Inc.")
    for match in _COMPANY_SUFFIX_PATTERN.finditer(text):
        name = match.group(0).strip().rstrip(".")
        entity = Entity(
            name=name,
            entity_type=EntityType.COMPANY,
            metadata={"source_doc": source_doc, "evidence": _context_window(text, *match.span())},
        )
        key = entity.entity_id
        if key not in seen:
            seen[key] = entity

    # Risks via taxonomy
    for match in _RISK_PATTERN.finditer(text):
        risk_name = match.group(1).lower()
        category = _RISK_KEYWORDS.get(risk_name, "unknown")
        entity = Entity(
            name=risk_name,
            entity_type=EntityType.RISK,
            metadata={
                "category": category,
                "source_doc": source_doc,
                "evidence": _context_window(text, *match.span()),
            },
        )
        key = entity.entity_id
        if key not in seen:
            seen[key] = entity

    # Technologies via keywords
    for match in _TECH_PATTERN.finditer(text):
        tech_name = match.group(1)
        entity = Entity(
            name=tech_name,
            entity_type=EntityType.TECHNOLOGY,
            metadata={"source_doc": source_doc, "evidence": _context_window(text, *match.span())},
        )
        key = entity.entity_id
        if key not in seen:
            seen[key] = entity

    return list(seen.values())


def extract_relationships(
    text: str,
    entities: list[Entity],
    source_doc: str = "",
) -> list[Relationship]:
    """Extract relationships between entities found in text.

    Scans for relationship indicator phrases near entity mentions.
    Only creates relationships between entities already extracted.

    Args:
        text: The text to scan for relationship patterns.
        entities: Entities previously extracted from the same text.
        source_doc: Source document identifier for provenance.

    Returns:
        List of extracted relationships with evidence.
    """
    if len(entities) < 2:
        return []

    # Build entity mention positions
    entity_positions: list[tuple[int, int, Entity]] = []
    for entity in entities:
        pattern = re.compile(r"\b" + re.escape(entity.name) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            entity_positions.append((match.start(), match.end(), entity))
    entity_positions.sort(key=lambda x: x[0])

    relationships: list[Relationship] = []
    seen_keys: set[str] = set()

    for rel_pattern, rel_type, direction in _RELATIONSHIP_PATTERNS:
        for match in rel_pattern.finditer(text):
            rel_start, rel_end = match.span()

            # Find nearest entity before and after the relationship phrase
            before = [
                (s, e, ent) for s, e, ent in entity_positions
                if e <= rel_start and rel_start - e < 200
            ]
            after = [
                (s, e, ent) for s, e, ent in entity_positions
                if s >= rel_end and s - rel_end < 200
            ]

            if not before or not after:
                continue

            subject = before[-1][2]
            obj = after[0][2]

            if subject.entity_id == obj.entity_id:
                continue

            if direction == "outgoing":
                src, tgt = subject.entity_id, obj.entity_id
            else:
                src, tgt = obj.entity_id, subject.entity_id

            evidence = _context_window(text, rel_start, rel_end, window=150)
            rel = Relationship(
                source_id=src,
                target_id=tgt,
                rel_type=rel_type,
                evidence=evidence,
                source_doc=source_doc,
                confidence=Decimal("0.6"),
                metadata={},
            )

            if rel.edge_key not in seen_keys:
                seen_keys.add(rel.edge_key)
                relationships.append(rel)

    return relationships
