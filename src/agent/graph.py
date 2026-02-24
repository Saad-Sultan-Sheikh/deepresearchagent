"""LangGraph StateGraph assembly — wires all 7 nodes into a compiled pipeline."""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from src.agent.state import ResearchState
from src.nodes.planner import planner
from src.nodes.searcher import searcher
from src.nodes.extractor import extractor
from src.nodes.refiner import refiner
from src.nodes.graph_writer import graph_writer
from src.nodes.analyzer import analyzer
from src.nodes.risk_assessor import risk_assessor
from src.nodes.reporter import reporter

log = logging.getLogger(__name__)


def _route_after_extractor(state: ResearchState) -> str:
    """Route to refiner for a second search round if data gaps exist, else proceed."""
    search_round = state.get("search_round", 1)
    entities = state.get("extracted_entities")
    data_gaps = entities.data_gaps if entities else []
    entity_count = len(entities.entities) if entities else 0
    if search_round < 2 and (len(data_gaps) > 0 or entity_count < 5):
        log.info(
            "Routing to refiner (round=%d, gaps=%d, entities=%d)",
            search_round,
            len(data_gaps),
            entity_count,
        )
        return "refiner"
    return "graph_writer"


def build_graph():
    """Build and compile the research agent StateGraph."""
    workflow = StateGraph(ResearchState)

    # Register nodes
    workflow.add_node("planner", planner)
    workflow.add_node("searcher", searcher)
    workflow.add_node("extractor", extractor)
    workflow.add_node("refiner", refiner)
    workflow.add_node("graph_writer", graph_writer)
    workflow.add_node("analyzer", analyzer)
    workflow.add_node("risk_assessor", risk_assessor)
    workflow.add_node("reporter", reporter)

    # Define edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "searcher")
    workflow.add_edge("searcher", "extractor")
    # After extraction: conditionally refine or proceed
    workflow.add_conditional_edges(
        "extractor",
        _route_after_extractor,
        {"refiner": "refiner", "graph_writer": "graph_writer"},
    )
    workflow.add_edge("refiner", "searcher")  # loop back for round 2
    workflow.add_edge("graph_writer", "analyzer")
    workflow.add_edge("analyzer", "risk_assessor")
    workflow.add_edge("risk_assessor", "reporter")
    workflow.add_edge("reporter", END)

    return workflow.compile()


# Compiled graph singleton — import and use this
research_graph = build_graph()
