import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
qid, system = sys.argv[1], sys.argv[2]
files = [Path(p) for p in sys.argv[3:]] or sorted(Path("evaluation/results").glob("run_*.jsonl"))
for p in files:
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["id"] == qid and r["system"] == system:
            print("=" * 70)
            print(p.name, "| rep", r["rep"], "| passed:", r["passed"], "| refused:", r["refused"], "| error:", r["error"])
            print(r["answer"])