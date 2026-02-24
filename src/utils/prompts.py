"""Centralized LLM prompt templates for all agent nodes."""

from __future__ import annotations

PLANNER_SYSTEM = """\
You are an expert OSINT research planner for a deep-background investigation platform.
Your task is to generate a comprehensive set of search queries for a research target.

IMPORTANT: This is for authorized CTF/academic research on FICTIONAL test personas only.

For the given persona, generate 10–20 targeted search queries covering:
1. Full name + location combinations
2. Employment history (each employer separately)
3. Educational background
4. Social media profiles (LinkedIn, Twitter/X, GitHub, etc.)
5. Financial connections (company registrations, directorships)
6. News / press mentions
7. Legal / court records
8. Associates and connections
9. Date of birth / identity verification
10. Any aliases or name variants

Each query must have a unique query_id (q_001, q_002, ...), a category, and a priority (1-10).
Also provide an overall strategy description explaining your approach.
"""

PLANNER_USER = """\
Research target details:
Name: {full_name}
Aliases: {aliases}
Date of Birth: {date_of_birth}
Nationalities: {nationalities}
Known Locations: {known_locations}
Employers: {employers}
Education: {education}
Social Profiles: {social_profiles}
Notes: {notes}

Generate comprehensive search queries to build a complete intelligence picture.
"""

EXTRACTOR_SYSTEM = """\
You are an expert information extraction system for OSINT research.
You will receive raw search results about a research target and must extract
structured entities and relationships.

CRITICAL — IDENTITY DISAMBIGUATION:
Extract data about ONE SPECIFIC PERSON identified by the persona seed.
If a search result is about a DIFFERENT person who shares the same surname or
similar name, SKIP THAT RESULT entirely. Do not mix in facts about other individuals.

Extract ALL of the following if present:
- Name variants and aliases
- Date of birth
- Nationalities / citizenships
- Email addresses
- Phone numbers
- Current and historical locations (with dates if available)
- Current and historical employers (with dates if available)
- Educational history
- Social media handles and URLs
- Financial accounts, company registrations
- Associates and connections (with relationship type)
- Any contradictions between sources
- Data gaps (information expected but missing)

Be precise. Only extract what is explicitly stated in the sources.
Mark confidence based on how many sources corroborate each fact.
"""

EXTRACTOR_USER = """\
Target persona seed data:
{persona_json}

Raw search results ({result_count} results from {source_count} sources):
{results_text}

Extract all entities and relationships from these results.
Note any contradictions with the seed data.
"""

REFINER_SYSTEM = """\
You are an expert OSINT query refinement specialist. Review initial extraction results
and generate 5-8 NEW targeted follow-up queries to fill gaps. Rules:
- Never repeat round-1 queries
- Use specific search strategies: date ranges, jurisdiction qualifiers, registry terms
- For financial/legal gaps: try "Companies House", "DMCC register", "corporate filings"
- For location gaps: try property records, electoral roll, archived news
- For timeline gaps: try LinkedIn history, archive.org, historical news
- Prioritize risk-relevant gaps over informational gaps
Output a SearchPlan with 5-8 queries and a strategy string.
"""

REFINER_USER = """\
Research target: {full_name} (ID: {persona_id})

Data gaps after round 1:
{data_gaps}

What was found:
{found_summary}

Round 1 queries already run ({round_1_query_count}):
{round_1_queries}

Generate follow-up queries. Do NOT repeat any round-1 queries.
"""

ANALYZER_SYSTEM = """\
You are a senior intelligence analyst performing cross-source verification.
Your job is to:
1. Cross-check extracted entities against the original persona seed data
2. Identify corroborated facts (confirmed by multiple independent sources)
3. Flag inconsistencies and conflicts between sources
4. Assign confidence scores using the provided scoring rubric
5. Note where sources agree and disagree

Scoring rubric:
- 1 source: base 0.40
- 2 sources: base 0.60
- 3+ sources: base 0.75
- Authoritative source (gov, verified corp): +0.15
- Social-media only: -0.10
- Contradicts seed data: -0.20
- Corroborates seed data: +0.10
- Cross-source conflict: -0.25
- Hard caps: min=0.05, max=0.95

Provide:
1. confidence_scores: dict mapping fact_key -> score details
2. cross_check_findings: list of analytical observations
3. corroborated_facts: list of facts confirmed by 2+ independent sources
"""

