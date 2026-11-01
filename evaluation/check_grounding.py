import argparse
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.graph import nodes
from app.ingestion import load_and_chunk_directory

CASES = [
    {
        "id": "A", "source": "path-params.md", "needle": "item_id: int",
        "body": ("Put the parameter name in curly braces in the path and add a function argument with the same "
                 "name, with a type annotation:\n\n```python\n@app.get(\"/items/{item_id}\")\n"
                 "async def read_item(item_id: int):\n    return {\"item_id\": item_id}\n```\n\n"),
        "correct": "Here `item_id` is declared as an `int` [1].",
        "planted": [
            ("contradiction", "Here `item_id` is declared as a `str`, and FastAPI rejects any value that is not a string [1]."),
            ("outside_knowledge", "Here `item_id` is declared as an `int`. This works because FastAPI is built on Starlette and Pydantic [1]."),
            ("fabricated", "Here `item_id` is declared as an `int`. FastAPI also writes every path parameter value to an access log file automatically [1]."),
        ],
    },
    {
        "id": "B", "source": "body.md", "needle": "undefined behavior",
        "body": "Sending a body with a `GET` request is supported by FastAPI, but only for very complex or extreme use cases.",
        "correct": " The behaviour of a `GET` request with a body is undefined in the specifications [1].",
        "planted": [
            ("contradiction", " The behaviour of a `GET` request with a body is fully defined in the specifications, so it is recommended for every endpoint [1]."),
            ("contradiction", " FastAPI does not support a body on `GET` requests at all [1]."),
            ("outside_knowledge", " Browsers' `fetch` API refuses to send a body with a `GET` request [1]."),
        ],
    },
    {
        "id": "C", "source": "path-params.md", "needle": "{file_path:path}",
        "body": "Declare the parameter with the `:path` convertor, for example `/files/{file_path:path}`.",
        "correct": " The parameter is named `file_path`, and `:path` tells FastAPI that it should match any path [1].",
        "planted": [
            ("contradiction", " Use `:str` instead of `:path`, because `:str` matches any path including slashes [1]."),
            ("fabricated", " The `:path` convertor needs the `starlette-paths` plugin to be installed first [1]."),
        ],
    },
    {
        "id": "D", "source": "handling-errors.md", "needle": "exc.body",
        "body": ("Register an exception handler for `RequestValidationError`. The exception carries the `body` it "
                 "received, and the handler can return it together with `exc.errors()` in a `JSONResponse`."),
        "correct": " In the example the handler returns status code 422 [1].",
        "planted": [
            ("contradiction", " In the example the handler returns status code 400 [1]."),
            ("contradiction", " The handler must be declared with `def`, because `async def` handlers cannot receive a `RequestValidationError` [1]."),
        ],
    },
]


def check(doc, answer):
    user_msg = f"Passages:\n\n{nodes._format_passages([doc])}\n\nAnswer to verify:\n{answer}"
    return nodes._call(nodes.GroundingCheck, [("system", nodes.GROUNDING_PROMPT), ("human", user_msg)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--pause", type=float, default=3)
    args = parser.parse_args()

    chunks = load_and_chunk_directory(settings.data_dir)
    located = {}
    for case in CASES:
        chunk = next((c for c in chunks if c.metadata["source"] == case["source"]
                      and case["needle"] in c.page_content), None)
        if chunk is None:
            print(f"Case {case['id']}: NO chunk in {case['source']} contains {case['needle']!r}: skipped")
            continue
        located[case["id"]] = chunk
        print(f"Case {case['id']}: using chunk '{chunk.metadata['section'][-60:]}'")

    rows = []
    out_path = Path("evaluation/results") / f"grounding_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as out:
        for rep in range(1, args.repeats + 1):
            for case in CASES:
                if case["id"] not in located:
                    continue
                variants = [("control", case["correct"])] + case["planted"]
                for kind, tail in variants:
                    result, error = check(located[case["id"]], case["body"] + tail)
                    row = {
                        "rep": rep, "case": case["id"], "kind": kind, "tail": tail.strip(), "error": error,
                        "grounded": None if result is None else result.grounded,
                        "claims": [] if result is None else result.unsupported_claims,
                    }
                    rows.append(row)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    verdict = "ERROR" if error else ("flagged" if row["grounded"] is False else "passed ")
                    print(f"rep {rep} case {case['id']} {kind:18} -> {verdict}")
                    time.sleep(args.pause)

    ok = [r for r in rows if not r["error"]]
    controls = [r for r in ok if r["kind"] == "control"]
    plants = [r for r in ok if r["kind"] != "control"]
    false_alarms = [r for r in controls if r["grounded"] is False]
    caught = [r for r in plants if r["grounded"] is False]

    print("\n# Grounding-check evaluation\n")
    print(f"{len(rows)} checks, {len(rows) - len(ok)} excluded because of errors.\n")
    print(f"- Correct answers flagged (false alarms): {len(false_alarms)}/{len(controls)}")
    print(f"- Planted false claims caught: {len(caught)}/{len(plants)}")
    by_kind = defaultdict(lambda: [0, 0])
    for r in plants:
        by_kind[r["kind"]][1] += 1
        by_kind[r["kind"]][0] += r["grounded"] is False
    for kind, (hit, total) in sorted(by_kind.items()):
        print(f"    {kind}: {hit}/{total}")
    print("\n## Missed plants (check said grounded=True)\n")
    for r in plants:
        if r["grounded"] is not False:
            print(f"- case {r['case']} rep {r['rep']} [{r['kind']}]: {r['tail'][:110]!r}")
    print("\n## False alarms (correct answer flagged)\n")
    for r in false_alarms:
        print(f"- case {r['case']} rep {r['rep']}: claims={r['claims']}")


if __name__ == "__main__":
    main()