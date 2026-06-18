-- Run this on your Azure PostgreSQL Flexible Server.
-- Ensure "vector" is in the server parameter: azure.extensions
--
-- The embedding dimension is a psql variable. Pass it to match your model:
--   text-embedding-3-large -> 3072   text-embedding-3-small -> 1536
-- Example:
--   psql "<conn string>" -v dim=1536 -f init_db.sql
-- If you don't pass -v dim=..., it defaults to 3072.
\if :{?dim}
\else
  \set dim 3072
\endif

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    content_text TEXT,
    embedding VECTOR(:dim)
);

-- INDEX (optional). pgvector's hnsw/ivfflat on `vector` supports <= 2000 dims.
--   * dim <= 2000 (e.g. 1536):
--       CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops);
--   * dim  > 2000 (e.g. 3072): keep VECTOR(dim) and index a halfvec cast (pgvector >= 0.7.0):
--       CREATE INDEX ON document_embeddings
--           USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);
--       -- then query: ORDER BY embedding::halfvec(3072) <=> $1::halfvec(3072)
-- The seed script (scripts/seed.py) creates the matching index automatically.
