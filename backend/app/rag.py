"""Retrieval-augmented generation over the document_embeddings table."""
from pgvector.psycopg import Vector

from .config import get_settings
from .db import get_conn
from .embeddings import embed, chat
from .schemas import Source


def retrieve(query: str, top_k: int | None = None) -> list[Source]:
    """Return the top_k most similar documents using cosine distance (<=>)."""
    settings = get_settings()
    k = top_k or settings.top_k
    query_vec = Vector(embed(query))

    # The column is always VECTOR(dim). For dim > 2000 the ANN index is built on a
    # halfvec cast, so the query must cast the same way to use it; for dim <= 2000 the
    # native index matches the plain operator. Either way the result is correct.
    if settings.embedding_dim > 2000:
        d = settings.embedding_dim
        dist = f"(embedding::halfvec({d}) <=> %s::halfvec({d}))"
    else:
        dist = "(embedding <=> %s)"

    sql = f"""
        SELECT id,
               content_text,
               1 - {dist} AS score
        FROM document_embeddings
        ORDER BY {dist}
        LIMIT %s
    """

    with get_conn() as conn:
        rows = conn.execute(sql, (query_vec, query_vec, k)).fetchall()

    return [Source(id=r[0], content_text=r[1], score=float(r[2])) for r in rows]


def answer(query: str) -> tuple[str, list[Source]]:
    sources = retrieve(query)
    if not sources:
        return ("I don't have any documents to answer that yet.", [])
    context = "\n\n---\n\n".join(
        f"[{i + 1}] {s.content_text}" for i, s in enumerate(sources)
    )
    reply = chat(query, context)
    return reply, sources
