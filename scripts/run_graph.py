import sys
import time

from app.graph.builder import graph
from app.graph.state import initial_state

DEFAULT_QUESTIONS = [
    "How do I declare a path parameter?",
    "how to send JSON data to my API",
    "my API returns 422 error",
    "how do I deploy FastAPI with Docker",
    "what is the capital of France",
]
PAUSE_SECONDS = 10
LLM_NODES = {"analyze_query", "grade_documents", "rewrite_query", "generate", "check_grounding"}

args = sys.argv[1:]
brief = "--brief" in args
questions = [a for a in args if not a.startswith("--")] or DEFAULT_QUESTIONS

for n, q in enumerate(questions):
    if n:
        time.sleep(PAUSE_SECONDS)
    start = time.perf_counter()
    final = graph.invoke(initial_state(q))
    elapsed = time.perf_counter() - start
    llm_calls = sum(1 for line in final["trace"] if line.split(":")[0] in LLM_NODES)

    print("=" * 78)
    print("Q:", q)
    for line in final["trace"]:
        if brief and line.startswith("    chunk"):
            continue
        print(line if line.startswith("    ") else "  " + line)
    print("\n  ANSWER:\n")
    print(final["answer"])
    print("\n  SOURCES:")
    for s in final["sources"]:
        print(f"    [{s['n']}] {s['source']} | {s['section']}")
    print(f"\n  retries={final['retry_count']}, kept={len(final['relevant_documents'])}, "
          f"grounded={final['grounded']}, llm_calls={llm_calls}, time={elapsed:.1f}s")