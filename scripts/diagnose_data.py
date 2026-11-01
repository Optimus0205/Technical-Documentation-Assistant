from pathlib import Path

from app.config import settings
from app.ingestion import load_and_chunk_directory

for p in sorted(Path(settings.data_dir).glob("*.md")):
    t = p.read_text(encoding="utf-8")
    print(f"{p.name}: {t.count('```python')} python blocks, "
          f"{t.count('{*')} unresolved includes")

chunks = load_and_chunk_directory(settings.data_dir)
print("\nTotal chunks:", len(chunks))
print("chunks containing ```      :", sum("```" in c.page_content for c in chunks))
print("chunks containing 'import' :", sum("import " in c.page_content for c in chunks))

for c in chunks:
    if "BaseModel" in c.page_content and c.metadata["source"] == "body.md":
        print("\n--- a body.md chunk mentioning BaseModel ---")
        print(c.metadata["section"])
        print(c.page_content[:400])
        break