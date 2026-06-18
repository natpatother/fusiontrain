import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import ingest
from .config import get_settings
from .db import close_pool, get_conn
from .rag import answer
from .schemas import (
    ChatRequest,
    ChatResponse,
    DocumentIn,
    DocumentList,
    DocumentSummary,
    IngestResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="RAG Chat Demo", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "database": db_ok}


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    try:
        reply, sources = answer(req.message)
    except Exception as exc:  # surface a clean error to the UI
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatResponse(answer=reply, sources=sources)


@app.post("/api/documents", response_model=IngestResponse)
def add_document_endpoint(doc: DocumentIn):
    """Ingest pasted text: chunk -> embed -> store."""
    try:
        ids = ingest.add_document(doc.content)
        total = ingest.count_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not ids:
        raise HTTPException(status_code=400, detail="No text to ingest.")
    return IngestResponse(inserted=len(ids), ids=ids, total=total)


@app.post("/api/documents/upload", response_model=IngestResponse)
async def upload_document_endpoint(file: UploadFile = File(...)):
    """Ingest an uploaded text file (.txt/.md/.csv/etc.)."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty or not text.")
    try:
        ids = ingest.add_document(text)
        total = ingest.count_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return IngestResponse(inserted=len(ids), ids=ids, total=total)


@app.get("/api/documents", response_model=DocumentList)
def list_documents_endpoint():
    try:
        docs = ingest.list_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return DocumentList(
        total=len(docs),
        documents=[DocumentSummary(**d) for d in docs],
    )


@app.delete("/api/documents/{doc_id}")
def delete_document_endpoint(doc_id: int):
    try:
        ok = ingest.delete_document(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": doc_id}


# Serve the built React app from the same App Service, if present.
# (Build the frontend with `npm run build` and copy frontend/dist -> backend/app/static)
# Mounted last so /api/* routes take precedence.
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
