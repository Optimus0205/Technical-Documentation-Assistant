from collections import Counter
from app.config import settings
from app.ingestion import load_and_chunk_directory

chunks = load_and_chunk_directory(settings.data_dir)
print("Total chunks:", len(chunks))
print(Counter(c.metadata["source"] for c in chunks))
sizes = [len(c.page_content) for c in chunks]
print(f"Chunk size min/avg/max: {min(sizes)}/{sum(sizes)//len(sizes)}/{max(sizes)}")

for c in chunks[:3]:
    print("-" * 60)
    print(c.metadata["source"], "|", c.metadata["section"])
    print(c.page_content)