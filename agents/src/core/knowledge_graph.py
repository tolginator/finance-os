"""Knowledge graph for company/entity relationship mapping.

Wraps networkx.MultiDiGraph with typed entities, relationships, and
financial-domain query operations.
"""

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

import networkx as nx


class EntityType(StrEnum):
    """Types of entities in the knowledge graph."""

    COMPANY = "company"
    PRODUCT = "product"
    RISK = "risk"
    TECHNOLOGY = "technology"
    PERSON = "person"
    SECTOR = "sector"


class RelationshipType(StrEnum):
    """Types of directed relationships between entities.

    Edge direction conventions (source → target):
        SUPPLIER:        source supplies to target
        CUSTOMER:        source is a customer of target
        COMPETITOR:      source competes with target (bidirectional semantics)
        TECHNOLOGY_USER: source uses technology target
        REGULATORY:      source is subject to regulatory target
        SUBSIDIARY:      source is a subsidiary of target
        PARTNER:         source partners with target (bidirectional semantics)
    """

    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    TECHNOLOGY_USER = "technology_user"
    REGULATORY = "regulatory"
    SUBSIDIARY = "subsidiary"
    PARTNER = "partner"


@dataclass(frozen=True)
class Entity:
    """A node in the knowledge graph."""

    name: str
    entity_type: EntityType
    ticker: str | None = None
    cik: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def entity_id(self) -> str:
        """Canonical identity: ticker > cik > normalized name."""
        if self.ticker:
            return f"ticker:{self.ticker.upper()}"
        if self.cik:
            return f"cik:{self.cik}"
        return f"name:{self.name.lower().strip()}"


