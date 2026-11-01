import sys

from app.baseline_rag import answer

question = " ".join(sys.argv[1:]) or "How do I declare a path parameter?"
result = answer(question)

print(f"\nQUESTION: {question}\n")
print(result["answer"])
print("\nSOURCES:")
for s in result["sources"]:
    print(f"  [{s['n']}] {s['source']} | {s['section']}")