"""Integration test for the full 7-node LangGraph pipeline (all external calls mocked)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.entities import Entity, ExtractedEntities
from src.models.search import SearchPlan, SearchQuery, SearchCategory, RawResult, SearchMeta
from src.nodes.analyzer import AnalyzerOutput
from src.nodes.risk_assessor import RiskAssessmentOutput


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_full_pipeline_runs_all_nodes(sample_persona, tmp_path):
    """Full pipeline smoke test — all LLMs and APIs mocked."""
    from src.agent.graph import build_graph
    from src.config import get_settings

    # Override output directories to temp path
    with patch("src.config.get_settings") as mock_settings:
        settings = MagicMock()
        settings.reports_dir = tmp_path / "reports"
        settings.logs_dir = tmp_path / "logs"
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        settings.max_search_results_per_query = 5
        settings.search_timeout_seconds = 10
        settings.llm_temperature = 0.1
        settings.planner_model = "gpt-4o"
        settings.analyzer_model = "claude-sonnet-4-6"
        settings.extractor_model = "gemini-1.5-pro"
        mock_settings.return_value = settings

        now = _now()
        plan = SearchPlan(
            queries=[
                SearchQuery(
                    query_id=f"q_{i:03d}",
                    text=f"test query {i}",
                    category=SearchCategory.IDENTITY,
                    priority=5,
                    rationale="test",
                )
                for i in range(5)
            ],
            strategy="Test strategy",
        )

        mock_result = RawResult(
            result_id="r001",
            query_id="q_001",
            source_api="tavily",
            url="https://example.com",
            title="Test result",
            snippet="Alice Test Person is a software engineer in New York.",
            relevance_score=0.9,
            retrieved_at=now,
        )

        mock_entities = ExtractedEntities(
            persona_id="test_001",
            run_id="testrun1",
            extracted_at=now,
            primary_name="Alice Test Person",
            current_employers=["TestCorp Inc"],
            emails=["alice@testcorp.com"],
            data_gaps=[],
            entities=[
                Entity(label="Person", value=f"Person {i}", confidence=0.8)
                for i in range(5)
            ],
        )

        mock_analyzer_output = AnalyzerOutput(
            confidence_assessments=[
                {
                    "fact_key": "primary_name",
                    "fact": "Alice Test Person",
                    "source_count": 2,
                    "authoritative_source": False,
                    "social_only": False,
                    "contradicts_seed": False,
                    "corroborates_seed": True,
                    "cross_source_conflict": False,
                    "rationale": "Confirmed",
                }
            ],
            cross_check_findings=["Name verified"],
            corroborated_facts=["Lives in New York"],
        )

        mock_risk_output = RiskAssessmentOutput(
            risk_flags=[],
            overall_risk_level="LOW",
            risk_rationale="No significant risks found",
        )

        # All Claude nodes share the same anthropic_client module object, so a single
        # patch with side_effect returns the right value per call (in pipeline order:
        # planner → analyzer → risk_assessor). Refiner is skipped because mock_entities
        # has 5 entities and no data_gaps.
        mock_claude = AsyncMock(side_effect=[plan, mock_analyzer_output, mock_risk_output])

        with patch("src.clients.anthropic_client.structured_completion", mock_claude), \
             patch("src.nodes.searcher.tavily_client.search", AsyncMock(return_value=([mock_result], SearchMeta(api="tavily", query_id="q_001", result_count=1, latency_ms=50, success=True)))), \
             patch("src.nodes.searcher.brave_client.search", AsyncMock(return_value=([], SearchMeta(api="brave", query_id="q_001", result_count=0, latency_ms=50, success=True)))), \
             patch("src.nodes.searcher.exa_client.search", AsyncMock(return_value=([], SearchMeta(api="exa", query_id="q_001", result_count=0, latency_ms=50, success=True)))), \
             patch("src.nodes.extractor.gemini_client.structured_completion", AsyncMock(return_value=mock_entities)), \
             patch("src.nodes.graph_writer.neo4j_client.get_driver", AsyncMock()), \
             patch("src.nodes.graph_writer.neo4j_client.run_query", AsyncMock(return_value=[])):

            graph = build_graph()
            initial_state = {
                "persona_id": "test_001",
                "persona_input": sample_persona,
                "search_queries": [],
                "query_strategy": "",
                "raw_results": [],
                "search_metadata": {},
                "extracted_entities": None,
                "graph_node_ids": [],
                "graph_relationship_ids": [],
                "graph_write_errors": [],
                "confidence_scores": {},
                "cross_check_findings": [],
                "corroborated_facts": [],
                "risk_flags": [],
                "overall_risk_level": "UNKNOWN",
                "risk_rationale": "",
                "report_markdown_path": "",
                "report_json_path": "",
                "report_data": None,
                "search_round": 1,
                "search_round_1_count": 0,
                "refinement_rationale": "",
                "run_id": "testrun1",
                "errors": [],
                "current_node": "",
                "node_timings": {},
                "langsmith_trace_url": None,
            }

            final_chunks = []
            async for chunk in graph.astream(initial_state):
                final_chunks.append(chunk)

        # Verify all 7 nodes ran
        node_names = [list(c.keys())[0] for c in final_chunks]
        assert "planner" in node_names
        assert "searcher" in node_names
        assert "extractor" in node_names
        assert "graph_writer" in node_names
        assert "analyzer" in node_names
        assert "risk_assessor" in node_names
        assert "reporter" in node_names
