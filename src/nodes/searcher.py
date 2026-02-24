"""Node 2 — Searcher: parallel Tavily + Brave + Exa per query."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.agent.state import ResearchState
from src.clients import brave_client, exa_client, tavily_client
from src.models.search import RawResult, SearchMeta, SearchQuery
from src.utils.logging import ExecutionLogger

log = logging.getLogger(__name__)

NODE_NAME = "searcher"

# If ALL 3 APIs fail for EVERY query, abort
_ABORT_THRESHOLD = 0.0  # fraction of successful results needed


async def searcher(state: ResearchState) -> dict:
    """Execute all search queries across Tavily, Brave, and Exa in parallel."""
    t0 = time.monotonic()
    queries: list[SearchQuery] = state["search_queries"]
    run_id = state["run_id"]
    exec_log = ExecutionLogger(run_id)

    search_round = state.get("search_round", 1)
    log.info("[%s] Running %d queries across 3 search APIs (round %d)", run_id, len(queries), search_round)

    existing_results: list[RawResult] = list(state.get("raw_results") or [])
    all_results: list[RawResult] = []
    all_meta: dict[str, SearchMeta] = {}
    errors: list[str] = []

    # Process queries with bounded concurrency
    sem = asyncio.Semaphore(5)

    async def search_query(q: SearchQuery) -> None:
        async with sem:
            tasks = [
                tavily_client.search(q),
                brave_client.search(q),
                exa_client.search(q),
            ]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results_list:
                if isinstance(res, Exception):
                    errors.append(f"Search error for query {q.query_id}: {res}")
                    continue
                results, meta = res
                all_results.extend(results)
                meta_key = f"{meta.api}_{meta.query_id}"
                all_meta[meta_key] = meta
                exec_log.search_event(
                    api=meta.api,
                    query_id=meta.query_id,
                    result_count=meta.result_count,
                    latency_ms=meta.latency_ms,
                    success=meta.success,
                )

    await asyncio.gather(*[search_query(q) for q in queries])

    if not all_results and errors:
        # All searches failed
        errors.append("ABORT: All search APIs failed for all queries")
        log.error("[%s] All searches failed — %d errors", run_id, len(errors))

    duration = time.monotonic() - t0
    log.info(
        "[%s] Searcher collected %d results in %.2fs (%d errors)",
        run_id, len(all_results), duration, len(errors),
    )

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "raw_results": existing_results + all_results,
        "search_metadata": all_meta,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": errors,
    }
