import sys

from app.vectorstore import get_vectorstore

query = sys.argv[1]
needle = sys.argv[2]          # text the "right" chunk must contain
store = get_vectorstore()

results = store.similarity_search_with_score(query, k=30)
print(f"Query: {query}\nLooking for a chunk containing: {needle!r}\n")
for rank, (doc, dist) in enumerate(results, start=1):
    hit = "  <-- HERE" if needle in doc.page_content else ""
    print(f"{rank:2d}  {dist:.3f}  {doc.metadata['source']} | {doc.metadata['section'][-50:]}{hit}")