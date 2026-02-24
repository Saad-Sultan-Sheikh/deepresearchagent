"""Unit tests for the planner node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.search import SearchCategory, SearchPlan, SearchQuery
from src.nodes.planner import PlannerError, planner


def _make_plan(n: int = 12) -> SearchPlan:
    return SearchPlan(
        queries=[
            SearchQuery(
                query_id=f"q_{i:03d}",
                text=f"query {i}",
                category=SearchCategory.IDENTITY,
                priority=5,
                rationale="test",
            )
            for i in range(1, n + 1)
        ],
        strategy="Test strategy",
    )


@pytest.mark.asyncio
async def test_planner_returns_queries(base_state):
    mock_plan = _make_plan(12)
    with patch("src.nodes.planner.anthropic_client.structured_completion", AsyncMock(return_value=mock_plan)):
        result = await planner(base_state)

    assert len(result["search_queries"]) == 12
    assert result["query_strategy"] == "Test strategy"
    assert result["current_node"] == "planner"
    assert "planner" in result["node_timings"]


@pytest.mark.asyncio
async def test_planner_retries_once_on_failure(base_state):
    mock_plan = _make_plan(10)
    call_count = 0

    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("First attempt fails")
        return mock_plan

    with patch("src.nodes.planner.anthropic_client.structured_completion", flaky):
        result = await planner(base_state)

    assert call_count == 2
    assert len(result["search_queries"]) == 10


@pytest.mark.asyncio
async def test_planner_raises_after_two_failures(base_state):
    async def always_fail(*args, **kwargs):
        raise ValueError("Always fails")

    with patch("src.nodes.planner.anthropic_client.structured_completion", always_fail):
        with pytest.raises(PlannerError):
            await planner(base_state)


@pytest.mark.asyncio
async def test_planner_updates_node_timings(base_state):
    base_state["node_timings"] = {"some_prior_node": 1.0}
    mock_plan = _make_plan(5)

    with patch("src.nodes.planner.anthropic_client.structured_completion", AsyncMock(return_value=mock_plan)):
        result = await planner(base_state)

    assert "some_prior_node" in result["node_timings"]
    assert "planner" in result["node_timings"]
