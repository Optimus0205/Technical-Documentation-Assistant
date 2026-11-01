from app.config import settings
from app.vectorstore import get_vectorstore

# (query, set of source files that SHOULD contain the answer; empty = no answer in corpus)
TESTS = [
    ("How do I declare a path parameter?", {"path-params.md"}),
    ("how to send JSON data to my API", {"body.md"}),
    ("how does it work", set()),
    ("my API returns 422 error", {"handling-errors.md", "path-params.md"}),
    ("how do I deploy FastAPI with Docker", set()),
    ("what is the capital of France", set()),
]

store = get_vectorstore()
print(f"{'query':45} {'best':>6} {'rank':>5} {'code':>5}  top result")
for query, expected in TESTS:
    results = store.similarity_search_with_score(query, k=settings.top_k)
    rank = next(
        (i + 1 for i, (d, _) in enumerate(results) if d.metadata["source"] in expected),
        None,
    )
    has_code = lambda t: "```" in t or "def " in t or "import " in t
    code_chunks = sum(has_code(d.page_content) for d, _ in results)
    top_doc, best = results[0]
    print(
        f"{query[:44]:45} {best:6.3f} {str(rank or '-'):>5} {code_chunks:>5}  "
        f"{top_doc.metadata['source']} | {top_doc.metadata['section'][-45:]}"
    )