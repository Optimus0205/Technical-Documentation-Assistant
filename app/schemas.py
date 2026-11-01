from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class QueryRequest(BaseModel):
    question: Question
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"question": "How do I declare a path parameter?"}]}
    )


class Source(BaseModel):
    n: int
    source: str
    section: str
    snippet: str
    distance: float | None = None


class QueryStats(BaseModel):
    retries: int
    llm_calls: int
    latency_seconds: float


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    refused: bool                    # True when no relevant documentation was found
    grounded: bool | None            # None = not verified (refusals, or the check itself failed)
    degraded: bool                   # True if any node failed and the result may be unreliable
    unsupported_claims: list[str]
    sources: list[Source]
    stats: QueryStats
    trace: list[str]


class DocumentInfo(BaseModel):
    source: str
    chunks: int


class DocumentsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    documents: list[DocumentInfo]


class IngestItem(BaseModel):
    name: str
    status: Literal["indexed", "error"]
    chunks: int = 0
    detail: str = ""


class IngestResponse(BaseModel):
    indexed: int
    failed: int
    total_chunks_in_store: int
    items: list[IngestItem]


class FeedbackRequest(BaseModel):
    query_id: str = Field(min_length=32, max_length=32, description="The query_id returned by /query")
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    query_id: str
    rating: str
    message: str