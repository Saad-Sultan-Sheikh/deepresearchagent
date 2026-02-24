"""Unit tests for the analyzer node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.nodes.analyzer import AnalyzerOutput, analyzer


def _make_analyzer_output():
    return AnalyzerOutput(
        confidence_assessments=[
            {
                "fact_key": "primary_name",
                "fact": "Alice Test Person",
                "source_count": 3,
                "authoritative_source": True,
                "social_only": False,
                "contradicts_seed": False,
                "corroborates_seed": True,
                "cross_source_conflict": False,
                "rationale": "Confirmed by 3 sources",
            }
        ],
        cross_check_findings=["Name confirmed across all sources"],
        corroborated_facts=["Alice Test Person lives in New York"],
    )


@pytest.mark.asyncio
async def test_analyzer_returns_confidence_scores(base_state):
    mock_output = _make_analyzer_output()
    with patch(
        "src.nodes.analyzer.anthropic_client.structured_completion",
        AsyncMock(return_value=mock_output),
    ):
        result = await analyzer(base_state)

    assert "primary_name" in result["confidence_scores"]
    assert result["confidence_scores"]["primary_name"].score > 0.75
    assert result["current_node"] == "analyzer"


@pytest.mark.asyncio
async def test_analyzer_returns_findings(base_state):
    mock_output = _make_analyzer_output()
    with patch(
        "src.nodes.analyzer.anthropic_client.structured_completion",
        AsyncMock(return_value=mock_output),
    ):
        result = await analyzer(base_state)

    assert len(result["cross_check_findings"]) > 0
    assert len(result["corroborated_facts"]) > 0


@pytest.mark.asyncio
async def test_analyzer_fallback_on_llm_failure(base_state, sample_entities):
    base_state["extracted_entities"] = sample_entities
    with patch(
        "src.nodes.analyzer.anthropic_client.structured_completion",
        AsyncMock(side_effect=Exception("LLM down")),
    ):
        result = await analyzer(base_state)

    # Should still return some confidence scores from fallback
    assert isinstance(result["confidence_scores"], dict)
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_analyzer_handles_empty_assessments(base_state, sample_entities):
    base_state["extracted_entities"] = sample_entities
    mock_output = AnalyzerOutput(
        confidence_assessments=[],
        cross_check_findings=[],
        corroborated_facts=[],
    )
    with patch(
        "src.nodes.analyzer.anthropic_client.structured_completion",
        AsyncMock(return_value=mock_output),
    ):
        result = await analyzer(base_state)

    # Fallback scores from entities
    assert isinstance(result["confidence_scores"], dict)
