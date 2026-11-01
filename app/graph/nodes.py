import re

from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from app.graph.state import GraphState
from app.llm import get_llm, text_of
from app.vectorstore import get_vectorstore
from app.config import settings


# ---------- Structured output schemas ----------

class QueryAnalysis(BaseModel):
    query_type: Literal["conceptual", "how_to", "troubleshooting", "api_reference"] = Field(
        description="conceptual = what/why explanation; how_to = steps or code to achieve something; "
                    "troubleshooting = an error or unexpected behaviour; api_reference = exact name/signature/option"
    )
    search_query: str = Field(
        description="The question rewritten as a search query: keep the user's technical terms, "
                    "add the documentation's likely vocabulary, no filler words."
    )


class ChunkGrade(BaseModel):
    chunk: int = Field(description="The chunk number as shown in the prompt")
    relevant: bool = Field(description="True only if the chunk helps answer the question directly")
    reason: str = Field(description="One short sentence explaining the verdict")


class BatchGrade(BaseModel):
    grades: list[ChunkGrade]
    sufficient: bool = Field(
        description="True only if the chunks marked relevant TOGETHER contain enough information "
                    "to answer the question well, not just part of it"
    )


class QueryRewrite(BaseModel):
    search_query: str = Field(description="A new search query that differs from all previous ones")


# ---------- Prompts ----------

ANALYZE_PROMPT = """You prepare user questions for searching a documentation corpus about FastAPI
(topics: first steps, path parameters, query parameters, request body, handling errors).
ALWAYS respond by calling the function, even if the question seems unrelated to FastAPI.
Never answer the question yourself.
Rules for search_query:
- Keep the user's technical terms.
- Do NOT add the word "FastAPI": every document is about FastAPI, so it only adds noise.
- Add the vocabulary the documentation itself likely uses (e.g. "request body" for "send JSON").
- If the question is unrelated to FastAPI, return it unchanged."""

GRADE_PROMPT = """You grade retrieved documentation chunks for a question.
A chunk is RELEVANT only if it contains information that helps answer the question directly.
A chunk that is merely about a related topic, or shares keywords but does not help answer, is NOT relevant.
Return one grade for every chunk number given.
Then judge SUFFICIENCY: do the chunks you marked relevant, taken together, contain enough
to answer the question well? If they only cover a small part or a different aspect, answer false."""

REWRITE_PROMPT = """The previous searches did not retrieve chunks that fully answer the question.
Write a NEW search query for the documentation. It must differ meaningfully from the
queries already tried (use different terms, the docs' own vocabulary, or code identifiers such as
decorators, class names or function arguments). Do NOT add the word "FastAPI".
Use the feedback to see what was missing."""


# ---------- Helpers ----------

def _call(schema, messages):
    """Ask the LLM for structured output. Returns (result, error_text).

    Models sometimes fail to produce valid structured output (e.g. they refuse in plain text).
    We never let that crash the graph: each node decides what to do when result is None."""
    try:
        return get_llm().with_structured_output(schema).invoke(messages), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def _format_chunks(docs: list[Document]) -> str:
    return "\n\n".join(
        f"[Chunk {i}] ({d.metadata['source']} | {d.metadata['section']})\n{d.page_content}"
        for i, d in enumerate(docs, start=1)
    )


# ---------- Nodes ----------

def analyze_query(state: GraphState) -> dict:
    result, error = _call(QueryAnalysis, [("system", ANALYZE_PROMPT), ("human", state["question"])])
    if result is None:
        q = state["question"]
        return {
            "query_type": "unknown",
            "search_query": q,
            "tried_queries": [q],
            "trace": [f"analyze_query: FAILED ({error}); using the original question"],
        }
    return {
        "query_type": result.query_type,
        "search_query": result.search_query,
        "tried_queries": [result.search_query],
        "trace": [f"analyze_query: type={result.query_type}, search_query={result.search_query!r}"],
    }


def retrieve(state: GraphState) -> dict:
    k = state["top_k"]
    results = get_vectorstore().similarity_search_with_score(state["search_query"], k=k)
    docs = []
    for doc, distance in results:
        doc.metadata["distance"] = round(float(distance), 3)
        docs.append(doc)
    return {
        "documents": docs,
        "trace": [f"retrieve: k={k}, query={state['search_query']!r}, best_distance={docs[0].metadata['distance']}"],
    }


