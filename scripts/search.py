import sys

from app.config import settings
from app.vectorstore import get_vectorstore

query = " ".join(sys.argv[1:]) or "How do I declare a path parameter?"

store = get_vectorstore()
results = store.similarity_search_with_score(query, k=settings.top_k)

print(f"\nQuery: {query}\n")
for doc, distance in results:
    print(f"distance={distance:.3f} | {doc.metadata['source']} | {doc.metadata['section']}")
    print(doc.page_content[:200].replace("\n", " "))
    print("-" * 60)