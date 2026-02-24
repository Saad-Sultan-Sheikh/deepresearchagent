"""CLI entry point — loads a persona JSON and runs the research graph."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# Ensure project root on sys.path when running as __main__
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agent.graph import research_graph
from src.agent.state import ResearchState
from src.clients.neo4j_client import close_driver, init_schema
from src.config import get_settings
from src.models.persona import PersonaInput
from src.utils.logging import ExecutionLogger, log

console = Console()


async def run_persona(persona_id: str, personas_dir: Path = Path("personas")) -> dict:
    """Load persona JSON, initialize state, stream graph, return final state."""
    settings = get_settings()

    # Load persona
    persona_path = personas_dir / f"{persona_id}.json"
    if not persona_path.exists():
        raise FileNotFoundError(f"Persona file not found: {persona_path}")

    persona_data = json.loads(persona_path.read_text(encoding="utf-8"))
    persona = PersonaInput(**persona_data)

    run_id = str(uuid.uuid4())[:8]
    exec_log = ExecutionLogger(run_id)

    console.print(
        Panel(
            f"[bold cyan]Deep Research Agent[/bold cyan]\n"
            f"Persona: [yellow]{persona.full_name}[/yellow] ({persona_id})\n"
            f"Run ID: [dim]{run_id}[/dim]",
            title="Starting Research Run",
        )
    )

    # Initialize Neo4j schema
    try:
        await init_schema()
    except Exception as exc:
        log.warning("Neo4j schema init failed (continuing without graph): %s", exc)

    # Build initial state
    initial_state: ResearchState = {
        "persona_id": persona_id,
        "persona_input": persona,
        "search_queries": [],
        "query_strategy": "",
        "raw_results": [],
        "search_metadata": {},
        "extracted_entities": None,  # type: ignore[assignment]
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
        "report_data": None,  # type: ignore[assignment]
        "search_round": 1,
        "search_round_1_count": 0,
        "refinement_rationale": "",
        "run_id": run_id,
        "errors": [],
        "current_node": "",
        "node_timings": {},
        "langsmith_trace_url": None,
    }

    final_state = initial_state.copy()

    # Configure LangSmith metadata
    config = {
        "metadata": {
            "persona_id": persona_id,
            "run_id": run_id,
        },
        "tags": [persona_id, run_id],
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running research pipeline...", total=None)

        async for chunk in research_graph.astream(initial_state, config=config):
            node_name = list(chunk.keys())[0] if chunk else "unknown"
            progress.update(task, description=f"[cyan]Node: {node_name}[/cyan]")

            # Merge chunk into final state
            for key, value in chunk.items():
                if isinstance(value, dict):
                    # chunk is {node_name: {state_updates}}
                    for state_key, state_val in value.items():
                        if state_key == "errors" and isinstance(state_val, list):
                            # Accumulate errors
                            existing = final_state.get("errors", [])
                            final_state["errors"] = existing + state_val
                        else:
                            final_state[state_key] = state_val

            exec_log.node_end(
                node=node_name,
                duration_ms=final_state.get("node_timings", {}).get(node_name, 0) * 1000,
                output_keys=list(chunk.get(node_name, {}).keys()) if node_name in chunk else [],
            )

    # Extract LangSmith trace URL if available
    langsmith_url = _get_langsmith_url()
    if langsmith_url:
        final_state["langsmith_trace_url"] = langsmith_url

    # Print summary
    risk_level = final_state.get("overall_risk_level", "UNKNOWN")
    report_path = final_state.get("report_markdown_path", "")
    flag_count = len(final_state.get("risk_flags") or [])

    console.print(
        Panel(
            f"[bold]Risk Level:[/bold] [{_risk_color(risk_level)}]{risk_level}[/{_risk_color(risk_level)}]\n"
            f"[bold]Flags:[/bold] {flag_count}\n"
            f"[bold]Report:[/bold] {report_path}\n"
            f"[bold]Errors:[/bold] {len(final_state.get('errors') or [])}",
            title="[green]Research Complete[/green]",
        )
    )

    await close_driver()
    return final_state


def _get_langsmith_url() -> str | None:
    """Attempt to get the LangSmith trace URL from the environment."""
    try:
        from langsmith import Client
        client = Client()
        # LangSmith URL is available via the run metadata after streaming
        project = os.getenv("LANGCHAIN_PROJECT", "deep-research-agent")
        return f"https://smith.langchain.com/projects/{project}"
    except Exception:
        return None


def _risk_color(level: str) -> str:
    return {
        "LOW": "green",
        "MEDIUM": "yellow",
        "HIGH": "red",
        "CRITICAL": "bold red",
    }.get(level, "white")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep Research AI Agent")
    parser.add_argument(
        "--persona",
        required=True,
        help="Persona ID to research (e.g. persona_001)",
    )
    parser.add_argument(
        "--personas-dir",
        default="personas",
        help="Directory containing persona JSON files",
    )
    args = parser.parse_args()

    asyncio.run(run_persona(args.persona, Path(args.personas_dir)))


if __name__ == "__main__":
    main()
