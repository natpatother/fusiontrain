from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question")


class Source(BaseModel):
    id: int
    content_text: str
    score: float  # cosine similarity (1.0 = identical)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class DocumentIn(BaseModel):
    content: str = Field(..., min_length=1, description="Raw text to ingest")


class IngestResponse(BaseModel):
    inserted: int
    ids: list[int]
    total: int  # total rows in the store after ingest


class DocumentSummary(BaseModel):
    id: int
    content_text: str


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentSummary]
