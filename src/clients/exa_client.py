"""Exa AI search client."""

from __future__ import annotations

import time

from exa_py import Exa

from src.config import get_settings
from src.models.search import RawResult, SearchMeta, SearchQuery
from src.utils.rate_limiter import rate_limiter


async def search(query: SearchQuery, max_results: int | None = None) -> tuple[list[RawResult], SearchMeta]:
    """Execute a single search query via Exa AI."""
    settings = get_settings()
    if max_results is None:
        max_results = settings.max_search_results_per_query

    start = time.monotonic()
    results: list[RawResult] = []
    error: str | None = None

    async def _call():
        import asyncio
        client = Exa(api_key=settings.exa_api_key)
        # Exa SDK is synchronous — run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: client.search_and_contents(
                query.text,
                num_results=max_results,
                text=True,
                highlights=True,
            ),
        )

    try:
        response = await rate_limiter.with_backoff("exa", _call)
        for i, item in enumerate(response.results):
            results.append(
                RawResult(
                    result_id=f"exa_{query.query_id}_{i}",
                    query_id=query.query_id,
                    source_api="exa",
                    url=item.url or "",
                    title=item.title or "",
                    snippet=_get_highlight(item),
                    full_content=getattr(item, "text", None),
                    published_date=item.published_date,
                    relevance_score=item.score if hasattr(item, "score") else 0.5,
                    retrieved_at=_now(),
                )
            )
    except Exception as exc:
        error = str(exc)

    latency_ms = (time.monotonic() - start) * 1000
    meta = SearchMeta(
        api="exa",
        query_id=query.query_id,
        result_count=len(results),
        latency_ms=latency_ms,
        success=error is None,
        error=error,
    )
    return results, meta


def _get_highlight(item) -> str:
    highlights = getattr(item, "highlights", None)
    if highlights:
        return " ".join(highlights[:3])
    return getattr(item, "text", "")[:500] if getattr(item, "text", None) else ""


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
