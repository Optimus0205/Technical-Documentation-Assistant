import time
import uuid

from app.graph.builder import graph
from app.graph.state import initial_state

LLM_NODES = {"analyze_query", "grade_documents", "rewrite_query", "generate", "check_grounding"}


def _is_node_line(line: str) -> bool:
    return not line.startswith(" ")      # per-chunk detail lines are indented


def run_query(question: str) -> dict:
    """Run the LangGraph workflow and shape its final state into an API result."""
    start = time.perf_counter()
    final = graph.invoke(initial_state(question), config={"recursion_limit": 30})
    latency = time.perf_counter() - start

    trace = final["trace"]
    docs = final["relevant_documents"]

    sources = []
    for s in final["sources"]:
        doc = docs[s["n"] - 1]           # the citation number maps to the passage given to the LLM
        sources.append({
            **s,
            "snippet": doc.page_content[:200].replace("\n", " "),
            "distance": doc.metadata.get("distance"),
        })

    node_lines = [line for line in trace if _is_node_line(line)]
    check_ran = any(line.startswith("check_grounding") for line in node_lines)
    return {
        "query_id": uuid.uuid4().hex,
        "answer": final["answer"],
        "refused": not docs,
        "grounded": final["grounded"],
        "degraded": any("FAILED" in line for line in node_lines) or (bool(docs) and not check_ran),
        "unsupported_claims": final["unsupported_claims"],
        "sources": sources,
        "stats": {
            "retries": final["retry_count"],
            "llm_calls": sum(1 for line in node_lines if line.split(":")[0] in LLM_NODES),
            "latency_seconds": round(latency, 1),
        },
        "trace": trace,
        "generation_failed": final["generation_failed"],   # used by the endpoint, not returned to the client
    }