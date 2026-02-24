"""Shared fixtures for unit and integration tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.entities import Entity, ExtractedEntities, Relationship
from src.models.persona import PersonaInput
from src.models.report import ConfidenceScore, RiskFlag, RiskLevel, FlagType
from src.models.search import RawResult, SearchMeta, SearchQuery, SearchCategory, SearchPlan

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def now_iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def sample_persona():
    return PersonaInput(
        persona_id="test_001",
        full_name="Alice Test Person",
        aliases=["A. Test"],
        date_of_birth="1990-01-01",
        nationalities=["American"],
        known_locations=["New York, NY"],
        employers=["TestCorp Inc"],
        education=["MIT - BSc CS 2012"],
        social_profiles=["https://linkedin.com/in/alicetest"],
        emails=["alice@testcorp.com"],
        phones=["+1-555-0100"],
        notes="Fictional test persona for unit testing.",
        risk_seed="LOW",
    )


@pytest.fixture
def sample_queries():
    return [
        SearchQuery(
            query_id="q_001",
            text="Alice Test Person New York",
            category=SearchCategory.IDENTITY,
            priority=9,
            rationale="Primary identity search",
        ),
        SearchQuery(
            query_id="q_002",
            text="Alice Test Person TestCorp Inc",
            category=SearchCategory.EMPLOYMENT,
            priority=8,
            rationale="Employment verification",
        ),
    ]


@pytest.fixture
def sample_raw_results(now_iso):
    return [
        RawResult(
            result_id="tavily_q_001_0",
            query_id="q_001",
            source_api="tavily",
            url="https://linkedin.com/in/alicetest",
            title="Alice Test Person | LinkedIn",
            snippet="Software engineer at TestCorp Inc, based in New York.",
            relevance_score=0.95,
            retrieved_at=now_iso,
        ),
        RawResult(
            result_id="brave_q_001_0",
            query_id="q_001",
            source_api="brave",
            url="https://github.com/alicetest",
            title="alicetest (Alice Test Person) · GitHub",
            snippet="Open source contributor. Based in NYC.",
            relevance_score=0.80,
            retrieved_at=now_iso,
        ),
    ]


@pytest.fixture
def sample_entities(now_iso):
    return ExtractedEntities(
        persona_id="test_001",
        run_id="abc12345",
        extracted_at=now_iso,
        primary_name="Alice Test Person",
        name_variants=["Alice Test Person"],
        aliases=["A. Test"],
        date_of_birth="1990-01-01",
        nationalities=["American"],
        current_locations=["New York, NY"],
        current_employers=["TestCorp Inc"],
        education_history=[{"institution": "MIT", "degree": "BSc CS", "year": "2012"}],
        emails=["alice@testcorp.com"],
        phones=["+1-555-0100"],
        social_handles=["https://linkedin.com/in/alicetest"],
        source_count=2,
        entities=[
            Entity(
                entity_id="email_001",
                label="Email",
                value="alice@testcorp.com",
                confidence=0.9,
                source_urls=["https://linkedin.com/in/alicetest"],
                extracted_at=now_iso,
            )
        ],
        relationships=[],
    )


@pytest.fixture
def sample_confidence_scores():
    return {
        "primary_name": ConfidenceScore(
            fact="Alice Test Person",
            score=0.85,
            source_count=3,
            authoritative_source=True,
            corroborates_seed=True,
            rationale="base=0.75; authoritative +0.15; corroborates-seed +0.10",
        )
    }


@pytest.fixture
def sample_risk_flag():
    return RiskFlag(
        flag_id="flag_001",
        flag_type=FlagType.TEMPORAL_GAP,
        severity=RiskLevel.MEDIUM,
        description="18-month employment gap detected",
        evidence=["No employer records 2015-2016"],
        confidence=0.7,
        recommended_action="Request explanation of employment gap",
    )


@pytest.fixture
def base_state(sample_persona, sample_queries, sample_raw_results, sample_entities):
    """Minimal valid ResearchState for node testing."""
    return {
        "persona_id": "test_001",
        "persona_input": sample_persona,
        "search_queries": sample_queries,
        "query_strategy": "Comprehensive identity verification",
        "raw_results": sample_raw_results,
        "search_metadata": {},
        "extracted_entities": sample_entities,
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
        "run_id": "abc12345",
        "errors": [],
        "current_node": "",
        "node_timings": {},
        "langsmith_trace_url": None,
    }
