"""Neo4j async driver wrapper with schema initialization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from src.config import get_settings

log = logging.getLogger(__name__)

_driver: Optional[AsyncDriver] = None


async def get_driver() -> AsyncDriver:
    """Return the module-level Neo4j async driver (lazy init)."""
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def get_session() -> AsyncSession:
    driver = await get_driver()
    return driver.session()


async def init_schema() -> None:
    """Run the Cypher schema file (constraints + indexes) on startup."""
    schema_path = Path(__file__).parent.parent.parent / "neo4j" / "init" / "schema.cypher"
    if not schema_path.exists():
        log.warning("Schema file not found: %s", schema_path)
        return

    cypher_text = schema_path.read_text(encoding="utf-8")
    # Split on semicolons; skip empty blocks and comment-only blocks
    statements = [
        s.strip()
        for s in cypher_text.split(";")
        if s.strip() and not all(
            line.startswith("//") or not line.strip()
            for line in s.strip().splitlines()
        )
    ]

    driver = await get_driver()
    async with driver.session() as session:
        for stmt in statements:
            try:
                await session.run(stmt)
            except Exception as exc:
                log.warning("Schema statement failed (may already exist): %s | %s", stmt[:60], exc)
    log.info("Neo4j schema initialized (%d statements)", len(statements))


async def run_query(
    cypher: str,
    parameters: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Execute a Cypher query and return list of record dicts."""
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, parameters or {})
        records = await result.data()
        return records


async def run_write_query(
    cypher: str,
    parameters: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Execute a write Cypher query in an explicit write transaction."""
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.execute_write(
            lambda tx: tx.run(cypher, parameters or {})
        )
        # execute_write returns the result of the last statement
        if hasattr(result, "data"):
            return await result.data()
        return []
