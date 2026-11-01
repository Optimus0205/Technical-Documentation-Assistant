import json
import sys
from pathlib import Path

results_dir = Path("evaluation/results")
paths = [Path(p) for p in sys.argv[1:]] or [sorted(results_dir.glob("run_*.jsonl"))[-1]]
questions = {q["id"]: q for q in json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))}

rows = []
for p in paths:
    rows += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

errors = [r for r in rows if r["error"]]
degraded = [r for r in rows if not r["error"] and r.get("degraded")]
ok = [r for r in rows if not r["error"] and not r.get("degraded")]


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}% ({a}/{b})" if b else "n/a"


def mean(xs: list) -> str:
    return f"{sum(xs) / len(xs):.1f}" if xs else "n/a"


def summary(system: str, unseen_only: bool) -> tuple[int, str, str, str]:
    sel = [r for r in ok if r["system"] == system
           and not (unseen_only and questions[r["id"]].get("dev"))]
    ans = [r for r in sel if questions[r["id"]]["expect"] == "answer"]
    ref = [r for r in sel if questions[r["id"]]["expect"] == "refuse"]
    return (len({r["id"] for r in sel}),
            pct(sum(r["passed"] for r in ans), len(ans)),
            pct(sum(r["refused"] for r in ans), len(ans)),
            pct(sum(r["passed"] for r in ref), len(ref)))


out = [f"# Evaluation report ({', '.join(p.name for p in paths)})", "",
       f"{len(rows)} runs: {len(ok)} counted, {len(errors)} excluded (API errors), "
       f"{len(degraded)} excluded (degraded: a node failed, so the result is unreliable).", "",
       "| System | Questions | Answerable: correct | Answerable: falsely refused | Unanswerable: correctly refused |",
       "|---|---|---|---|---|"]
for unseen in (False, True):
    for system in ("baseline", "graph"):
        n, a, b, c = summary(system, unseen)
        label = f"{system} ({'unseen questions only' if unseen else 'all questions'})"
        out.append(f"| {label} | {n} | {a} | {b} | {c} |")

graph = [r for r in ok if r["system"] == "graph"]
base = [r for r in ok if r["system"] == "baseline"]
answered = [r for r in graph if not r["refused"]]
out += ["", "## Cost and behaviour (counted runs only)", "",
        f"- Baseline: 1 LLM call, mean latency {mean([r['seconds'] for r in base])} s",
        f"- Graph: mean {mean([r['llm_calls'] for r in graph])} LLM calls, "
        f"mean latency {mean([r['latency'] for r in graph])} s, "
        f"mean retries {mean([r['retries'] for r in graph])}",
        f"- Graph answers verified by the grounding check: "
        f"grounded=True {sum(r['grounded'] is True for r in answered)}, "
        f"False {sum(r['grounded'] is False for r in answered)}, "
        f"None {sum(r['grounded'] is None for r in answered)} (of {len(answered)} answered)",
        "", "## Per question (passes / counted runs)", "",
        "| id | kind | question | baseline | graph |", "|---|---|---|---|---|"]
for qid, q in questions.items():
    cells = []
    for system in ("baseline", "graph"):
        sel = [r for r in ok if r["id"] == qid and r["system"] == system]
        cells.append(f"{sum(r['passed'] for r in sel)}/{len(sel)}" if sel else "-")
    kind = ("refuse" if q["expect"] == "refuse" else "answer") + (" (dev)" if q.get("dev") else "")
    out.append(f"| {qid} | {kind} | {q['question'][:55]} | {cells[0]} | {cells[1]} |")

failures = [r for r in ok if not r["passed"]]
out += ["", "## Failures (read these: the keyword check is crude)", ""]
for r in failures:
    out.append(f"- rep {r['rep']} {r['id']} {r['system']}: {r['answer'][:200].replace(chr(10), ' ')!r}")
if degraded:
    out += ["", "## Excluded as degraded", ""] + [
        f"- rep {r['rep']} {r['id']} graph ({r['seconds']} s, refused={r['refused']})" for r in degraded]
if errors:
    out += ["", "## Excluded because of API errors", ""] + [
        f"- rep {r['rep']} {r['id']} {r['system']}" for r in errors]

text = "\n".join(out)
target = paths[0].with_suffix(".md") if len(paths) == 1 else results_dir / "report_merged.md"
target.write_text(text, encoding="utf-8")
print(text)