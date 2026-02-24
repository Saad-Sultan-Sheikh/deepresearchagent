"""Unit tests for the extractor node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.entities import ExtractedEntities
from src.nodes.extractor import extractor


@pytest.mark.asyncio
async def test_extractor_returns_entities(base_state, sample_entities):
    with patch(
        "src.nodes.extractor.gemini_client.structured_completion",
        AsyncMock(return_value=sample_entities),
    ):
        result = await extractor(base_state)

    assert result["extracted_entities"] is not None
    assert result["extracted_entities"].primary_name == "Alice Test Person"
    assert result["current_node"] == "extractor"


@pytest.mark.asyncio
async def test_extractor_backfills_run_metadata(base_state, sample_entities):
    # Return entity with wrong run_id — should be overwritten
    sample_entities.run_id = "wrong_id"
    sample_entities.persona_id = "wrong_persona"

    with patch(
        "src.nodes.extractor.gemini_client.structured_completion",
        AsyncMock(return_value=sample_entities),
    ):
        result = await extractor(base_state)

    assert result["extracted_entities"].run_id == "abc12345"
    assert result["extracted_entities"].persona_id == "test_001"


@pytest.mark.asyncio
async def test_extractor_returns_empty_on_failure(base_state):
    with patch(
        "src.nodes.extractor.gemini_client.structured_completion",
        AsyncMock(side_effect=Exception("LLM failed")),
    ):
        result = await extractor(base_state)

    entities = result["extracted_entities"]
    assert isinstance(entities, ExtractedEntities)
    assert entities.primary_name == "Alice Test Person"
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_extractor_handles_no_results(base_state, sample_entities):
    base_state["raw_results"] = []

    with patch(
        "src.nodes.extractor.gemini_client.structured_completion",
        AsyncMock(return_value=sample_entities),
    ):
        result = await extractor(base_state)

    assert result["extracted_entities"] is not None
