"""Node 1 — Planner: Claude generates search queries from the persona seed."""

from __future__ import annotations

import asyncio
import logging
import time

from src.agent.state import ResearchState
from src.clients import anthropic_client
from src.models.search import SearchPlan, SearchQuery
from src.utils.prompts import PLANNER_SYSTEM, PLANNER_USER

log = logging.getLogger(__name__)

NODE_NAME = "planner"


class PlannerError(Exception):
    pass


async def planner(state: ResearchState) -> dict:
    """Generate search queries for the given persona using Claude."""
    t0 = time.monotonic()
    persona = state["persona_input"]
    run_id = state["run_id"]

    log.info("[%s] Planning searches for persona: %s", run_id, persona.full_name)

    user_msg = PLANNER_USER.format(
        full_name=persona.full_name,
        aliases=", ".join(persona.aliases) or "none",
        date_of_birth=persona.date_of_birth or "unknown",
        nationalities=", ".join(persona.nationalities) or "unknown",
        known_locations=", ".join(persona.known_locations) or "unknown",
        employers=", ".join(persona.employers) or "unknown",
        education=", ".join(persona.education) or "unknown",
        social_profiles=", ".join(persona.social_profiles) or "none",
        notes=persona.notes or "none",
    )

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    plan: SearchPlan | None = None

    # Retry up to 4 times with backoff (handles 529 overloaded + transient errors)
    for attempt in range(4):
        try:
            plan = await anthropic_client.structured_completion(
                prompt_messages=messages,
                output_schema=SearchPlan,
            )
            break
        except Exception as exc:
            log.warning("[%s] Planner attempt %d failed: %s", run_id, attempt + 1, exc)
            if attempt == 3:
                raise PlannerError(f"Planner failed after 4 attempts: {exc}") from exc
            wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
            log.info("[%s] Retrying planner in %ds...", run_id, wait)
            await asyncio.sleep(wait)

    assert plan is not None

    duration = time.monotonic() - t0
    log.info(
        "[%s] Planner produced %d queries in %.2fs",
        run_id, len(plan.queries), duration,
    )

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "search_queries": plan.queries,
        "query_strategy": plan.strategy,
        "current_node": NODE_NAME,
        "node_timings": timings,
    }
