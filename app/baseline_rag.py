from langchain_core.documents import Document

from app.config import settings
from app.llm import get_llm, text_of
from app.vectorstore import get_vectorstore

SYSTEM_PROMPT = """You are a technical documentation assistant for FastAPI.
Answer the question using ONLY the numbered context passages provided.
- Cite the passages you used like [1] or [2][3], right after the claims they support.
- If the passages do not contain the answer, say you don't know based on the documentation.
- Copy code exactly as it appears in the passages."""


def format_context(docs: list[Document]) -> str:
    """Number each chunk so the LLM can cite it, and show where it came from."""
    parts = []
    for i, d in enumerate(docs, start=1):
        header = f"[{i}] (source: {d.metadata['source']} | {d.metadata['section']})"
        parts.append(f"{header}\n{d.page_content}")
    return "\n\n".join(parts)


def answer(question: str) -> dict:
    store = get_vectorstore()
    docs = store.similarity_search(question, k=settings.top_k)

    user_message = f"Context:\n{format_context(docs)}\n\nQuestion: {question}"
    response = get_llm().invoke([("system", SYSTEM_PROMPT), ("human", user_message)])

    return {
        "answer": text_of(response.content),
        "sources": [
            {"n": i, "source": d.metadata["source"], "section": d.metadata["section"]}
            for i, d in enumerate(docs, start=1)
        ],
    }