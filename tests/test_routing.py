from app.config import settings
from app.graph.routing import route_after_generate, route_after_grading, route_after_grounding


def state(**overrides):
    base = {
        "relevant_documents": [],
        "context_sufficient": False,
        "retry_count": 0,
        "generation_failed": False,
        "grounded": None,
        "generation_attempts": 1,
    }
    base.update(overrides)
    return base


def test_good_evidence_goes_to_generate():
    assert route_after_grading(state(relevant_documents=["d"], context_sufficient=True)) == "generate"


def test_partial_evidence_retries_first():
    assert route_after_grading(state(relevant_documents=["d"], retry_count=0)) == "rewrite_query"


def test_partial_evidence_answers_when_retries_exhausted():
    s = state(relevant_documents=["d"], retry_count=settings.max_retries)
    assert route_after_grading(s) == "generate"


def test_no_evidence_retries_then_refuses():
    assert route_after_grading(state(retry_count=0)) == "rewrite_query"
    assert route_after_grading(state(retry_count=settings.max_retries)) == "fallback"


def test_failed_generation_ends_the_graph():
    assert route_after_generate(state(generation_failed=True)) == "end"
    assert route_after_generate(state(generation_failed=False)) == "check_grounding"


def test_ungrounded_answer_is_regenerated_a_bounded_number_of_times():
    allowed = settings.max_regenerations
    assert route_after_grounding(state(grounded=False, generation_attempts=1)) == "generate"
    assert route_after_grounding(state(grounded=False, generation_attempts=allowed + 1)) == "end"


def test_grounded_or_unverified_answers_end():
    assert route_after_grounding(state(grounded=True)) == "end"
    assert route_after_grounding(state(grounded=None)) == "end"