@dataclass(frozen=True)
class Relationship:
    """A directed edge in the knowledge graph with provenance."""

    source_id: str
    target_id: str
    rel_type: RelationshipType
    evidence: str = ""
    source_doc: str = ""
    confidence: Decimal = Decimal("0.5")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def edge_key(self) -> str:
        """Deterministic key for dedup across ingestions."""
        raw = f"{self.source_id}|{self.target_id}|{self.rel_type.value}|{self.evidence}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class KnowledgeGraph:
    """In-memory knowledge graph backed by networkx.MultiDiGraph.

    Supports multiple relationship types between the same entity pair,
    provenance tracking, and financial-domain queries.
    """

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()

    # ── Mutation ──────────────────────────────────────────────

    def add_entity(self, entity: Entity) -> str:
        """Add or update an entity node. Returns the entity_id."""
        eid = entity.entity_id
        attrs = {
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "ticker": entity.ticker,
            "cik": entity.cik,
            "metadata": dict(entity.metadata),
        }
        if eid in self._graph:
            # Merge metadata when same entity_id is added again
            existing = self._graph.nodes[eid]
            merged_meta = {**existing.get("metadata", {}), **entity.metadata}
            attrs["metadata"] = merged_meta
            # Enrich ticker/cik on the existing node if previously missing
            if entity.ticker and not existing.get("ticker"):
                attrs["ticker"] = entity.ticker
            if entity.cik and not existing.get("cik"):
                attrs["cik"] = entity.cik
        self._graph.add_node(eid, **attrs)
        return eid

    def add_relationship(self, rel: Relationship) -> str:
        """Add a relationship edge. Returns the edge key."""
        if rel.source_id not in self._graph:
            msg = f"Source entity '{rel.source_id}' not in graph"
            raise ValueError(msg)
        if rel.target_id not in self._graph:
            msg = f"Target entity '{rel.target_id}' not in graph"
            raise ValueError(msg)
        key = rel.edge_key
        self._graph.add_edge(
            rel.source_id,
            rel.target_id,
            key=key,
            rel_type=rel.rel_type.value,
            evidence=rel.evidence,
            source_doc=rel.source_doc,
            confidence=str(rel.confidence),
            metadata=dict(rel.metadata),
        )
        return key

    # ── Queries ───────────────────────────────────────────────

    def get_entity(self, entity_id: str) -> Entity | None:
        """Look up an entity by its canonical ID."""
        if entity_id not in self._graph:
            return None
        data = self._graph.nodes[entity_id]
        return Entity(
            name=data["name"],
            entity_type=EntityType(data["entity_type"]),
            ticker=data.get("ticker"),
            cik=data.get("cik"),
            metadata=data.get("metadata", {}),
        )

    def find_by_name(self, name: str) -> Entity | None:
        """Resolve an entity by name (case-insensitive)."""
        normalized = name.lower().strip()
        for nid, data in self._graph.nodes(data=True):
            if data["name"].lower().strip() == normalized:
                return self.get_entity(nid)
            if data.get("ticker") and data["ticker"].upper() == name.upper().strip():
                return self.get_entity(nid)
        return None

    def find_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Return all entities of a given type."""
        result = []
        for nid, data in self._graph.nodes(data=True):
            if data.get("entity_type") == entity_type.value:
                entity = self.get_entity(nid)
                if entity:
                    result.append(entity)
        return result

    def get_relationships(
        self,
        entity_id: str,
        rel_type: RelationshipType | None = None,
        direction: str = "both",
    ) -> list[Relationship]:
        """Get relationships for an entity, optionally filtered by type and direction.

        Args:
            entity_id: The canonical entity ID.
            rel_type: Optional filter by relationship type.
            direction: "outgoing", "incoming", or "both".
        """
        if entity_id not in self._graph:
            return []
        edges: list[tuple[str, str, dict[str, Any]]] = []
        if direction in ("outgoing", "both"):
            edges.extend(
                (u, v, d)
                for u, v, d in self._graph.out_edges(entity_id, data=True)
            )
        if direction in ("incoming", "both"):
            edges.extend(
                (u, v, d)
                for u, v, d in self._graph.in_edges(entity_id, data=True)
            )
        result = []
        for u, v, data in edges:
            if rel_type and data.get("rel_type") != rel_type.value:
                continue
            result.append(Relationship(
                source_id=u,
                target_id=v,
                rel_type=RelationshipType(data["rel_type"]),
                evidence=data.get("evidence", ""),
                source_doc=data.get("source_doc", ""),
                confidence=Decimal(data.get("confidence", "0.5")),
                metadata=data.get("metadata", {}),
            ))
        return result

    def find_related(self, entity_id: str, max_depth: int = 2) -> list[Entity]:
        """Find all entities reachable within max_depth hops (undirected traversal)."""
        if entity_id not in self._graph:
            return []
        undirected = self._graph.to_undirected(as_view=True)
        visited: set[str] = set()
        frontier = {entity_id}
        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for neighbor in undirected.neighbors(nid):
                    if neighbor not in visited and neighbor != entity_id:
                        next_frontier.add(neighbor)
            visited.update(frontier)
            frontier = next_frontier - visited
        visited.update(frontier)
        visited.discard(entity_id)
        return [e for eid in visited if (e := self.get_entity(eid)) is not None]

    def find_shared_risks(self, entity_ids: list[str]) -> list[Entity]:
        """Find RISK entities connected to all of the given entities."""
        if len(entity_ids) < 2:
            return []
        risk_sets: list[set[str]] = []
        for eid in entity_ids:
            connected_risks: set[str] = set()
            for rel in self.get_relationships(eid):
                target = rel.target_id if rel.source_id == eid else rel.source_id
                entity = self.get_entity(target)
                if entity and entity.entity_type == EntityType.RISK:
                    connected_risks.add(target)
            risk_sets.append(connected_risks)
        shared = risk_sets[0]
        for rs in risk_sets[1:]:
            shared = shared & rs
        return [e for rid in shared if (e := self.get_entity(rid)) is not None]

    def trace_supply_chain(
        self, entity_id: str, direction: str = "upstream"
    ) -> list[Entity]:
        """Trace the supply chain from an entity.

        Args:
            entity_id: Starting entity.
            direction: "upstream" follows SUPPLIER edges backward (who supplies to me),
                       "downstream" follows SUPPLIER edges forward (who I supply to).
        """
        if entity_id not in self._graph:
            return []
        chain: list[str] = []
        visited: set[str] = {entity_id}
        frontier: deque[str] = deque([entity_id])

        while frontier:
            current = frontier.popleft()
            if direction == "upstream":
                edges = self._graph.in_edges(current, data=True)
                candidates = [
                    u for u, _, d in edges
                    if d.get("rel_type") == RelationshipType.SUPPLIER.value
                ]
            else:
                edges = self._graph.out_edges(current, data=True)
                candidates = [
                    v for _, v, d in edges
                    if d.get("rel_type") == RelationshipType.SUPPLIER.value
                ]
            for nid in candidates:
                if nid not in visited:
                    visited.add(nid)
                    chain.append(nid)
                    frontier.append(nid)

        return [e for eid in chain if (e := self.get_entity(eid)) is not None]

    # ── Stats ─────────────────────────────────────────────────

    @property
    def entity_count(self) -> int:
        """Total number of entities."""
        return self._graph.number_of_nodes()

    @property
    def relationship_count(self) -> int:
        """Total number of relationships."""
        return self._graph.number_of_edges()

    def stats(self) -> dict[str, Any]:
        """Summary statistics of the graph."""
        type_counts: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            t = data.get("entity_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        rel_counts: dict[str, int] = {}
        for _, _, data in self._graph.edges(data=True):
            r = data.get("rel_type", "unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1
        return {
            "entity_count": self.entity_count,
            "relationship_count": self.relationship_count,
            "entities_by_type": type_counts,
            "relationships_by_type": rel_counts,
        }

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a JSON-compatible dict."""
        entities = []
        for nid, data in self._graph.nodes(data=True):
            entities.append({"id": nid, **data})
        relationships = []
        for u, v, _key, data in self._graph.edges(keys=True, data=True):
            relationships.append({"source": u, "target": v, "key": _key, **data})
        return {"entities": entities, "relationships": relationships}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialize a graph from a dict (does not mutate the input)."""
        kg = cls()
        for node in data.get("entities", []):
            node = dict(node)
            nid = node.pop("id")
            kg._graph.add_node(nid, **node)
        for edge in data.get("relationships", []):
            edge = dict(edge)
            src = edge.pop("source")
            tgt = edge.pop("target")
            key = edge.pop("key", None)
            kg._graph.add_edge(src, tgt, key=key, **edge)
        return kg

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def merge(self, other: Self) -> None:
        """Merge another graph into this one. Deduplicates by entity_id and edge_key."""
        for nid, data in other._graph.nodes(data=True):
            if nid in self._graph:
                existing = self._graph.nodes[nid]
                merged_meta = {**existing.get("metadata", {}), **data.get("metadata", {})}
                self._graph.nodes[nid].update({**data, "metadata": merged_meta})
            else:
                self._graph.add_node(nid, **data)
        for u, v, key, data in other._graph.edges(keys=True, data=True):
            if not self._graph.has_edge(u, v, key=key):
                self._graph.add_edge(u, v, key=key, **data)
