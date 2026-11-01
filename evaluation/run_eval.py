import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.baseline_rag import answer as baseline_answer
from app.service import run_query
from app.config import settings

QUESTIONS_FILE = Path("evaluation/questions.json")
RESULTS_DIR = Path("evaluation/results")


def norm(text: str) -> str:
    return text.replace("’", "'").lower()


def is_refusal(text: str) -> bool:
    return "i don't know" in norm(text)[:120]


def run_baseline(question: str) -> dict:
    r = baseline_answer(question)
    return {
        "answer": r["answer"],
        "refused": is_refusal(r["answer"]),
        "sources": [s["source"] for s in r["sources"]],
    }


def run_graph(question: str) -> dict:
    r = run_query(question)
    if r["generation_failed"]:
        raise RuntimeError("generation failed")
    return {
        "answer": r["answer"],
        "refused": r["refused"] or is_refusal(r["answer"]),
        "sources": [s["source"] for s in r["sources"]],
        "grounded": r["grounded"],
        "degraded": r["degraded"],
        "retries": r["stats"]["retries"],
        "llm_calls": r["stats"]["llm_calls"],
        "latency": r["stats"]["latency_seconds"],
        "trace": r["trace"],
    }

OTHER_REFUSAL = ("no mention", "no information", "does not cover", "doesn't cover",
                 "not covered", "does not contain", "not mentioned")


def refuses_in_other_words(text: str) -> bool:
    """A refusal that does not use the exact phrase: says the docs lack the answer, and gives no code."""
    t = norm(text)
    return "```" not in t and any(p in t[:200] for p in OTHER_REFUSAL)


def passed(q: dict, result: dict) -> bool:
    if q["expect"] == "refuse":
        return result["refused"] or refuses_in_other_words(result["answer"])
    if result["refused"]:
        return False
    return any(s.lower() in result["answer"].lower() for s in q["must_include_any"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--pause", type=float, default=8, help="seconds to wait between questions")
    parser.add_argument("--only", default="", help="comma-separated question ids, e.g. q01,q14")
    parser.add_argument("--systems", default="baseline,graph", help="comma-separated: baseline,graph")
    args = parser.parse_args()
    systems = args.systems.split(",")

    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    print(f"Writing {out_path}")

    with out_path.open("a", encoding="utf-8") as out:
        for rep in range(1, args.repeats + 1):
            for q in questions:
                for system, fn in (("baseline", run_baseline), ("graph", run_graph)):
                    if system not in systems:
                        continue
                    start = time.perf_counter()
                    try:
                        result, error = fn(q["question"]), None
                    except Exception as exc:
                        result = {"answer": "", "refused": False, "sources": []}
                        error = f"{type(exc).__name__}: {str(exc)[:150]}"
                    seconds = round(time.perf_counter() - start, 1)
                    row = {
                        "rep": rep, "model": settings.llm_model, "id": q["id"], "system": system, "error": error, **result,
                        "passed": None if error else passed(q, result), "seconds": seconds,
                    }
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    status = "ERROR" if error else ("pass" if row["passed"] else "FAIL")
                    print(f"rep {rep} {q['id']} {system:8} {status:5} {seconds:5.1f}s  {q['question'][:50]}")
                time.sleep(args.pause)


if __name__ == "__main__":
    main()