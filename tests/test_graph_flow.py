from langchain_core.documents import Document

from app.config import settings
from app.graph import nodes
from app.graph.builder import build_graph
from app.graph.state import initial_state


def make_doc(i):
    return Document(page_content=f"chunk {i}", metadata={"source": "s.md", "section": "S"})


class FakeStore:
    def __init__(self):
        self.calls = []                                    # (query, k) for every search

    def similarity_search_with_score(self, query, k):
        self.calls.append((query, k))
        return [(make_doc(i), 0.5) for i in range(k)]


class FakeLLM:
    def invoke(self, messages):
        class Reply:
            content = "Use the thing [1]."
        return Reply()


def run_graph(monkeypatch, grade_plan, grounding_plan=(True,)):
    """grade_plan: one entry per grading round: True (relevant chunk), False (nothing relevant), "fail".
    grounding_plan: one entry per grounding check."""
    store = FakeStore()
    grades, checks = iter(grade_plan), iter(grounding_plan)

    def fake_call(schema, messages):
        if schema is nodes.QueryAnalysis:
            return nodes.QueryAnalysis(query_type="how_to", search_query="first query"), None
        if schema is nodes.QueryRewrite:
            return nodes.QueryRewrite(search_query="rewritten query"), None
        if schema is nodes.BatchGrade:
            plan = next(grades)
            if plan == "fail":
                return None, "RuntimeError: boom"
            if plan:
                return nodes.BatchGrade(
                    grades=[nodes.ChunkGrade(chunk=1, relevant=True, reason="ok")], sufficient=True), None
            return nodes.BatchGrade(grades=[], sufficient=False), None   # missing grades = not relevant
        if schema is nodes.GroundingCheck:
            ok = next(checks)
            claims = [] if ok else ["claim X"]
            return nodes.GroundingCheck(grounded=ok, unsupported_claims=claims), None
        raise AssertionError(f"unexpected schema {schema}")

    monkeypatch.setattr(nodes, "_call", fake_call)
    monkeypatch.setattr(nodes, "get_vectorstore", lambda: store)
    monkeypatch.setattr(nodes, "get_llm", lambda *a, **k: FakeLLM())
    final = build_graph().invoke(initial_state("a question"))
    return final, store


def test_retry_then_answer_grows_k(monkeypatch):
    final, store = run_graph(monkeypatch, [False, True])
    assert final["retry_count"] == 1
    assert [k for _, k in store.calls] == [settings.top_k, settings.top_k + 4]
    assert store.calls[1][0] == "rewritten query"
    assert final["grounded"] is True
    assert [s["n"] for s in final["sources"]] == [1]


def test_retries_are_bounded_then_refuses(monkeypatch):
    final, store = run_graph(monkeypatch, [False] * (settings.max_retries + 1))
    assert final["answer"] == "I don't know based on the documentation."
    assert final["retry_count"] == settings.max_retries
    assert len(store.calls) == settings.max_retries + 1
    assert final["grounded"] is None


def test_grader_failure_fails_closed_and_is_traced(monkeypatch):
    final, _ = run_graph(monkeypatch, ["fail"] * (settings.max_retries + 1))
    assert final["answer"] == "I don't know based on the documentation."
    assert any("grade_documents: FAILED" in line for line in final["trace"])


def test_ungrounded_answer_is_regenerated_once(monkeypatch):
    final, _ = run_graph(monkeypatch, [True], grounding_plan=[False, True])
    assert final["generation_attempts"] == 2
    assert final["grounded"] is True


def test_still_ungrounded_answer_is_flagged_with_the_claims(monkeypatch):
    final, _ = run_graph(monkeypatch, [True], grounding_plan=[False, False])
    assert final["grounded"] is False
    assert "Not confirmed by the passages" in final["answer"]
    assert "claim X" in final["answer"]