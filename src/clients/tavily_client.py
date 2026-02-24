"""Tavily search API client."""

from __future__ import annotations

import time
import uuid

from tavily import AsyncTavilyClient

from src.config import get_settings
from src.models.search import RawResult, SearchMeta, SearchQuery
from src.utils.rate_limiter import rate_limiter


async def search(query: SearchQuery, max_results: int | None = None) -> tuple[list[RawResult], SearchMeta]:
    """Execute a single search query via Tavily."""
    settings = get_settings()
    if max_results is None:
        max_results = settings.max_search_results_per_query

    start = time.monotonic()
    results: list[RawResult] = []
    error: str | None = None

    async def _call():
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        return await client.search(
            query=query.text,
            max_results=max_results,
            include_raw_content=True,
            search_depth="advanced",
        )

    try:
        response = await rate_limiter.with_backoff("tavily", _call)
        for i, item in enumerate(response.get("results", [])):
            results.append(
                RawResult(
                    result_id=f"tavily_{query.query_id}_{i}",
                    query_id=query.query_id,
                    source_api="tavily",
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    full_content=item.get("raw_content"),
                    published_date=item.get("published_date"),
                    relevance_score=item.get("score", 0.0),
                    retrieved_at=_now(),
                )
            )
    except Exception as exc:
        error = str(exc)

    latency_ms = (time.monotonic() - start) * 1000
    meta = SearchMeta(
        api="tavily",
        query_id=query.query_id,
        result_count=len(results),
        latency_ms=latency_ms,
        success=error is None,
        error=error,
    )
    return results, meta


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
