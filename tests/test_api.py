import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.storage import init_db, log_query


class FakeStore:
    def __init__(self, ids):
        self._ids = ids

    def get(self, limit=None, include=None):
        return {"ids": self._ids[:limit] if limit else self._ids}


def fake_result(**overrides):
    base = {
        "query_id": "a" * 32,
        "answer": "Use it [1].",
        "refused": False,
        "grounded": True,
        "degraded": False,
        "unsupported_claims": [],
        "sources": [{"n": 1, "source": "s.md", "section": "S", "snippet": "x", "distance": 0.5}],
        "stats": {"retries": 0, "llm_calls": 4, "latency_seconds": 1.0},
        "trace": ["analyze_query: ok"],
        "generation_failed": False,
    }
    base.update(overrides)
    return base


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "feedback_db", str(tmp_path / "feedback.db"))   # throwaway database
    init_db()
    monkeypatch.setattr(main, "get_vectorstore", lambda: FakeStore(["id1"]))      # "index is not empty"
    return TestClient(main.app)       # no `with`: the startup hook (model loading) is skipped


def test_too_short_question_is_rejected_with_422(client):
    assert client.post("/query", json={"question": "hi"}).status_code == 422


def test_query_answers_and_is_logged_for_feedback(client, monkeypatch):
    monkeypatch.setattr(main, "run_query", lambda q: fake_result())
    r = client.post("/query", json={"question": "How do I declare a path parameter?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Use it [1]."
    assert body["sources"][0]["source"] == "s.md"
    fb = client.post("/feedback", json={"query_id": body["query_id"], "rating": "up"})
    assert fb.status_code == 200


def test_feedback_for_unknown_query_is_404(client):
    r = client.post("/feedback", json={"query_id": "0" * 32, "rating": "up"})
    assert r.status_code == 404


def test_feedback_with_invalid_rating_is_422(client):
    r = client.post("/feedback", json={"query_id": "a" * 32, "rating": "maybe"})
    assert r.status_code == 422


def test_empty_index_returns_503(client, monkeypatch):
    monkeypatch.setattr(main, "get_vectorstore", lambda: FakeStore([]))
    r = client.post("/query", json={"question": "How do I declare a path parameter?"})
    assert r.status_code == 503


def test_failed_generation_returns_503(client, monkeypatch):
    monkeypatch.setattr(main, "run_query", lambda q: fake_result(generation_failed=True))
    r = client.post("/query", json={"question": "How do I declare a path parameter?"})
    assert r.status_code == 503


def test_unexpected_error_returns_500_without_leaking_details(client, monkeypatch):
    def boom(question):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(main, "run_query", boom)
    r = client.post("/query", json={"question": "How do I declare a path parameter?"})
    assert r.status_code == 500
    assert "secret" not in r.text


def test_second_rating_replaces_the_first(client):
    log_query("b" * 32, "a question", fake_result(query_id="b" * 32))
    for rating in ("up", "down"):
        r = client.post("/feedback", json={"query_id": "b" * 32, "rating": rating})
        assert r.status_code == 200
    summary = client.get("/feedback/summary").json()
    assert summary["up"] == 0 and summary["down"] == 1