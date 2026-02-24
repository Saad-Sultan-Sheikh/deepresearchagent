"""Evaluator CLI — scores a completed research run against ground-truth eval config.

Usage:
    python -m src.evaluation.evaluator --persona persona_001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ANSI color helpers
def _green(s: str) -> str:
    return f"\033[92m{s}\033[0m"


def _red(s: str) -> str:
    return f"\033[91m{s}\033[0m"


def _yellow(s: str) -> str:
    return f"\033[93m{s}\033[0m"


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def evaluate(report_data: dict[str, Any], eval_config: dict[str, Any]) -> dict[str, Any]:
    """Score report_data against eval_config.

    Returns a dict with per-check results and an overall pass/fail.
    """
    checks: list[dict[str, Any]] = []
    all_passed = True

    # ── 1. Risk level check ─────────────────────────────────────────────────
    expected_risk = eval_config.get("expected_risk_level", "")
    actual_risk = report_data.get("overall_risk_level", "UNKNOWN")
    # persona_003 accepts HIGH or CRITICAL
    if isinstance(actual_risk, dict):
        actual_risk = actual_risk.get("value", "UNKNOWN")
    persona_id = eval_config.get("persona_id", "")
    if persona_id == "persona_003":
        risk_pass = actual_risk in ("HIGH", "CRITICAL")
    else:
        risk_pass = actual_risk == expected_risk
    checks.append({
        "check": "risk_level",
        "expected": expected_risk,
        "actual": actual_risk,
        "passed": risk_pass,
        "message": f"Risk level: expected={expected_risk}, actual={actual_risk}",
    })
    if not risk_pass:
        all_passed = False

    # ── 2. Flag count check ──────────────────────────────────────────────────
    risk_flags = report_data.get("risk_flags", [])
    flag_count = len(risk_flags)
    min_flags = eval_config.get("expected_flag_count_min", 0)
    max_flags = eval_config.get("expected_flag_count_max", 999)
    flag_count_pass = min_flags <= flag_count <= max_flags
    checks.append({
        "check": "flag_count",
        "expected": f"{min_flags}–{max_flags}",
        "actual": flag_count,
        "passed": flag_count_pass,
        "message": f"Flag count: expected {min_flags}–{max_flags}, actual={flag_count}",
    })
    if not flag_count_pass:
        all_passed = False

    # ── 3. Required flag types ────────────────────────────────────────────────
    actual_flag_types: set[str] = set()
    for f in risk_flags:
        ft = f.get("flag_type", "")
        if isinstance(ft, dict):
            ft = ft.get("value", "")
        actual_flag_types.add(ft)

    required_flag_types = eval_config.get("expected_flag_types", [])
    for required_type in required_flag_types:
        present = required_type in actual_flag_types
        checks.append({
            "check": f"required_flag_{required_type}",
            "expected": required_type,
            "actual": list(actual_flag_types),
            "passed": present,
            "message": f"Required flag {required_type}: {'found' if present else 'MISSING'}",
        })
        if not present:
            all_passed = False

    # ── 4. Forbidden flag types ───────────────────────────────────────────────
    forbidden_flag_types = eval_config.get("forbidden_flag_types", [])
    for forbidden_type in forbidden_flag_types:
        present = forbidden_type in actual_flag_types
        checks.append({
            "check": f"forbidden_flag_{forbidden_type}",
            "expected": f"NOT {forbidden_type}",
            "actual": list(actual_flag_types),
            "passed": not present,
            "message": f"Forbidden flag {forbidden_type}: {'PRESENT (fail)' if present else 'absent (ok)'}",
        })
        if present:
            all_passed = False

    # ── 5. Average confidence score ───────────────────────────────────────────
    min_confidence = eval_config.get("min_confidence_score", 0.0)
    confidence_scores = report_data.get("confidence_scores", {})
    if confidence_scores:
        scores = []
        for cs in confidence_scores.values():
            if isinstance(cs, dict):
                scores.append(float(cs.get("score", 0.0)))
        avg_conf = sum(scores) / len(scores) if scores else 0.0
    else:
        avg_conf = 0.0
    conf_pass = avg_conf >= min_confidence or not confidence_scores
    checks.append({
        "check": "avg_confidence",
        "expected": f">={min_confidence:.2f}",
        "actual": f"{avg_conf:.2f}",
        "passed": conf_pass,
        "message": f"Avg confidence: {avg_conf:.2f} (min={min_confidence:.2f})",
    })
    if not conf_pass:
        all_passed = False

    # ── 6. Graph node count ───────────────────────────────────────────────────
    min_entity_count = eval_config.get("min_entity_count", 0)
    graph_node_count = report_data.get("graph_node_count", 0)
    node_pass = graph_node_count >= min_entity_count
    checks.append({
        "check": "graph_node_count",
        "expected": f">={min_entity_count}",
        "actual": graph_node_count,
        "passed": node_pass,
        "message": f"Graph nodes: {graph_node_count} (min={min_entity_count})",
    })
    if not node_pass:
        all_passed = False

    # ── 7. Required corroborated facts ────────────────────────────────────────
    corroborated_facts = report_data.get("corroborated_facts", [])
    corroborated_text = " | ".join(corroborated_facts).lower()
    required_facts = eval_config.get("required_corroborated_facts", [])
    for fact in required_facts:
        found = fact.lower() in corroborated_text
        checks.append({
            "check": f"corroborated_fact_{fact[:30]}",
            "expected": fact,
            "actual": "present" if found else "absent",
            "passed": found,
            "message": f"Required fact '{fact[:40]}...': {'found' if found else 'MISSING'}",
        })
        if not found:
            all_passed = False

    return {
        "persona_id": persona_id,
        "overall_pass": all_passed,
        "checks": checks,
        "notes": eval_config.get("notes", ""),
    }


def _print_results(results: dict[str, Any]) -> None:
    persona_id = results["persona_id"]
    overall = results["overall_pass"]
    status_str = _green("PASS") if overall else _red("FAIL")

    print()
    print(_bold(f"Evaluation: {persona_id}"))
    print("=" * 60)

    for check in results["checks"]:
        icon = "✓" if check["passed"] else "✗"
        color = _green if check["passed"] else _red
        print(f"  {color(icon)} {check['message']}")

    print()
    if results.get("notes"):
        print(_yellow(f"Notes: {results['notes']}"))
    print(_bold(f"Overall: {status_str}"))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Deep Research Agent output")
    parser.add_argument(
        "--persona",
        required=True,
        help="Persona ID (e.g. persona_001)",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing report outputs",
    )
    parser.add_argument(
        "--eval-dir",
        default="personas/evaluation",
        help="Directory containing evaluation JSON configs",
    )
    args = parser.parse_args()

    # Load report data
    report_path = Path(args.reports_dir) / args.persona / "data.json"
    if not report_path.exists():
        print(_red(f"Error: Report not found at {report_path}"))
        print("Run the agent first: python -m src.agent.runner --persona " + args.persona)
        sys.exit(1)

    report_data = json.loads(report_path.read_text(encoding="utf-8"))

    # Load eval config
    eval_path = Path(args.eval_dir) / f"{args.persona}_eval.json"
    if not eval_path.exists():
        print(_red(f"Error: Eval config not found at {eval_path}"))
        sys.exit(1)

    eval_config = json.loads(eval_path.read_text(encoding="utf-8"))

    # Run evaluation
    results = evaluate(report_data, eval_config)
    _print_results(results)

    sys.exit(0 if results["overall_pass"] else 1)


if __name__ == "__main__":
    main()
