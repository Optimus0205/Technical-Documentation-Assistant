import logging
import re
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    HTTPException,
    Response
)

from app.config import settings
from app.ingest_service import (
    IngestError, delete_document, fetch_url, index_document, name_from_url,
    prepare_text, safe_filename, validate_extension,
)
from app.schemas import (
    DocumentsResponse, FeedbackRequest, FeedbackResponse, IngestResponse,
    QueryRequest, QueryResponse,
)
from app.service import run_query
from app.storage import feedback_summary, init_db, log_query, query_exists, save_feedback
from app.vectorstore import get_embeddings, get_vectorstore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_api")

MAX_FILES = 10
MAX_URLS = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_embeddings()                     # load the embedding model once, at startup
    logger.info("Embedding model loaded, database ready")
    yield


app = FastAPI(
    title="Technical Documentation Assistant",
    description="Self-corrective RAG over technical documentation (LangGraph).",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    ids = get_vectorstore().get(include=[])["ids"]
    return {"status": "ok", "indexed_chunks": len(ids)}


@app.get("/documents", response_model=DocumentsResponse)
def list_documents():
    data = get_vectorstore().get(include=["metadatas"])
    counts = Counter(m["source"] for m in data["metadatas"])
    docs = [{"source": name, "chunks": n} for name, n in sorted(counts.items())]
    return {"total_documents": len(docs), "total_chunks": sum(counts.values()), "documents": docs}


@app.delete("/documents/{source}")
def remove_document(source: str):
    try:
        name = safe_filename(source)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    removed = delete_document(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No indexed document named '{name}'.")
    return {"deleted": name, "chunks_removed": removed}



@app.post("/ingest", response_model=IngestResponse)
def ingest(
    response: Response,
    files: list[UploadFile] = File(
        default=[],
        description="Upload one or more TXT or supported text files"
    ),
    urls: str = Form(
        default="",
        description="One or more HTTP(S) URLs, separated by spaces, commas or new lines"
    ),
):
    files = [f for f in files if f.filename]

    url_list = [u for u in re.split(r"[\s,]+", urls) if u]

    if not files and not url_list:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one file or URL."
        )

    if len(files) > MAX_FILES or len(url_list) > MAX_URLS:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_FILES} files and {MAX_URLS} URLs per request."
        )

    items: list[dict] = []

    def process(label: str, load):
        try:
            name, text = load()
            n_chunks = index_document(name, text)

            items.append({
                "name": name,
                "status": "indexed",
                "chunks": n_chunks,
                "detail": ""
            })

        except IngestError as exc:
            items.append({
                "name": label,
                "status": "error",
                "chunks": 0,
                "detail": str(exc)
            })

        except Exception:
            logger.exception("Unexpected error while ingesting %s", label)

            items.append({
                "name": label,
                "status": "error",
                "chunks": 0,
                "detail": "Unexpected server error"
            })

    def from_upload(f: UploadFile):
        name = safe_filename(f.filename)
        validate_extension(name)

        data = f.file.read(settings.max_upload_bytes + 1)

        if len(data) > settings.max_upload_bytes:
            raise IngestError("The file is larger than the 1 MB limit")

        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise IngestError("The file is not valid UTF-8 text")

        return prepare_text(name, text)

    def from_url(u: str):
        final_url, content_type, text = fetch_url(u)
        return prepare_text(name_from_url(final_url, content_type), text)

    for f in files:
        process(f.filename, lambda f=f: from_upload(f))

    for u in url_list:
        process(u, lambda u=u: from_url(u))

    indexed = sum(
        1 for i in items if i["status"] == "indexed"
    )

    if indexed == 0:
        response.status_code = 422

    return {
        "indexed": indexed,
        "failed": len(items) - indexed,
        "total_chunks_in_store": get_vectorstore()._collection.count(),
        "items": items,
    }


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if not get_vectorstore().get(limit=1, include=[])["ids"]:
        raise HTTPException(status_code=503, detail="The document index is empty. Ingest documents first.")

    try:
        result = run_query(request.question)
    except Exception:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail="Internal error while answering the question.")

    if result["generation_failed"]:
        raise HTTPException(
            status_code=503,
            detail="The language model could not generate an answer right now. Please retry shortly.",
        )
    try:
        log_query(result["query_id"], request.question, result)    # so /feedback can reference it
    except Exception:
        logger.exception("Could not log the query")                # never fail an answer over logging
    return result


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(body: FeedbackRequest):
    if not query_exists(body.query_id):
        raise HTTPException(status_code=404, detail="Unknown query_id. Use the query_id returned by /query.")
    save_feedback(body.query_id, body.rating, body.comment)
    return {"query_id": body.query_id, "rating": body.rating, "message": "Feedback recorded. Thank you!"}


@app.get("/feedback/summary")
def feedback_overview():
    return feedback_summary()