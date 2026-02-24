"""Node 4 — Graph Writer: persists extracted entities to Neo4j (idempotent MERGE)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from src.agent.state import ResearchState
from src.clients import neo4j_client
from src.config import get_settings
from src.models.entities import Entity, ExtractedEntities, Relationship

log = logging.getLogger(__name__)

NODE_NAME = "graph_writer"


class GraphWriterError(Exception):
    pass


async def graph_writer(state: ResearchState) -> dict:
    """Persist entities and relationships to Neo4j using MERGE."""
    t0 = time.monotonic()
    settings = get_settings()
    entities: ExtractedEntities = state["extracted_entities"]
    persona_id = state["persona_id"]
    run_id = state["run_id"]
    now = datetime.now(timezone.utc).isoformat()

    # Skip graph persistence if Neo4j is disabled (e.g. no Docker / no Neo4j installed)
    if not settings.neo4j_enabled:
        log.info("[%s] Neo4j disabled — skipping graph write", run_id)
        duration = time.monotonic() - t0
        timings = dict(state.get("node_timings") or {})
        timings[NODE_NAME] = duration
        return {
            "graph_node_ids": [],
            "graph_relationship_ids": [],
            "graph_write_errors": ["Neo4j disabled via NEO4J_ENABLED=false"],
            "current_node": NODE_NAME,
            "node_timings": timings,
            "errors": [],
        }

    log.info("[%s] Writing %d entities to Neo4j", run_id, len(entities.entities))

    node_ids: list[str] = []
    rel_ids: list[str] = []
    write_errors: list[str] = []

    try:
        # Ensure connection
        await neo4j_client.get_driver()

        # Create Run node
        await _merge_run_node(run_id, persona_id, now)
        node_ids.append(f"run_{run_id}")

        # Create Person node for the target
        person_node_id = await _merge_person_node(entities, persona_id, run_id, now)
        node_ids.append(person_node_id)

        # Create and link all other entities
        for entity in entities.entities:
            try:
                node_id = await _merge_entity_node(entity, run_id, now)
                node_ids.append(node_id)
            except Exception as exc:
                write_errors.append(f"Entity merge failed [{entity.entity_id}]: {exc}")

        # Write relationships
        for rel in entities.relationships:
            try:
                rel_id = await _merge_relationship(rel, now)
                rel_ids.append(rel_id)
            except Exception as exc:
                write_errors.append(f"Relationship merge failed [{rel.relationship_id}]: {exc}")

        # Link Run → Person
        await _link_run_to_person(run_id, person_node_id)

    except Exception as exc:
        raise GraphWriterError(f"Fatal Neo4j error: {exc}") from exc

    duration = time.monotonic() - t0
    log.info(
        "[%s] Graph writer done: %d nodes, %d rels, %d errors (%.2fs)",
        run_id, len(node_ids), len(rel_ids), len(write_errors), duration,
    )

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "graph_node_ids": node_ids,
        "graph_relationship_ids": rel_ids,
        "graph_write_errors": write_errors,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": write_errors,
    }


async def _merge_run_node(run_id: str, persona_id: str, now: str) -> None:
    cypher = """
    MERGE (r:Run {run_id: $run_id})
    SET r.persona_id = $persona_id,
        r.created_at = $now
    """
    await neo4j_client.run_query(cypher, {"run_id": run_id, "persona_id": persona_id, "now": now})


async def _merge_person_node(
    entities: ExtractedEntities,
    persona_id: str,
    run_id: str,
    now: str,
) -> str:
    node_id = f"person_{persona_id}"
    cypher = """
    MERGE (p:Person {entity_id: $entity_id})
    SET p.value = $name,
        p.persona_id = $persona_id,
        p.run_id = $run_id,
        p.extracted_at = $now,
        p.nationalities = $nationalities,
        p.date_of_birth = $dob
    RETURN p.entity_id AS id
    """
    await neo4j_client.run_query(
        cypher,
        {
            "entity_id": node_id,
            "name": entities.primary_name or "Unknown",
            "persona_id": persona_id,
            "run_id": run_id,
            "now": now,
            "nationalities": entities.nationalities,
            "dob": entities.date_of_birth or "",
        },
    )
    return node_id


async def _merge_entity_node(entity: Entity, run_id: str, now: str) -> str:
    label = _sanitize_label(entity.label)
    cypher = f"""
    MERGE (n:{label} {{entity_id: $entity_id}})
    SET n.value = $value,
        n.confidence = $confidence,
        n.source_urls = $source_urls,
        n.run_id = $run_id,
        n.extracted_at = $now
    RETURN n.entity_id AS id
    """
    await neo4j_client.run_query(
        cypher,
        {
            "entity_id": entity.entity_id,
            "value": entity.value,
            "confidence": entity.confidence,
            "source_urls": entity.source_urls,
            "run_id": run_id,
            "now": now,
        },
    )
    return entity.entity_id


async def _merge_relationship(rel: Relationship, now: str) -> str:
    rel_type = _sanitize_rel_type(rel.type)
    cypher = f"""
    MATCH (src {{entity_id: $src_id}})
    MATCH (tgt {{entity_id: $tgt_id}})
    MERGE (src)-[r:{rel_type} {{relationship_id: $rel_id}}]->(tgt)
    SET r.confidence = $confidence,
        r.evidence = $evidence,
        r.created_at = $now
    RETURN r.relationship_id AS id
    """
    await neo4j_client.run_query(
        cypher,
        {
            "src_id": rel.source_entity_id,
            "tgt_id": rel.target_entity_id,
            "rel_id": rel.relationship_id,
            "confidence": rel.confidence,
            "evidence": rel.evidence,
            "now": now,
        },
    )
    return rel.relationship_id


async def _link_run_to_person(run_id: str, person_node_id: str) -> None:
    cypher = """
    MATCH (r:Run {run_id: $run_id})
    MATCH (p:Person {entity_id: $person_id})
    MERGE (r)-[:PRODUCED]->(p)
    """
    await neo4j_client.run_query(cypher, {"run_id": run_id, "person_id": person_node_id})


def _sanitize_label(label: str) -> str:
    """Allow only alphanumeric label names."""
    return "".join(c for c in label if c.isalnum() or c == "_")


def _sanitize_rel_type(rel_type: str) -> str:
    """Allow only uppercase alphanumeric + underscore relationship types."""
    return "".join(c for c in rel_type.upper() if c.isalnum() or c == "_")
