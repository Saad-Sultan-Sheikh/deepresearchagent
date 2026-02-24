# Architectural Patterns

Patterns observed across multiple files in this codebase. Deviate only with good reason.

---

## 1. Node Contract

Every pipeline node follows the same signature and internal structure.
Appears in all 8 files under `src/nodes/`.

```
async def <node_name>(state: ResearchState) -> dict
```

Internal structure (in order):
1. Record start time with `time.monotonic()`
2. Extract needed fields from `state`
3. Do work (LLM call / API call / DB write)
4. Collect errors into a local `errors: list[str] = []`
5. Merge `node_timings` from state, add own duration
6. Return a **partial dict** — only the keys this node updates

Keys every node must return: `"current_node"` (set to `NODE_NAME`), `"node_timings"`, `"errors"`.

Reference implementation: `src/nodes/planner.py:23` · `src/nodes/searcher.py:23`.

**Never return the full state** — LangGraph merges partial dicts automatically.

---

## 2. Error Accumulation (operator.add reducer)

`ResearchState.errors` is declared as `Annotated[list[str], operator.add]`
(`src/agent/state.py:54`). LangGraph uses the `operator.add` reducer, so each
node's returned `"errors"` list is **appended** to the existing list, not overwritten.

Consequence: every node should return `"errors": errors` even when the list is empty.
Never mutate `state["errors"]` directly.

The runner (`src/agent/runner.py:116`) replicates this manually when merging chunks
outside the graph.

---

## 3. Timing Pattern

Every node records its own wall-clock duration and accumulates timings from prior nodes.
Appears in all 8 node files.

```python
t0 = time.monotonic()
# ... work ...
duration = time.monotonic() - t0
timings = dict(state.get("node_timings") or {})
timings[NODE_NAME] = duration
return { ..., "node_timings": timings }
```

`dict(state.get("node_timings") or {})` creates a shallow copy so prior node timings
are preserved. Reporter renders these as a table (`src/nodes/reporter.py:56`).

---

## 4. Pydantic Settings Singleton

`src/config.py:70` — `get_settings()` is decorated with `@lru_cache(maxsize=1)`.
**Always call `get_settings()`** rather than constructing `Settings()` directly.
All client modules follow this; see `src/clients/anthropic_client.py:16`.

The same lazy-singleton pattern applies to the Neo4j driver:
module-level `_driver: AsyncDriver | None = None` initialized on first call to
`get_driver()` (`src/clients/neo4j_client.py`).

---

## 5. Structured LLM Completion Interface

All three LLM clients expose identical async functions:

```python
async def structured_completion(
    prompt_messages: list[dict[str, str]],   # [{"role": "system"|"user", "content": "..."}]
    output_schema: Type[T],                   # Pydantic BaseModel subclass
    temperature: float | None = None,
) -> T

async def text_completion(
    prompt_messages: list[dict[str, str]],
    temperature: float | None = None,
) -> str
```

Implemented in:
- `src/clients/anthropic_client.py:25` (Claude Sonnet 4.6)
- `src/clients/gemini_client.py:24` (Gemini 2.5-flash)
- `src/clients/openai_client.py` (unused — no OpenAI credits)

`structured_completion` uses LangChain's `.with_structured_output(schema)` to enforce
Pydantic validation on the model response. Callers receive a fully-validated model
instance or an exception — never raw JSON.

**Nodes mock this function** in tests via `patch("src.nodes.<node>.anthropic_client.structured_completion", AsyncMock(...))`.

---

## 6. Search Client Interface

All three search clients expose the same return type:

```python
async def search(
    query: SearchQuery,
    max_results: int | None = None,
) -> tuple[list[RawResult], SearchMeta]
```

Implemented in `src/clients/tavily_client.py`, `src/clients/brave_client.py`,
`src/clients/exa_client.py`.

`SearchMeta` captures: `api`, `query_id`, `result_count`, `latency_ms`, `success`, `error`.
The searcher node calls all three in parallel with `asyncio.gather(*tasks, return_exceptions=True)`
and treats `isinstance(res, Exception)` results as non-fatal errors (`src/nodes/searcher.py:46`).

