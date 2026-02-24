"""Node 3 — Extractor: Gemini 1.5 Pro extracts structured entities from raw results."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

from src.agent.state import ResearchState
from src.clients import gemini_client
from src.models.entities import ExtractedEntities
from src.utils.prompts import EXTRACTOR_SYSTEM, EXTRACTOR_USER

log = logging.getLogger(__name__)

NODE_NAME = "extractor"

_MAX_SNIPPET_CHARS = 300
_MAX_RESULTS_TO_SEND = 50  # Limit to avoid token overflows (Gemini 1M ctx)


async def extractor(state: ResearchState) -> dict:
    """Extract structured entities from raw search results using Gemini."""
    t0 = time.monotonic()
    persona = state["persona_input"]
    raw_results = state["raw_results"]
    run_id = state["run_id"]
    now = datetime.now(timezone.utc).isoformat()

    log.info("[%s] Extracting entities from %d raw results", run_id, len(raw_results))

    # Build compact results text for the prompt
    top_results = sorted(raw_results, key=lambda r: r.relevance_score, reverse=True)[:_MAX_RESULTS_TO_SEND]
    results_text = _format_results(top_results)

    user_msg = EXTRACTOR_USER.format(
        persona_json=persona.model_dump_json(indent=2),
        result_count=len(top_results),
        source_count=len({r.source_api for r in top_results}),
        results_text=results_text,
    )

    messages = [
        {"role": "system", "content": EXTRACTOR_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    entities: ExtractedEntities | None = None
    errors: list[str] = []

    try:
        entities = await gemini_client.structured_completion(
            prompt_messages=messages,
            output_schema=ExtractedEntities,
        )
        if entities is None:
            raise ValueError("Gemini returned None for ExtractedEntities")
        # Backfill run metadata
        entities.persona_id = persona.persona_id
        entities.run_id = run_id
        entities.extracted_at = now
        entities.source_count = len({r.url for r in raw_results})
        # Backfill per-entity timestamps that the LLM doesn't provide
        for ent in entities.entities:
            if not ent.extracted_at:
                ent.extracted_at = now
        for rel in entities.relationships:
            if not rel.created_at:
                rel.created_at = now
    except (ValidationError, Exception) as exc:
        err_msg = f"Extractor failed: {exc}"
        log.error("[%s] %s", run_id, err_msg)
        errors.append(err_msg)
        # Return empty entities — pipeline continues
        entities = ExtractedEntities(
            persona_id=persona.persona_id,
            run_id=run_id,
            extracted_at=now,
            primary_name=persona.full_name,
        )

    duration = time.monotonic() - t0
    log.info("[%s] Extractor done in %.2fs", run_id, duration)

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "extracted_entities": entities,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": errors,
    }


def _format_results(results) -> str:
    lines = []
    for r in results:
        snippet = (r.snippet or "")[:_MAX_SNIPPET_CHARS]
        lines.append(
            f"[{r.source_api.upper()}] {r.title}\n"
            f"URL: {r.url}\n"
            f"Snippet: {snippet}\n"
        )
    return "\n---\n".join(lines)
