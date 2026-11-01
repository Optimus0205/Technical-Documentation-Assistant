import sys

from app.config import settings
from app.ingestion import load_and_chunk_directory

source, needle = sys.argv[1], sys.argv[2]
for c in load_and_chunk_directory(settings.data_dir):
    if c.metadata["source"] == source and needle in c.page_content:
        print(c.metadata["section"])
        print("-" * 60)
        print(c.page_content)
        print("=" * 60)