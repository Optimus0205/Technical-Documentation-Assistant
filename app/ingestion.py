import hashlib
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
MIN_CHUNK_CHARS = 60  # drop fragments too small to carry meaning

size_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
    strip_whitespace=False,   # keep indentation of code at chunk starts
)


def clean_markdown(text: str) -> str:
    """Remove docs-site-only syntax that means nothing to a reader or an LLM."""
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.S)            # front matter
    text = re.sub(r"\{\*.*?\*\}", "", text)                          # unresolved code includes
    text = re.sub(r"[ \t]*\{\s*#[\w-]+\s*\}", "", text)              # { #anchor } tags
    text = re.sub(r"</?div[^>]*>", "", text)                         # <div class="termy"> etc.
    text = re.sub(r"</?(?:font|span)[^>]*>", "", text)               # terminal colour tags like <font color=...>
    text = re.sub(r"<dfn[^>]*>(.*?)</dfn>", r"\1", text)             # <dfn title=...>word</dfn>
    # Admonitions: "/// note | Title" -> "Note: Title", "/// tip" -> "Tip:", closing "///" removed
    text = re.sub(r"^///[ \t]*(\w+)[ \t]*\|[ \t]*(.+)$",
                  lambda m: f"{m.group(1).capitalize()}: {m.group(2)}", text, flags=re.M)
    text = re.sub(r"^///[ \t]*(\w+)[ \t]*$",
                  lambda m: f"{m.group(1).capitalize()}:", text, flags=re.M)
    text = re.sub(r"^///[ \t]*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_file(path: Path) -> str:
    return clean_markdown(path.read_text(encoding="utf-8"))


HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


def split_by_headers(text: str) -> list[Document]:
    """Split Markdown into sections at #, ## and ### headings.

    Unlike MarkdownHeaderTextSplitter this keeps every line exactly as written
    (indentation matters in code), and it ignores '#' lines inside ``` fences,
    which are Python comments, not headings.
    """
    sections: list[Document] = []
    meta: dict[str, str] = {}
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        content = "\n".join(buf).strip("\n")   # trim blank lines only, not indentation
        if content.strip():
            sections.append(Document(page_content=content, metadata=dict(meta)))
        buf.clear()

    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match:
            flush()                                  # finish the previous section
            level = len(match.group(1))
            meta[f"h{level}"] = match.group(2)
            for deeper in range(level + 1, 4):       # a new h2 clears the old h3
                meta.pop(f"h{deeper}", None)
        buf.append(line)
    flush()
    return sections


def chunk_text(text: str, source: str) -> list[Document]:
    sections = split_by_headers(text)
    chunks = size_splitter.split_documents(sections)
    chunks = [c for c in chunks if len(c.page_content.strip()) >= MIN_CHUNK_CHARS]

    for i, chunk in enumerate(chunks):
        heading = " > ".join(
            chunk.metadata[h] for h in ("h1", "h2", "h3") if h in chunk.metadata
        )
        chunk.metadata["source"] = source
        chunk.metadata["section"] = heading or "(no heading)"
        digest = hashlib.md5(f"{source}:{i}:{chunk.page_content}".encode()).hexdigest()
        chunk.metadata["chunk_id"] = digest
    return chunks


def load_and_chunk_directory(data_dir: str) -> list[Document]:
    all_chunks: list[Document] = []
    for path in sorted(p for p in Path(data_dir).iterdir() if p.suffix.lower() in (".md", ".txt")):
        all_chunks.extend(chunk_text(load_file(path), source=path.name))
    return all_chunks