"""Integration tests for the searcher node — mocks all external search APIs."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.models.search import RawResult, SearchMeta
from src.nodes.searcher import searcher


def _make_mock_result(api: str, query_id: str, now: str) -> tuple[list[RawResult], SearchMeta]:
    results = [
        RawResult(
            result_id=f"{api}_{query_id}_0",
            query_id=query_id,
            source_api=api,
            url=f"https://{api}.example.com/result",
            title=f"{api.capitalize()} result",
            snippet="Test result snippet",
            relevance_score=0.8,
            retrieved_at=now,
        )
    ]
    meta = SearchMeta(
        api=api,
        query_id=query_id,
        result_count=1,
        latency_ms=50.0,
        success=True,
    )
    return results, meta


@pytest.mark.asyncio
async def test_searcher_collects_from_all_apis(base_state, now_iso):
    mock_results = {
        "tavily": lambda q: _make_mock_result("tavily", q.query_id, now_iso),
        "brave": lambda q: _make_mock_result("brave", q.query_id, now_iso),
        "exa": lambda q: _make_mock_result("exa", q.query_id, now_iso),
    }

    async def mock_tavily(q, **kw):
        return mock_results["tavily"](q)

    async def mock_brave(q, **kw):
        return mock_results["brave"](q)

    async def mock_exa(q, **kw):
        return mock_results["exa"](q)

    base_state["raw_results"] = []  # start clean so accumulation doesn't add prior results
    with patch("src.nodes.searcher.tavily_client.search", mock_tavily), \
         patch("src.nodes.searcher.brave_client.search", mock_brave), \
         patch("src.nodes.searcher.exa_client.search", mock_exa):
        result = await searcher(base_state)

    # 2 queries × 3 APIs × 1 result each = 6 total
    assert len(result["raw_results"]) == 6
    assert result["current_node"] == "searcher"


@pytest.mark.asyncio
async def test_searcher_continues_on_single_api_failure(base_state, now_iso):
    async def mock_success(q, **kw):
        return _make_mock_result("tavily", q.query_id, now_iso)

    async def mock_fail(q, **kw):
        raise Exception("API unavailable")

    with patch("src.nodes.searcher.tavily_client.search", mock_success), \
         patch("src.nodes.searcher.brave_client.search", mock_fail), \
         patch("src.nodes.searcher.exa_client.search", mock_success):
        result = await searcher(base_state)

    # Should still have results from tavily and exa
    assert len(result["raw_results"]) > 0
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_searcher_metadata_recorded(base_state, now_iso):
    async def mock_any(q, **kw):
        return _make_mock_result("tavily", q.query_id, now_iso)

    with patch("src.nodes.searcher.tavily_client.search", mock_any), \
         patch("src.nodes.searcher.brave_client.search", mock_any), \
         patch("src.nodes.searcher.exa_client.search", mock_any):
        result = await searcher(base_state)

    assert len(result["search_metadata"]) > 0
