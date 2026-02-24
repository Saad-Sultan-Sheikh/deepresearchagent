"""Node 5 — Analyzer: Claude cross-checks sources and assigns confidence scores."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.agent.state import ResearchState
from src.clients import anthropic_client
from src.models.report import ConfidenceScore
from src.utils.confidence import compute_confidence
from src.utils.prompts import ANALYZER_SYSTEM, ANALYZER_USER

log = logging.getLogger(__name__)

NODE_NAME = "analyzer"

_MAX_SNIPPETS = 40


class AnalyzerOutput(BaseModel):
    """Structured output from the Claude analyzer."""
    confidence_assessments: list[dict[str, Any]] = Field(default_factory=list)
    cross_check_findings: list[str] = Field(default_factory=list)
    corroborated_facts: list[str] = Field(default_factory=list)


async def analyzer(state: ResearchState) -> dict:
    """Cross-check entities against sources and produce confidence scores."""
    t0 = time.monotonic()
    entities = state["extracted_entities"]
    persona = state["persona_input"]
    raw_results = state["raw_results"]
    run_id = state["run_id"]

    log.info("[%s] Analyzing %d entities", run_id, len(entities.entities))

    # Prepare snippets
    top_results = sorted(raw_results, key=lambda r: r.relevance_score, reverse=True)[:_MAX_SNIPPETS]
    snippets_text = "\n---\n".join(
        f"[{r.source_api.upper()}] {r.title}\n{r.snippet[:250]}"
        for r in top_results
    )

    user_msg = ANALYZER_USER.format(
        persona_json=persona.model_dump_json(indent=2),
        entities_json=entities.model_dump_json(indent=2),
        snippet_count=len(top_results),
        snippets_text=snippets_text,
    )

    messages = [
        {"role": "system", "content": ANALYZER_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    errors: list[str] = []
    output: AnalyzerOutput | None = None

    try:
        output = await anthropic_client.structured_completion(
            prompt_messages=messages,
            output_schema=AnalyzerOutput,
        )
    except Exception as exc:
        err_msg = f"Analyzer LLM failed: {exc}"
        log.error("[%s] %s", run_id, err_msg)
        errors.append(err_msg)
        output = AnalyzerOutput()

    # Convert LLM assessments to ConfidenceScore objects
    confidence_scores: dict[str, ConfidenceScore] = {}
    for assessment in (output.confidence_assessments or []):
        fact_key = assessment.get("fact_key", assessment.get("fact", "unknown"))
        try:
            cs = compute_confidence(
                fact=assessment.get("fact", fact_key),
                source_count=int(assessment.get("source_count", 1)),
                authoritative_source=bool(assessment.get("authoritative_source", False)),
                social_only=bool(assessment.get("social_only", False)),
                contradicts_seed=bool(assessment.get("contradicts_seed", False)),
                corroborates_seed=bool(assessment.get("corroborates_seed", False)),
                cross_source_conflict=bool(assessment.get("cross_source_conflict", False)),
                rationale=assessment.get("rationale", ""),
            )
            confidence_scores[str(fact_key)] = cs
        except Exception as exc:
            log.warning("[%s] Failed to compute confidence for %s: %s", run_id, fact_key, exc)

    # Fallback: build basic scores from extracted entities if LLM returned nothing
    if not confidence_scores and entities.entities:
        for entity in entities.entities[:20]:
            cs = compute_confidence(
                fact=f"{entity.label}:{entity.value}",
                source_count=len(entity.source_urls) or 1,
            )
            confidence_scores[entity.entity_id] = cs

    duration = time.monotonic() - t0
    log.info("[%s] Analyzer produced %d confidence scores in %.2fs", run_id, len(confidence_scores), duration)

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "confidence_scores": confidence_scores,
        "cross_check_findings": output.cross_check_findings,
        "corroborated_facts": output.corroborated_facts,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": errors,
    }
