"""Node 7 — Reporter: Jinja2 Markdown + JSON output, final JSONL summary."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import BaseLoader, Environment

from src.agent.state import ResearchState
from src.config import get_settings
from src.models.report import ReportData, RiskLevel
from src.utils.logging import ExecutionLogger
from src.utils.prompts import REPORT_TEMPLATE

log = logging.getLogger(__name__)

NODE_NAME = "reporter"


async def reporter(state: ResearchState) -> dict:
    """Generate Markdown + JSON reports and write final JSONL log entry."""
    t0 = time.monotonic()
    settings = get_settings()
    persona_id = state["persona_id"]
    run_id = state["run_id"]
    now = datetime.now(timezone.utc).isoformat()

    log.info("[%s] Generating reports for persona %s", run_id, persona_id)

    # Build ReportData
    entities = state.get("extracted_entities")
    risk_flags = state.get("risk_flags") or []
    confidence_scores = state.get("confidence_scores") or {}

    # Compute per-round query counts.
    # After round 2, state["search_queries"] only holds the round-2 queries
    # (refiner replaced the list), so round_2_count = len(search_queries).
    round_1_count = state.get("search_round_1_count", 0)
    current_queries = state.get("search_queries") or []
    if round_1_count > 0:
        actual_round_1 = round_1_count
        actual_round_2 = len(current_queries)
    else:
        actual_round_1 = len(current_queries)
        actual_round_2 = 0

    report_data = ReportData(
        persona_id=persona_id,
        run_id=run_id,
        generated_at=now,
        langsmith_trace_url=state.get("langsmith_trace_url"),
        full_name=state["persona_input"].full_name,
        overall_risk_level=RiskLevel(state.get("overall_risk_level") or "UNKNOWN"),
        risk_rationale=state.get("risk_rationale") or "",
        executive_summary=_build_executive_summary(state),
        confidence_scores=confidence_scores,
        risk_flags=risk_flags,
        corroborated_facts=state.get("corroborated_facts") or [],
        cross_check_findings=state.get("cross_check_findings") or [],
        graph_node_count=len(state.get("graph_node_ids") or []),
        graph_relationship_count=len(state.get("graph_relationship_ids") or []),
        total_sources=len(state.get("raw_results") or []),
        search_query_count=actual_round_1 + actual_round_2,
        search_round_1_count=actual_round_1,
        search_round_2_count=actual_round_2,
        refinement_rationale=state.get("refinement_rationale") or "",
        node_timings=state.get("node_timings") or {},
        errors=state.get("errors") or [],
    )

    # Ensure output directory
    report_dir = settings.reports_dir / persona_id
    report_dir.mkdir(parents=True, exist_ok=True)

    # Render Markdown
    md_path = report_dir / "report.md"
    md_content = _render_markdown(report_data)
    md_path.write_text(md_content, encoding="utf-8")

    # Write JSON
    json_path = report_dir / "data.json"
    json_path.write_text(
        report_data.model_dump_json(indent=2),
        encoding="utf-8",
    )

    duration = time.monotonic() - t0
    log.info("[%s] Reports written to %s in %.2fs", run_id, report_dir, duration)

    # Final JSONL summary
    exec_log = ExecutionLogger(run_id)
    exec_log.summary(
        persona_id=persona_id,
        overall_risk=report_data.overall_risk_level.value
        if hasattr(report_data.overall_risk_level, "value")
        else str(report_data.overall_risk_level),
        flag_count=len(risk_flags),
        report_path=str(md_path),
        langsmith_url=state.get("langsmith_trace_url"),
    )

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "report_markdown_path": str(md_path),
        "report_json_path": str(json_path),
        "report_data": report_data,
        "current_node": NODE_NAME,
        "node_timings": timings,
    }


def _render_markdown(report: ReportData) -> str:
    env = Environment(loader=BaseLoader())
    template = env.from_string(REPORT_TEMPLATE)
    return template.render(report=report)


def _build_executive_summary(state: ResearchState) -> str:
    persona = state["persona_input"]
    risk_level_raw = state.get("overall_risk_level") or "UNKNOWN"
    risk_level = risk_level_raw.value if hasattr(risk_level_raw, "value") else str(risk_level_raw)
    flag_count = len(state.get("risk_flags") or [])
    source_count = len(state.get("raw_results") or [])
    corroborated = len(state.get("corroborated_facts") or [])
    search_round = state.get("search_round", 1)

    search_desc = (
        f"Conducted a 2-round adaptive search strategy: initial planner queries followed by "
        f"targeted gap-filling queries. Analysed {source_count} sources across Tavily, Brave, and Exa search APIs."
        if search_round >= 2
        else f"Analysed {source_count} sources across Tavily, Brave, and Exa search APIs."
    )

    return (
        f"Research investigation completed for **{persona.full_name}** ({persona.persona_id}). "
        f"{search_desc} "
        f"{corroborated} facts were corroborated across multiple independent sources. "
        f"Risk assessment determined **{risk_level}** overall risk with {flag_count} flag(s) identified."
    )