def grade_documents(state: GraphState) -> dict:
    docs = state["documents"]
    user_msg = f"Question: {state['question']}\n\n{_format_chunks(docs)}"
    result, error = _call(BatchGrade, [("system", GRADE_PROMPT), ("human", user_msg)])

    if result is None:   # fail closed: if we cannot grade, we cannot trust the chunks
        return {
            "relevant_documents": [],
            "context_sufficient": False,
            "grading_feedback": "grading failed",
            "trace": [f"grade_documents: FAILED ({error}); treating all chunks as not relevant"],
        }

    verdicts = {g.chunk: g for g in result.grades}
    relevant, trace_lines, rejected_reasons = [], [], []
    for i, doc in enumerate(docs, start=1):
        grade = verdicts.get(i)
        is_relevant = bool(grade and grade.relevant)    # a missing grade counts as NOT relevant
        reason = grade.reason if grade else "no grade returned"
        label = f"{doc.metadata['source']} | {doc.metadata['section'][-40:]}"
        trace_lines.append(f"    chunk {i} [{'KEEP' if is_relevant else 'drop'}] {label}: {reason}")
        if is_relevant:
            relevant.append(doc)
        else:
            rejected_reasons.append(reason)

    sufficient = bool(relevant) and result.sufficient
    if sufficient:
        feedback = ""
    elif relevant:
        feedback = ("Some chunks were relevant but together they did not fully answer the question. "
                    "Rejected chunks: " + "; ".join(rejected_reasons[:4]))
    else:
        feedback = "; ".join(rejected_reasons[:5])

    summary = f"grade_documents: {len(relevant)}/{len(docs)} relevant, sufficient={sufficient}"
    return {
        "relevant_documents": relevant,
        "context_sufficient": sufficient,
        "grading_feedback": feedback,
        "trace": [summary] + trace_lines,
    }


def rewrite_query(state: GraphState) -> dict:
    user_msg = (
        f"Original question: {state['question']}\n"
        f"Question type: {state['query_type']}\n"
        f"Queries already tried: {state['tried_queries']}\n"
        f"Why the retrieved chunks were not enough: {state['grading_feedback']}"
    )
    result, error = _call(QueryRewrite, [("system", REWRITE_PROMPT), ("human", user_msg)])
    n = state["retry_count"] + 1          # always count the retry, so the loop must end
    new_k = state["top_k"] + 4

    if result is None:                    # keep the old query but still widen the search
        return {
            "retry_count": n,
            "top_k": new_k,
            "trace": [f"rewrite_query: FAILED ({error}); keeping query, k grows to {new_k}"],
        }
    return {
        "retry_count": n,
        "top_k": new_k,
        "search_query": result.search_query,
        "tried_queries": [result.search_query],
        "trace": [f"rewrite_query: retry={n}, k grows to {new_k}, new query={result.search_query!r}"],
    }


# ---------- Generation and grounding check ----------

class GroundingCheck(BaseModel):
    grounded: bool = Field(
        description="True only if every factual claim, technical detail and code example in the "
                    "answer is supported by the passages"
    )
    unsupported_claims: list[str] = Field(
        description="Short descriptions of claims or code NOT supported by the passages. Empty if grounded."
    )


GENERATE_PROMPT = """You are a technical documentation assistant. Answer the question using ONLY the numbered passages provided.
Rules:
- Cite passages like [1] or [2][3] right after the claims they support. Use only the passage numbers given.
- Do not add facts, headers, status codes, or code that are not in the passages, even if you know them to be true.
- Copy code exactly as written in the passages, including indentation, inside fenced code blocks.
- Be concise and direct.
- If the passages only partly answer the question, answer the part they support and say clearly what the documentation provided does not cover.
- Do not put text in quotation marks as if quoting the documentation. Paraphrase in your own words; only code is copied verbatim.
- Use square brackets only for passage citations like [1]."""

GROUNDING_PROMPT = """You verify whether an answer is supported by the documentation passages it was written from.
Check every factual claim, technical detail and code example in the answer.
- A claim is SUPPORTED only if the passages state it or clearly show it.
- A claim that is true in the real world but does not appear in the passages is UNSUPPORTED.
- Ignore wording, formatting, citation markers like [1], and statements that the documentation does not cover something.
Return grounded=true only if there are no unsupported claims."""

