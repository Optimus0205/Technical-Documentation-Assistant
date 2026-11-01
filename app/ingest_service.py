import ipaddress
import re
import socket
import threading
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from app.config import settings
from app.ingestion import chunk_text, clean_markdown
from app.vectorstore import get_vectorstore

ALLOWED_EXTENSIONS = {".md", ".txt", ".html", ".htm"}
_lock = threading.Lock()


class IngestError(ValueError):
    """A problem with the user's input (not a server bug)."""


def safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name           # drop any directory part: ../../x.md -> x.md
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    if not base:
        raise IngestError("Invalid file name")
    return base[:100]


def validate_extension(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError(f"Unsupported file type '{ext or 'none'}'. Allowed: .md, .txt, .html")
    return ext


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return markdownify(str(main), heading_style="ATX")


def prepare_text(filename: str, raw: str) -> tuple[str, str]:
    """Validate and normalise one document. Returns (stored_name, text)."""
    name = safe_filename(filename)
    ext = validate_extension(name)
    if ext in {".html", ".htm"}:
        raw = html_to_markdown(raw)
        name = Path(name).stem + ".md"
    if not raw.strip():
        raise IngestError("The document is empty")
    return name, raw


def index_document(name: str, text: str) -> int:
    """Chunk, embed and store one document, replacing any earlier version. Returns chunk count."""
    chunks = chunk_text(clean_markdown(text), source=name)
    if not chunks:
        raise IngestError("No usable text found (too short after cleaning)")
    with _lock:
        collection = get_vectorstore()._collection
        collection.delete(where={"source": name})          # replace the old version: no stale chunks
        get_vectorstore().add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
        (Path(settings.data_dir) / name).write_text(text, encoding="utf-8")   # so `ingest --reset` keeps it
    return len(chunks)


def delete_document(name: str) -> int:
    with _lock:
        collection = get_vectorstore()._collection
        ids = collection.get(where={"source": name}, include=[])["ids"]
        if not ids:
            return 0
        collection.delete(ids=ids)
        (Path(settings.data_dir) / name).unlink(missing_ok=True)
    return len(ids)


# ---------- URL fetching with SSRF protection ----------

def _check_public_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise IngestError("Only http(s) URLs are allowed")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise IngestError(f"Cannot resolve host '{parsed.hostname}'")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise IngestError("URL points to a non-public address (blocked)")


def fetch_url(url: str) -> tuple[str, str, str]:
    """Download a page. Returns (final_url, content_type, text)."""
    current = url
    for _ in range(4):                                     # at most 3 redirects
        _check_public_host(current)                        # re-checked at every hop
        try:
            with requests.get(current, timeout=15, stream=True, allow_redirects=False,
                              headers={"User-Agent": "doc-assistant/0.1"}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    current = urljoin(current, r.headers.get("Location", ""))
                    continue
                if r.status_code != 200:
                    raise IngestError(f"The server answered HTTP {r.status_code}")
                body, size = [], 0
                for part in r.iter_content(8192):
                    size += len(part)
                    if size > settings.max_upload_bytes:
                        raise IngestError("The page is larger than the 1 MB limit")
                    body.append(part)
                text = b"".join(body).decode("utf-8", errors="replace")
                return current, r.headers.get("Content-Type", ""), text
        except requests.RequestException as exc:
            raise IngestError(f"Could not download the URL ({type(exc).__name__})")
    raise IngestError("Too many redirects")


def name_from_url(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    last = Path(parsed.path).name or "index"
    name = f"{parsed.hostname}_{last}"       # host prefix: a web page can never overwrite a corpus file
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        name += ".html" if "html" in content_type.lower() else ".txt"
    return name