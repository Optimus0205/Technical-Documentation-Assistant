import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for p in sorted(Path("evaluation/results").glob("run_*.jsonl")):
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["system"] == "graph" and r.get("grounded") is False:
            print("=" * 70)
            print(p.name, r["id"], "rep", r["rep"])
            print(r["answer"])