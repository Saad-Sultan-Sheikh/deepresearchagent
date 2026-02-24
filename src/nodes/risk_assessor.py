"""Node 6 — Risk Assessor: Claude identifies risk flags and overall risk level."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.agent.state import ResearchState
from src.clients import anthropic_client
from src.models.report import FlagType, RiskFlag, RiskLevel
from src.utils.prompts import RISK_SYSTEM, RISK_USER

log = logging.getLogger(__name__)

NODE_NAME = "risk_assessor"


class RiskAssessmentOutput(BaseModel):
    """Structured output from the Claude risk assessor."""
    risk_flags: list[dict[str, Any]] = Field(default_factory=list)
    overall_risk_level: str = Field(default="LOW")
    risk_rationale: str = Field(default="")


async def risk_assessor(state: ResearchState) -> dict:
    """Identify risk flags and determine overall risk level."""
    t0 = time.monotonic()
    entities = state["extracted_entities"]
    confidence_scores = state.get("confidence_scores") or {}
    cross_check_findings = state.get("cross_check_findings") or []
    run_id = state["run_id"]

    log.info("[%s] Running risk assessment", run_id)

    # Serialize confidence scores for prompt
    confidence_json = json.dumps(
        {k: v.model_dump() for k, v in confidence_scores.items()},
        indent=2,
        default=str,
    )[:4000]  # Truncate if huge

    user_msg = RISK_USER.format(
        entities_json=entities.model_dump_json(indent=2)[:4000],
        confidence_json=confidence_json,
        findings_text="\n".join(f"- {f}" for f in cross_check_findings[:30]),
    )

    messages = [
        {"role": "system", "content": RISK_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    errors: list[str] = []
    output: RiskAssessmentOutput | None = None

    try:
        output = await anthropic_client.structured_completion(
            prompt_messages=messages,
            output_schema=RiskAssessmentOutput,
        )
    except Exception as exc:
        err_msg = f"Risk assessor LLM failed: {exc}"
        log.error("[%s] %s", run_id, err_msg)
        errors.append(err_msg)
        output = RiskAssessmentOutput()

    # Parse flags
    risk_flags: list[RiskFlag] = []
    for i, flag_dict in enumerate(output.risk_flags or []):
        try:
            flag = RiskFlag(
                flag_id=flag_dict.get("flag_id", f"flag_{i:03d}"),
                flag_type=FlagType(flag_dict.get("flag_type", "IDENTITY_INCONSISTENCY")),
                severity=RiskLevel(flag_dict.get("severity", "MEDIUM")),
                description=flag_dict.get("description", ""),
                evidence=flag_dict.get("evidence", []),
                confidence=float(flag_dict.get("confidence", 0.5)),
                recommended_action=flag_dict.get("recommended_action", ""),
            )
            risk_flags.append(flag)
        except Exception as exc:
            log.warning("[%s] Failed to parse risk flag %d: %s", run_id, i, exc)

    # Validate / recalculate overall risk level
    overall_risk = _calculate_risk_level(risk_flags, output.overall_risk_level)

    duration = time.monotonic() - t0
    log.info(
        "[%s] Risk assessor done: %d flags, level=%s (%.2fs)",
        run_id, len(risk_flags), overall_risk, duration,
    )

    timings = dict(state.get("node_timings") or {})
    timings[NODE_NAME] = duration

    return {
        "risk_flags": risk_flags,
        "overall_risk_level": overall_risk,
        "risk_rationale": output.risk_rationale,
        "current_node": NODE_NAME,
        "node_timings": timings,
        "errors": errors,
    }


def _calculate_risk_level(flags: list[RiskFlag], llm_level: str) -> str:
    """Validate LLM risk level against deterministic rules."""
    critical_count = sum(1 for f in flags if f.severity == RiskLevel.CRITICAL)
    high_count = sum(1 for f in flags if f.severity == RiskLevel.HIGH)
    medium_count = sum(1 for f in flags if f.severity == RiskLevel.MEDIUM)

    if critical_count >= 1 or high_count >= 3:
        return RiskLevel.CRITICAL.value
    if high_count >= 2:
        return RiskLevel.HIGH.value
    if high_count >= 1 or medium_count >= 3:
        return RiskLevel.MEDIUM.value

    # Trust LLM if within valid values
    try:
        return RiskLevel(llm_level).value
    except ValueError:
        return RiskLevel.LOW.value
