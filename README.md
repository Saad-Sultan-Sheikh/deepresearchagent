# Deep Research AI Agent

An autonomous OSINT research agent for CTF / academic research using **fully fictional test personas**. The agent investigates a target persona by running multi-step web searches, extracting structured entities, persisting an identity graph to Neo4j, cross-checking sources with confidence scores, assessing risks, and generating Markdown + JSON reports.

> **Important:** This tool is designed exclusively for authorized security research, CTF competitions, and academic study using fictional personas. Never use it against real individuals without explicit authorization.

---

## Architecture

```
[planner] → [searcher] → [extractor] → [graph_writer] → [analyzer] → [risk_assessor] → [reporter]
```

| Layer | Technology |
|---|---|
| Orchestration | LangGraph `StateGraph` (7 nodes) |
| Tracing | LangSmith cloud |
| Planner LLM | OpenAI GPT-4o |
| Analyzer / Risk LLM | Anthropic Claude Sonnet 4.6 |
| Extractor LLM | Google Gemini 1.5 Pro |
| Search APIs | Tavily + Brave Search + Exa AI (parallel) |
| Graph DB | Neo4j 5 Community (Docker) |
| Output | `reports/{persona_id}/report.md` + `data.json` |

---

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- API keys for all services (see below)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in all API keys
```

Required API keys:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
TAVILY_API_KEY=tvly-...
BRAVE_API_KEY=BSA...
EXA_API_KEY=...
NEO4J_PASSWORD=strongpassword123
LANGCHAIN_API_KEY=ls__...
```

### 3. Start Neo4j

```bash
docker compose up -d neo4j
```

Wait for Neo4j to be healthy:
```bash
docker compose ps   # check neo4j status is "healthy"
```

### 4. Run research on a persona

```bash
# Run persona_001 (Eleanor Maddox — clean profile, expect LOW risk)
docker compose run agent --persona persona_001

# Run persona_002 (Marcus Ashby — mixed profile, expect MEDIUM risk)
docker compose run agent --persona persona_002

# Run persona_003 (Viktor Karev — high-risk, expect HIGH/CRITICAL)
docker compose run agent --persona persona_003
```

### 5. View outputs

```bash
# Markdown report
cat reports/persona_001/report.md

# JSON data
cat reports/persona_001/data.json

# Execution log
cat logs/execution_*.jsonl
```

**Neo4j Browser**: Open `http://localhost:7474` (user: `neo4j`, password: from `.env`)
```cypher
MATCH (n) RETURN n LIMIT 50
```

**LangSmith Dashboard**: View traces at https://smith.langchain.com

---

## Local Development

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run directly (without Docker)

```bash
# Start Neo4j first
docker compose up -d neo4j

# Set NEO4J_URI to localhost
export NEO4J_URI=bolt://localhost:7687

python -m src.agent.runner --persona persona_001
```

---

## Running Tests

```bash
# Unit tests (no external services required)
pytest tests/unit/ -v

# Integration tests (requires Neo4j running)
docker compose up -d neo4j
pytest tests/integration/ -v

# All tests
pytest tests/ -v
```

---

## Test Personas

| Persona | Name | Expected Risk | Key Characteristics |
|---------|------|---------------|---------------------|
| `persona_001` | Eleanor Grace Maddox | LOW | Clean Portland software engineer; consistent history |
| `persona_002` | Marcus Delroy Ashby | MEDIUM | British financial consultant; Malta gap, employment inconsistency |
| `persona_003` | Viktor Semyon Karev | HIGH/CRITICAL | Dubai blockchain; DOB conflict, multi-jurisdiction, Pandora Papers associates |

---

## Expected Verification Checklist

After running all 3 personas:

- [ ] `reports/persona_001/report.md` — risk level `LOW`, 0 flags
- [ ] `reports/persona_002/report.md` — risk level `MEDIUM`, Malta address flagged, confidence ~0.45
- [ ] `reports/persona_003/report.md` — risk level `HIGH` or `CRITICAL`, 3+ flags including `IDENTITY_INCONSISTENCY`, `FINANCIAL_OPACITY`, `JURISDICTION_MISMATCH`
- [ ] Neo4j Browser shows nodes and relationships for all 3 runs
- [ ] LangSmith dashboard shows 7-node traces per run
- [ ] `logs/execution_*.jsonl` — each line is a structured event with timing

---

## Project Structure

```
Application/
├── src/
│   ├── config.py                  # Pydantic Settings
│   ├── agent/
│   │   ├── graph.py               # StateGraph assembly
│   │   ├── state.py               # ResearchState TypedDict
│   │   └── runner.py              # CLI entry point
│   ├── nodes/                     # 7 pipeline nodes
│   │   ├── planner.py             # GPT-4o query planning
│   │   ├── searcher.py            # Parallel Tavily + Brave + Exa
│   │   ├── extractor.py           # Gemini entity extraction
│   │   ├── graph_writer.py        # Neo4j persistence
│   │   ├── analyzer.py            # Claude cross-check + confidence
│   │   ├── risk_assessor.py       # Claude risk flags
│   │   └── reporter.py            # Jinja2 Markdown + JSON output
│   ├── clients/                   # API/DB wrappers
│   ├── models/                    # Pydantic models
│   └── utils/                     # Rate limiter, logging, confidence, prompts
├── personas/                      # 3 fictional test personas
├── neo4j/init/schema.cypher       # DB constraints + indexes
├── tests/                         # Unit + integration tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Risk Level Determination

| Level | Condition |
|-------|-----------|
| `CRITICAL` | Any CRITICAL flag OR 3+ HIGH flags |
| `HIGH` | 2+ HIGH flags |
| `MEDIUM` | 1 HIGH flag OR 3+ MEDIUM flags |
| `LOW` | Otherwise |

## Flag Types

| Flag | Description |
|------|-------------|
| `IDENTITY_INCONSISTENCY` | DOB conflicts, name contradictions |
| `FINANCIAL_OPACITY` | Hidden ownership, unregistered entities |
| `JURISDICTION_MISMATCH` | Simultaneous addresses in conflicting jurisdictions |
| `TEMPORAL_GAP` | Unexplained gaps >12 months |
| `ALIAS_PROLIFERATION` | Excessive aliases (3+) |
| `SANCTIONS_PROXIMITY` | Associates near sanctions lists / leaked documents |

## Confidence Scoring

Base scores: 1 source → 0.40, 2 sources → 0.60, 3+ sources → 0.75

Modifiers: Authoritative source +0.15 | Social-only −0.10 | Contradicts seed −0.20 | Corroborates seed +0.10 | Cross-source conflict −0.25

Hard caps: min=0.05, max=0.95