NOTE_UNVERIFIED = "\n\n_Note: some details in this answer may go beyond what the retrieved documentation states._"


def _format_passages(docs: list[Document]) -> str:
    return "\n\n".join(
        f"[{i}] ({d.metadata['source']} | {d.metadata['section']})\n{d.page_content}"
        for i, d in enumerate(docs, start=1)
    )


def _normalize_citations(text: str) -> str:
    """Some models emit full-width brackets, e.g. 【1】. Convert them to [1]."""
    return re.sub(r"【\s*(\d+)\s*】", r"[\1]", text)


def _cited_numbers(text: str, n_docs: int) -> list[int]:
    """Find passage numbers cited in the answer, ignoring anything inside code."""
    prose = re.sub(r"```.*?```", "", text, flags=re.S)     # fenced code: items[0] is not a citation
    prose = re.sub(r"`[^`]*`", "", prose)                   # inline code
    found: set[int] = set()
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", prose):
        found.update(int(x) for x in re.split(r"\s*,\s*", group))
    return sorted(i for i in found if 1 <= i <= n_docs)


def generate(state: GraphState) -> dict:
    docs = state["relevant_documents"]
    attempt = state["generation_attempts"] + 1

    user_msg = f"Passages:\n\n{_format_passages(docs)}\n\nQuestion: {state['question']}"
    if not state["context_sufficient"]:
        user_msg += ("\n\nNOTE: the passages may answer only part of the question. "
                     "Answer what they support and say what they do not cover.")
    if state["unsupported_claims"]:
        user_msg += ("\n\nYour previous answer contained claims that the passages do not support:\n- "
                     + "\n- ".join(state["unsupported_claims"])
                     + "\nWrite the answer again WITHOUT those claims.")

    try:
        response = get_llm().invoke([("system", GENERATE_PROMPT), ("human", user_msg)])
        text = _normalize_citations(text_of(response.content)).strip()
        if not text:
            raise ValueError("empty answer")
    except Exception as exc:
        return {
            "answer": "Sorry, I could not generate an answer because the language model request failed. "
                      "Please try again.",
            "sources": [],
            "generation_attempts": attempt,
            "generation_failed": True,
            "trace": [f"generate: FAILED ({type(exc).__name__}: {str(exc)[:100]})"],
        }

    cited = _cited_numbers(text, len(docs))
    numbers = cited or list(range(1, len(docs) + 1))      # no valid citations: show everything we gave it
    sources = [
        {"n": i, "source": docs[i - 1].metadata["source"], "section": docs[i - 1].metadata["section"]}
        for i in numbers
    ]
    label = "first draft" if attempt == 1 else f"regeneration {attempt - 1}"
    partial = "" if state["context_sufficient"] else ", partial evidence"
    return {
        "answer": text,
        "sources": sources,
        "generation_attempts": attempt,
        "generation_failed": False,
        "trace": [f"generate: {label}, {len(docs)} passages given, cited={cited}{partial}"],
    }


def check_grounding(state: GraphState) -> dict:
    docs = state["relevant_documents"]
    user_msg = f"Passages:\n\n{_format_passages(docs)}\n\nAnswer to verify:\n{state['answer']}"
    result, error = _call(GroundingCheck, [("system", GROUNDING_PROMPT), ("human", user_msg)])

    if result is None:    # the check itself failed: return the answer, but do NOT claim it was verified
        return {
            "grounded": None,
            "unsupported_claims": [],
            "trace": [f"check_grounding: FAILED ({error}); answer not verified"],
        }

    claims = [] if result.grounded else result.unsupported_claims
    lines = [f"check_grounding: grounded={result.grounded}"] + [f"    unsupported: {c}" for c in claims]
    update: dict = {"grounded": result.grounded, "unsupported_claims": claims}
    if not result.grounded and state["generation_attempts"] > settings.max_regenerations:
        note = ("\n\n_Note: this answer may go beyond what the retrieved documentation states. "
                "Not confirmed by the passages:_\n" + "\n".join(f"- _{c}_" for c in claims))
        update["answer"] = state["answer"] + note
        lines.append("    no regenerations left: answer flagged as partly unverified")
    update["trace"] = lines
    return update


def fallback(state: GraphState) -> dict:
    return {
        "answer": "I don't know based on the documentation.",
        "sources": [],
        "trace": ["fallback: retries exhausted, no relevant documents, refusing"],
    }