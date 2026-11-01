import operator
from typing import Annotated, TypedDict

from langchain_core.documents import Document

from app.config import settings


class GraphState(TypedDict):
    question: str                       # the user's original words, never overwritten
    query_type: str
    search_query: str                   # what we actually search with (may be rewritten)
    tried_queries: Annotated[list[str], operator.add]
    top_k: int
    retry_count: int
    documents: list[Document]
    relevant_documents: list[Document]
    grading_feedback: str
    context_sufficient: bool
    answer: str
    sources: list[dict]
    generation_attempts: int
    generation_failed: bool
    grounded: bool | None               # None = not verified
    unsupported_claims: list[str]
    trace: Annotated[list[str], operator.add]   # append-only log


def initial_state(question: str) -> GraphState:
    return {
        "question": question,
        "query_type": "",
        "search_query": question,
        "tried_queries": [],
        "top_k": settings.top_k,
        "retry_count": 0,
        "documents": [],
        "relevant_documents": [],
        "grading_feedback": "",
        "context_sufficient": False,
        "answer": "",
        "sources": [],
        "generation_attempts": 0,
        "generation_failed": False,
        "grounded": None,
        "unsupported_claims": [],
        "trace": [],
    }