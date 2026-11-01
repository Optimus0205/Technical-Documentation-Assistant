from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.routing import route_after_generate, route_after_grading, route_after_grounding
from app.graph.state import GraphState


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("analyze_query", nodes.analyze_query)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("grade_documents", nodes.grade_documents)
    builder.add_node("rewrite_query", nodes.rewrite_query)
    builder.add_node("generate", nodes.generate)
    builder.add_node("check_grounding", nodes.check_grounding)
    builder.add_node("fallback", nodes.fallback)

    builder.add_edge(START, "analyze_query")
    builder.add_edge("analyze_query", "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    builder.add_conditional_edges(
        "grade_documents",
        route_after_grading,
        {"generate": "generate", "rewrite_query": "rewrite_query", "fallback": "fallback"},
    )
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_conditional_edges(
        "generate",
        route_after_generate,
        {"check_grounding": "check_grounding", "end": END},
    )
    builder.add_conditional_edges(
        "check_grounding",
        route_after_grounding,
        {"generate": "generate", "end": END},
    )
    builder.add_edge("fallback", END)

    return builder.compile()


graph = build_graph()