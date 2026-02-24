"""Node 2b — Refiner: Claude Sonnet 4.6 generates follow-up queries from extraction gaps."""

from __future__ import annotations

import logging
import time
from collections import Counter

from src.agent.state import ResearchState
from src.clients import anthropic_client
from src.models.search import SearchPlan, SearchQuery
from src.utils.prompts import REFINER_SYSTEM, REFINER_USER

log = logging.getLogger(__name__)

NODE_NAME = "refiner"


async def refiner(state: ResearchState) -> dict:
    """Generate targeted follow-up queries based on extraction data gaps."""
    t0 = time.monotonic()
    persona = state["persona_input"]
    run_id = state["run_id"]
    entities = state.get("extracted_entities")
    current_queries = state.get("search_queries") or []

    data_gaps = entities.data_gaps if entities else []
    round_1_count = len(current_queries)
    found_summary = _build_found_summary(entities)

    log.info(
        "[%s] Refiner: %d data gaps identified, generating follow-up queries",
        run_id,
        len(data_gaps),
    )

    user_msg = REFINER_USER.format(
        full_name=persona.full_name,
        persona_id=persona.persona_id,
        data_gaps="\n".join(f"- {g}" for g in data_gaps) or "None identified",
        found_summary=found_summary,
        round_1_query_count=round_1_count,
        round_1_queries="\n".join(
            f"- [{q.category.value}] {q.text}" for q in current_queries
        ),
    )

    errors: list[str] = []
    plan = None
    try:
        plan = await anthropic_client.structured_completion(
            prompt_messages=[
                {"role": "system", "content": REFINER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            output_schema=SearchPlan,
        )
    except Exception as exc:
        errors.append(f"Refiner LLM failed: {exc}")
        log.warning("[%s] Refiner LLM error: %s", run_id, exc)

    follow_up: list[SearchQuery] = []
    rationale = "Refinement skipped."
    if plan and plan.queries:
        for i, q in enumerate(plan.queries[:8]):
            follow_up.append(
                SearchQuery(
                    query_id=f"r2_{i + 1:03d}",
                    text=q.text,
                    category=q.category,
                    priority=q.priority,
                    rationale=q.rationale,
                )
            )
        rationale = plan.strategy
        log.info("[%s] Refiner generated %d follow-up queries", run_id, len(follow_up))

    duration = time.monotonic() - t0
    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "search_queries": follow_up,
        "search_round": 2,
        "search_round_1_count": round_1_count,
        "refinement_rationale": rationale,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": errors,
    }


def _build_found_summary(entities) -> str:
    """Build a brief human-readable summary of what was extracted so far."""
    if not entities:
        return "No entities extracted yet."
    lines = []
    if entities.primary_name:
        lines.append(f"Name: {entities.primary_name}")
    if entities.current_employers:
        lines.append(f"Employers: {', '.join(entities.current_employers[:3])}")
    if entities.current_locations:
        lines.append(f"Locations: {', '.join(entities.current_locations[:3])}")
    if entities.entities:
        type_counts = dict(Counter(e.label for e in entities.entities))
        lines.append(f"Entity types: {type_counts}")
    return "\n".join(lines) or "Minimal data extracted."
