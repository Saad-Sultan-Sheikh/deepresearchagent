"""Brave Search API client (via httpx)."""

from __future__ import annotations

import time

import httpx

from src.config import get_settings
from src.models.search import RawResult, SearchMeta, SearchQuery
from src.utils.rate_limiter import rate_limiter

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


async def search(query: SearchQuery, max_results: int | None = None) -> tuple[list[RawResult], SearchMeta]:
    """Execute a single search query via Brave Search API."""
    settings = get_settings()
    if max_results is None:
        max_results = settings.max_search_results_per_query

    start = time.monotonic()
    results: list[RawResult] = []
    error: str | None = None

    async def _call():
        async with httpx.AsyncClient(timeout=settings.search_timeout_seconds) as client:
            response = await client.get(
                BRAVE_API_URL,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_api_key,
                },
                params={"q": query.text, "count": max_results},
            )
            response.raise_for_status()
            return response.json()

    try:
        data = await rate_limiter.with_backoff("brave", _call)
        web_results = data.get("web", {}).get("results", [])
        for i, item in enumerate(web_results):
            results.append(
                RawResult(
                    result_id=f"brave_{query.query_id}_{i}",
                    query_id=query.query_id,
                    source_api="brave",
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                    published_date=item.get("page_age"),
                    relevance_score=0.5,  # Brave doesn't return explicit scores
                    retrieved_at=_now(),
                )
            )
    except Exception as exc:
        error = str(exc)

    latency_ms = (time.monotonic() - start) * 1000
    meta = SearchMeta(
        api="brave",
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
