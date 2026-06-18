"""Document ingestion: chunk -> embed -> store in document_embeddings.

Keeps the required schema exactly (id, content_text, embedding VECTOR(dim)) — each
chunk becomes one row. The column dimension follows EMBEDDING_DIM.
"""
import re

from pgvector.psycopg import Vector

from .config import get_settings
from .db import get_conn
from .embeddings import embed


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """Split text into ~max_chars chunks, preferring paragraph boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = f"{current}\n{para}".strip()
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(para) <= max_chars:
            current = para
        else:
            # Hard-split an oversized paragraph with overlap.
            step = max(1, max_chars - overlap)
            for i in range(0, len(para), step):
                chunks.append(para[i : i + max_chars])
    if current:
        chunks.append(current)
    return chunks


def _ensure_table(conn) -> None:
    dim = get_settings().embedding_dim
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS document_embeddings (
            id SERIAL PRIMARY KEY,
            content_text TEXT,
            embedding VECTOR({dim})
        );
        """
    )


def add_document(text: str) -> list[int]:
    """Chunk, embed, and insert a document. Returns the new row ids."""
    chunks = chunk_text(text)
    if not chunks:
        return []
    ids: list[int] = []
    with get_conn() as conn:
        _ensure_table(conn)
        for chunk in chunks:
            vec = Vector(embed(chunk))
            row = conn.execute(
                "INSERT INTO document_embeddings (content_text, embedding) "
                "VALUES (%s, %s) RETURNING id",
                (chunk, vec),
            ).fetchone()
            ids.append(row[0])
        conn.commit()
    return ids


def list_documents(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, content_text FROM document_embeddings ORDER BY id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [{"id": r[0], "content_text": r[1] or ""} for r in rows]


def delete_document(doc_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM document_embeddings WHERE id = %s", (doc_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def count_documents() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM document_embeddings").fetchone()
    return int(row[0])
