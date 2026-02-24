"""Unit tests for the risk assessor node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.nodes.risk_assessor import RiskAssessmentOutput, _calculate_risk_level, risk_assessor
from src.models.report import FlagType, RiskFlag, RiskLevel


def _make_flag(severity: str, flag_type: str = "TEMPORAL_GAP") -> RiskFlag:
    return RiskFlag(
        flag_id=f"flag_{severity}",
        flag_type=FlagType(flag_type),
        severity=RiskLevel(severity),
        description=f"Test {severity} flag",
        evidence=["test evidence"],
        confidence=0.7,
        recommended_action="Investigate",
    )


class TestCalculateRiskLevel:
    def test_critical_flag_gives_critical(self):
        flags = [_make_flag("CRITICAL")]
        assert _calculate_risk_level(flags, "LOW") == "CRITICAL"

    def test_three_high_flags_give_critical(self):
        flags = [_make_flag("HIGH")] * 3
        assert _calculate_risk_level(flags, "LOW") == "CRITICAL"

    def test_two_high_flags_give_high(self):
        flags = [_make_flag("HIGH")] * 2
        assert _calculate_risk_level(flags, "LOW") == "HIGH"

    def test_one_high_flag_gives_medium(self):
        flags = [_make_flag("HIGH")]
        assert _calculate_risk_level(flags, "LOW") == "MEDIUM"

    def test_three_medium_flags_give_medium(self):
        flags = [_make_flag("MEDIUM")] * 3
        assert _calculate_risk_level(flags, "LOW") == "MEDIUM"

    def test_no_flags_trusts_llm_level(self):
        assert _calculate_risk_level([], "HIGH") == "HIGH"

    def test_no_flags_low_default(self):
        assert _calculate_risk_level([], "LOW") == "LOW"

    def test_invalid_llm_level_defaults_low(self):
        assert _calculate_risk_level([], "INVALID") == "LOW"


@pytest.mark.asyncio
async def test_risk_assessor_returns_flags(base_state, sample_entities):
    base_state["extracted_entities"] = sample_entities
    base_state["confidence_scores"] = {}
    base_state["cross_check_findings"] = ["Employment gap noted"]

    mock_output = RiskAssessmentOutput(
        risk_flags=[
            {
                "flag_id": "flag_001",
                "flag_type": "TEMPORAL_GAP",
                "severity": "MEDIUM",
                "description": "18-month gap",
                "evidence": ["No employer records 2015-2016"],
                "confidence": 0.7,
                "recommended_action": "Verify",
            }
        ],
        overall_risk_level="MEDIUM",
        risk_rationale="Employment gap detected",
    )

    with patch(
        "src.nodes.risk_assessor.anthropic_client.structured_completion",
        AsyncMock(return_value=mock_output),
    ):
        result = await risk_assessor(base_state)

    assert len(result["risk_flags"]) == 1
    assert result["overall_risk_level"] == "MEDIUM"
    assert result["risk_rationale"] == "Employment gap detected"
    assert result["current_node"] == "risk_assessor"


@pytest.mark.asyncio
async def test_risk_assessor_handles_llm_failure(base_state, sample_entities):
    base_state["extracted_entities"] = sample_entities

    with patch(
        "src.nodes.risk_assessor.anthropic_client.structured_completion",
        AsyncMock(side_effect=Exception("LLM error")),
    ):
        result = await risk_assessor(base_state)

    assert result["risk_flags"] == []
    assert result["overall_risk_level"] == "LOW"
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_risk_assessor_deterministic_override(base_state, sample_entities):
    """When 3 HIGH flags are found, should override LLM's LOW to CRITICAL."""
    base_state["extracted_entities"] = sample_entities

    mock_output = RiskAssessmentOutput(
        risk_flags=[
            {
                "flag_id": f"flag_{i}",
                "flag_type": "IDENTITY_INCONSISTENCY",
                "severity": "HIGH",
                "description": f"High risk flag {i}",
                "evidence": [],
                "confidence": 0.8,
                "recommended_action": "Escalate",
            }
            for i in range(3)
        ],
        overall_risk_level="LOW",  # LLM wrong
        risk_rationale="...",
    )

    with patch(
        "src.nodes.risk_assessor.anthropic_client.structured_completion",
        AsyncMock(return_value=mock_output),
    ):
        result = await risk_assessor(base_state)

    assert result["overall_risk_level"] == "CRITICAL"
