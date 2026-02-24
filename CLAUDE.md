# Deep Research AI Agent

## Overview
Autonomous OSINT research pipeline for CTF/academic investigation of **fictional personas only**.
An 8-node LangGraph pipeline plans searches, queries 3 search APIs in parallel, extracts structured
entities with Gemini, optionally runs a second adaptive search round via a refiner node, persists
a knowledge graph to Neo4j, scores source confidence, assesses financial-crime risk flags, and
renders Markdown + JSON reports.

## Tech Stack
- **Orchestration**: LangGraph `StateGraph` — `src/agent/graph.py`
- **LLMs**: Claude Sonnet 4.6 (planner, refiner, analyzer, risk assessor) · Gemini 2.5-flash (extractor)
- **Search**: Tavily + Brave + Exa — all 3 queried in parallel per query
- **Graph DB**: Neo4j 5 Community (Docker) — `neo4j/init/schema.cypher`
- **Config**: Pydantic Settings loaded from `.env` — `src/config.py:13`
- **Models**: Pydantic v2 throughout `src/models/`
- **Report rendering**: Jinja2 template — `src/utils/prompts.py:180`
- **Tracing**: LangSmith (optional, set `LANGCHAIN_TRACING_V2=true`)

## Key Directories

| Path | Purpose |
|------|---------|
| `src/agent/` | `ResearchState` TypedDict, `StateGraph` assembly, CLI runner |
| `src/nodes/` | One file per pipeline node — planner → searcher → extractor → refiner → graph_writer → analyzer → risk_assessor → reporter |
| `src/clients/` | Thin async wrappers for every external API/DB (3 LLMs, 3 search APIs, Neo4j) |
| `src/models/` | Pydantic schemas: persona seed, search results, extracted entities, report output |
| `src/utils/` | Centralized LLM prompts, confidence scorer, async rate limiter, JSONL event logger |
| `src/evaluation/` | Evaluator CLI — scores `data.json` against `personas/evaluation/*_eval.json` |
| `personas/` | Seed JSON files for the 3 test personas (001 LOW · 002 MEDIUM · 003 HIGH) |
| `personas/evaluation/` | Ground-truth eval configs (`*_eval.json`) |
| `reports/{persona_id}/` | Per-run output: `report.md` + `data.json` |
| `logs/` | Append-only JSONL execution event streams |
| `tests/unit/` | Fast tests; all external calls mocked |
| `tests/integration/` | Full-pipeline tests with mocked LLM and search clients |

## Commands

```bash
# Neo4j (required unless NEO4J_ENABLED=false)
docker compose up -d neo4j

# Run the agent
python -m src.agent.runner --persona persona_001   # Eleanor Maddox — LOW risk
python -m src.agent.runner --persona persona_002   # Marcus Ashby  — MEDIUM risk
python -m src.agent.runner --persona persona_003   # Viktor Karev  — HIGH/CRITICAL risk

# Score a run against ground truth
python -m src.evaluation.evaluator --persona persona_001

# Tests
pytest tests/unit/ -v          # fast, no external deps
pytest tests/integration/ -v   # mocked APIs, validates full state flow
pytest -v                      # all tests
```

## Environment
Copy `.env.example` → `.env`. Required keys: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
`TAVILY_API_KEY`, `BRAVE_API_KEY`, `EXA_API_KEY`, `NEO4J_PASSWORD`.

Toggle `NEO4J_ENABLED=false` to skip graph persistence and run without Docker.
`LANGCHAIN_API_KEY` is optional — omit to disable LangSmith tracing.

## Pipeline & State
`ResearchState` TypedDict (`src/agent/state.py:15`) is the single object flowing through all nodes.
Each node receives the full state and returns a **partial dict of updates only** — LangGraph merges them.

After extractor, a conditional edge (`src/agent/graph.py:17`) routes to `refiner` for a second
search round when data gaps exist or fewer than 5 entities were extracted, then loops back to
`searcher`. Otherwise the pipeline proceeds linearly to `graph_writer`.

## Notable Config Fields (`src/config.py`)
- `analyzer_model` — Claude model for planner/refiner/analyzer/risk (default: `claude-sonnet-4-6`)
- `extractor_model` — Gemini model for extraction (default: `gemini-2.5-flash`)
- `neo4j_enabled` — skip graph writes entirely when `false`
- `max_search_results_per_query` — per-API cap per query (default: `10`)

## Additional Documentation
Check these files when working in the relevant area:

| File | When to consult |
|------|----------------|
| `.claude/docs/architectural_patterns.md` | Adding/modifying nodes, clients, or models; understanding conventions |
