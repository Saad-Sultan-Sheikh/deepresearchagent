"""Integration tests for the graph_writer node — requires Neo4j running."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.nodes.graph_writer import GraphWriterError, graph_writer


@pytest.mark.asyncio
async def test_graph_writer_returns_node_ids(base_state, sample_entities):
    """Graph writer should return node IDs on success."""
    base_state["extracted_entities"] = sample_entities

    with patch("src.nodes.graph_writer.neo4j_client.get_driver", AsyncMock()), \
         patch("src.nodes.graph_writer.neo4j_client.run_query", AsyncMock(return_value=[])):
        result = await graph_writer(base_state)

    assert "graph_node_ids" in result
    assert len(result["graph_node_ids"]) >= 1  # At least person + run nodes
    assert result["current_node"] == "graph_writer"


@pytest.mark.asyncio
async def test_graph_writer_raises_on_connection_error(base_state, sample_entities):
    """Fatal Neo4j connection error should raise GraphWriterError."""
    base_state["extracted_entities"] = sample_entities

    with patch(
        "src.nodes.graph_writer.neo4j_client.get_driver",
        AsyncMock(side_effect=Exception("Connection refused")),
    ):
        with pytest.raises(GraphWriterError):
            await graph_writer(base_state)


@pytest.mark.asyncio
async def test_graph_writer_entity_errors_are_non_fatal(base_state, sample_entities):
    """Individual entity write errors should not abort the pipeline."""
    base_state["extracted_entities"] = sample_entities

    call_count = 0

    async def partial_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 3:  # only the per-entity merge fails (non-fatal inner try/except)
            raise Exception("Entity write error")
        return []

    with patch("src.nodes.graph_writer.neo4j_client.get_driver", AsyncMock()), \
         patch("src.nodes.graph_writer.neo4j_client.run_query", partial_fail):
        result = await graph_writer(base_state)

    # Should have errors but not raise
    assert "graph_write_errors" in result