---

## 7. Centralized Prompt Templates

All LLM prompt strings live in `src/utils/prompts.py` — never inline in node files.
Each node has a `_SYSTEM` + `_USER` pair. User templates use `str.format()` with
named placeholders. The report template uses Jinja2 `{{ }}` syntax.

Naming convention:
- `PLANNER_SYSTEM` / `PLANNER_USER`
- `EXTRACTOR_SYSTEM` / `EXTRACTOR_USER`
- `REFINER_SYSTEM` / `REFINER_USER`
- `ANALYZER_SYSTEM` / `ANALYZER_USER`
- `RISK_SYSTEM` / `RISK_USER`
- `REPORT_TEMPLATE` (Jinja2, rendered in `src/nodes/reporter.py:103`)

---

## 8. Neo4j MERGE Idempotency

The graph writer (`src/nodes/graph_writer.py`) uses Cypher `MERGE` (never `CREATE`)
for all node and relationship writes. This makes every run safe to re-execute —
duplicate runs produce the same graph state, not duplicate nodes.

Node uniqueness is enforced by constraints defined in `neo4j/init/schema.cypher`,
applied at startup via `init_schema()` in `src/clients/neo4j_client.py`.

If `NEO4J_ENABLED=false` (`src/config.py:33`), the graph writer returns immediately
with empty lists — all downstream nodes continue unaffected.

---

## 9. Pydantic Field Validators for LLM Output Coercion

LLM models occasionally return JSON-stringified dicts for fields typed as `dict`.
Affected models add a `@field_validator(..., mode="before")` to coerce string → dict:

- `Entity.metadata` — `src/models/entities.py:21`
- `Relationship.properties` — `src/models/entities.py:43`

Pattern:
```python
@field_validator("field_name", mode="before")
@classmethod
def coerce_field(cls, v: Any) -> dict:
    if isinstance(v, str):
        try: return json.loads(v)
        except Exception: return {}
    return v if isinstance(v, dict) else {}
```

Apply this to any `dict`-typed field on a model that receives LLM output.

Fields that the LLM reliably omits get `default` or `default_factory`:
- `Entity.entity_id` — `src/models/entities.py:12` (`default_factory` UUID)
- `Relationship.relationship_id` — `src/models/entities.py:33` (`default_factory` UUID)
- `Entity.value` — `src/models/entities.py:14` (`default=""`)

---

## 10. Test Fixture Composition

`tests/conftest.py` defines a composable fixture hierarchy. Unit tests should use
the lowest-level fixture that covers their needs; integration tests compose upward.

```
sample_persona
sample_queries
now_iso ──────┬── sample_raw_results
              └── sample_entities ──┬── base_state
                                    └── (sample_confidence_scores, sample_risk_flag)
```

`base_state` (`tests/conftest.py:150`) is a fully-populated `ResearchState` dict
suitable for passing directly to any node under test.

Async node tests follow this pattern:
```python
@pytest.mark.asyncio
async def test_<node>_<behaviour>(base_state):
    mock = AsyncMock(return_value=<expected_output>)
    with patch("src.nodes.<node>.<client>.structured_completion", mock):
        result = await <node>(base_state)
    assert result["<key>"] == <expected>
```

`pytest.ini` sets `asyncio_mode = auto`, so `@pytest.mark.asyncio` is optional
but included for explicitness.

---

## 11. Raw Results Accumulation Across Search Rounds

The searcher node accumulates results across rounds rather than overwriting.
This is the only node that reads its own output field from prior state:

```python
existing_results = list(state.get("raw_results") or [])
# ... collect new results into all_results ...
return { "raw_results": existing_results + all_results, ... }
```

`src/nodes/searcher.py:32`. All other nodes overwrite their output fields.

The refiner sets `"search_queries"` to only the round-2 queries. The reporter
therefore reads `state["search_round_1_count"]` (set by refiner) to know how
many were round-1 vs round-2 (`src/nodes/reporter.py:40`).
