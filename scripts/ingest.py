import argparse

from app.config import settings
from app.ingestion import load_and_chunk_directory
from app.vectorstore import get_vectorstore

parser = argparse.ArgumentParser()
parser.add_argument("--reset", action="store_true", help="delete the collection first")
args = parser.parse_args()

store = get_vectorstore()
if args.reset:
    store.delete_collection()
    store = get_vectorstore()
    print("Collection reset.")

chunks = load_and_chunk_directory(settings.data_dir)
ids = [c.metadata["chunk_id"] for c in chunks]
store.add_documents(chunks, ids=ids)

print(f"Indexed {len(chunks)} chunks.")
print(f"Total in store: {store._collection.count()}")