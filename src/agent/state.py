"""ResearchState TypedDict — the shared state object flowing through the LangGraph pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

from src.models.entities import ExtractedEntities
from src.models.persona import PersonaInput
from src.models.report import ConfidenceScore, ReportData, RiskFlag
from src.models.search import RawResult, SearchMeta, SearchQuery


class ResearchState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    persona_id: str
    persona_input: PersonaInput

    # ── Planner output ────────────────────────────────────────────────────────
    search_queries: list[SearchQuery]
    query_strategy: str

    # ── Search routing control ────────────────────────────────────────────────
    search_round: int
    search_round_1_count: int
    refinement_rationale: str

    # ── Searcher output ───────────────────────────────────────────────────────
    raw_results: list[RawResult]
    search_metadata: dict[str, SearchMeta]

    # ── Extractor output ──────────────────────────────────────────────────────
    extracted_entities: ExtractedEntities

    # ── Graph Writer output ───────────────────────────────────────────────────
    graph_node_ids: list[str]
    graph_relationship_ids: list[str]
    graph_write_errors: list[str]

    # ── Analyzer output ───────────────────────────────────────────────────────
    confidence_scores: dict[str, ConfidenceScore]
    cross_check_findings: list[str]
    corroborated_facts: list[str]

    # ── Risk Assessor output ──────────────────────────────────────────────────
    risk_flags: list[RiskFlag]
    overall_risk_level: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    risk_rationale: str

    # ── Reporter output ───────────────────────────────────────────────────────
    report_markdown_path: str
    report_json_path: str
    report_data: ReportData

    # ── Execution metadata ────────────────────────────────────────────────────
    run_id: str
    # errors uses operator.add so each node can append without overwriting
    errors: Annotated[list[str], operator.add]
    current_node: str
    node_timings: dict[str, float]
    langsmith_trace_url: Optional[str]
