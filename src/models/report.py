"""Report models — confidence scores, risk flags, final report data."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class FlagType(str, Enum):
    IDENTITY_INCONSISTENCY = "IDENTITY_INCONSISTENCY"
    FINANCIAL_OPACITY = "FINANCIAL_OPACITY"
    JURISDICTION_MISMATCH = "JURISDICTION_MISMATCH"
    TEMPORAL_GAP = "TEMPORAL_GAP"
    ALIAS_PROLIFERATION = "ALIAS_PROLIFERATION"
    SANCTIONS_PROXIMITY = "SANCTIONS_PROXIMITY"


class ConfidenceScore(BaseModel):
    fact: str
    score: float = Field(..., ge=0.05, le=0.95)
    source_count: int = Field(default=1)
    authoritative_source: bool = Field(default=False)
    social_only: bool = Field(default=False)
    contradicts_seed: bool = Field(default=False)
    corroborates_seed: bool = Field(default=False)
    cross_source_conflict: bool = Field(default=False)
    rationale: str = Field(default="")


class RiskFlag(BaseModel):
    flag_id: str
    flag_type: FlagType
    severity: RiskLevel
    description: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_action: str = Field(default="")


class ReportData(BaseModel):
    """Complete structured data for the final report."""

    persona_id: str
    run_id: str
    generated_at: str
    langsmith_trace_url: Optional[str] = None

    # Summary
    full_name: str
    overall_risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_rationale: str = ""
    executive_summary: str = ""

    # Data
    confidence_scores: dict[str, ConfidenceScore] = Field(default_factory=dict)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    corroborated_facts: list[str] = Field(default_factory=list)
    cross_check_findings: list[str] = Field(default_factory=list)

    # Graph stats
    graph_node_count: int = 0
    graph_relationship_count: int = 0

    # Search stats
    total_sources: int = 0
    search_query_count: int = 0
    search_round_1_count: int = 0
    search_round_2_count: int = 0
    refinement_rationale: str = ""

    # Node timings
    node_timings: dict[str, float] = Field(default_factory=dict)

    # Errors encountered during run
    errors: list[str] = Field(default_factory=list)
