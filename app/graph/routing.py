from app.config import settings
from app.graph.state import GraphState


def route_after_grading(state: GraphState) -> str:
    if state["relevant_documents"] and state["context_sufficient"]:
        return "generate"                      # good evidence: answer
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"                 # not good enough yet: try again
    if state["relevant_documents"]:
        return "generate"                      # retries used up: answer from partial evidence
    return "fallback"                          # nothing relevant after all retries: refuse


def route_after_generate(state: GraphState) -> str:
    return "end" if state["generation_failed"] else "check_grounding"


def route_after_grounding(state: GraphState) -> str:
    if state["grounded"] is False and state["generation_attempts"] <= settings.max_regenerations:
        return "generate"                      # regenerate, told which claims to drop
    return "end"