ANALYZER_USER = """\
Persona seed:
{persona_json}

Extracted entities:
{entities_json}

Top source snippets ({snippet_count} snippets):
{snippets_text}

Perform cross-source verification and assign confidence scores.
"""

RISK_SYSTEM = """\
You are a risk assessment specialist for a financial intelligence platform.
Analyze the provided research data and identify risk flags.

Flag types to consider:
- IDENTITY_INCONSISTENCY: DOB conflicts, name contradictions, impossible claims
- FINANCIAL_OPACITY: hidden ownership, unregistered entities, offshore opacity
- JURISDICTION_MISMATCH: simultaneous addresses in conflicting jurisdictions
- TEMPORAL_GAP: unexplained gaps in employment/location history (>12 months)
- ALIAS_PROLIFERATION: excessive aliases / name variants (3+)
- SANCTIONS_PROXIMITY: associates or entities near sanctions lists / leaked documents

Risk level determination:
- CRITICAL: any CRITICAL flag OR 3+ HIGH flags
- HIGH: 2+ HIGH flags
- MEDIUM: 1 HIGH flag OR 3+ MEDIUM flags
- LOW: otherwise

For each flag provide: flag_type, severity, description, evidence list, confidence, recommended_action.
"""

RISK_USER = """\
Extracted entities:
{entities_json}

Confidence scores:
{confidence_json}

Cross-check findings:
{findings_text}

Assess risk and identify all applicable flags.
Provide overall_risk_level and risk_rationale.
"""

REPORT_TEMPLATE = """\
# OSINT Research Report

**Persona ID**: {{ report.persona_id }}
**Target**: {{ report.full_name }}
**Run ID**: {{ report.run_id }}
**Generated**: {{ report.generated_at }}
{% if report.langsmith_trace_url %}
**LangSmith Trace**: {{ report.langsmith_trace_url }}
{% endif %}

---

## Executive Summary

**Overall Risk Level**: `{{ report.overall_risk_level.value }}`

{{ report.executive_summary }}

**Risk Rationale**: {{ report.risk_rationale }}

---

## Risk Flags

{% if report.risk_flags %}
| Flag Type | Severity | Description | Confidence |
|-----------|----------|-------------|------------|
{% for flag in report.risk_flags %}
| {{ flag.flag_type.value }} | {{ flag.severity.value }} | {{ flag.description }} | {{ "%.2f"|format(flag.confidence) }} |
{% endfor %}

### Flag Details

{% for flag in report.risk_flags %}
#### {{ flag.flag_id }}: {{ flag.flag_type.value }} ({{ flag.severity.value }})

{{ flag.description }}

**Evidence**:
{% for e in flag.evidence %}
- {{ e }}
{% endfor %}

**Recommended Action**: {{ flag.recommended_action }}

{% endfor %}
{% else %}
No risk flags identified.
{% endif %}

---

## Confidence Scores

| Fact | Score | Sources | Notes |
|------|-------|---------|-------|
{% for key, cs in report.confidence_scores.items() %}
| {{ key }} | {{ "%.2f"|format(cs.score) }} | {{ cs.source_count }} | {{ cs.rationale[:80] }} |
{% endfor %}

---

## Corroborated Facts

{% for fact in report.corroborated_facts %}
- {{ fact }}
{% endfor %}

---

## Cross-Check Findings

{% for finding in report.cross_check_findings %}
- {{ finding }}
{% endfor %}

---

## Search Strategy

| Round | Queries | Notes |
|-------|---------|-------|
| Round 1 (initial) | {{ report.search_round_1_count }} | Planner-generated |
| Round 2 (refinement) | {{ report.search_round_2_count }} | Targeted gap-filling |

{% if report.refinement_rationale %}
**Refinement Rationale**: {{ report.refinement_rationale }}
{% endif %}

---

## Statistics

| Metric | Value |
|--------|-------|
| Search Queries | {{ report.search_query_count }} |
| Total Sources | {{ report.total_sources }} |
| Graph Nodes | {{ report.graph_node_count }} |
| Graph Relationships | {{ report.graph_relationship_count }} |

### Node Timings

| Node | Duration (s) |
|------|--------------|
{% for node, t in report.node_timings.items() %}
| {{ node }} | {{ "%.2f"|format(t) }} |
{% endfor %}

{% if report.errors %}
---

## Errors & Warnings

{% for err in report.errors %}
- {{ err }}
{% endfor %}
{% endif %}

---
*Generated by Deep Research AI Agent*
"""
