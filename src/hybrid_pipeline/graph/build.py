"""Construção do grafo LangGraph."""

from langgraph.graph import END, START, StateGraph

from hybrid_pipeline.graph.nodes import (
    analysis_node,
    generation_node,
    parsing_node,
    validation_node,
)
from hybrid_pipeline.graph.state import PipelineState


def build_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("parsing", parsing_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("generation", generation_node)
    builder.add_node("validation", validation_node)

    builder.add_edge(START, "parsing")
    builder.add_edge("parsing", "analysis")
    builder.add_edge("analysis", "generation")
    builder.add_edge("generation", "validation")
    builder.add_edge("validation", END)

    return builder.compile()


graph = build_graph()
