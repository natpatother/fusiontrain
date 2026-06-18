"""Create the table (if needed) and load sample documents into the vector store.

Usage:
    python scripts/seed.py
"""
import sys
from pathlib import Path

from pgvector.psycopg import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.embeddings import embed  # noqa: E402

SAMPLE_DOCS = [
    "Fusion Solution Co., Ltd. provides cloud infrastructure and AI solutions "
    "built on Microsoft Azure landing zones.",
    "The Microsoft Teams integration runs as an iFrame app, allowing officers to "
    "chat with the knowledge base directly inside Teams.",
    "Azure Active Directory (Entra ID) handles authentication and single sign-on "
    "for all users accessing the application.",
    "Azure Key Vault stores secrets, connection strings, and API keys; the App "
    "Service reads them via managed identity.",
    "Network Security Groups (NSG) control inbound and outbound traffic to the "
    "Production vNet resources.",
    "System health is monitored with Azure Security Center, Azure Monitor, and "
    "Azure Log Analytics for centralized logging.",
    "Application Insights captures telemetry and performance metrics for the App "
    "Service backend.",
    "Documents and uploaded files are stored in Azure Blob Storage as a common "
    "service shared across the platform.",
    "The chat search feature uses Azure OpenAI text-embedding-3-large (3072 "
    "dimensions) to embed text and PostgreSQL pgvector for similarity search.",
    "Azure AI services in use include the Translator, Language service, and Speech "
    "service for multilingual support.",
    "The PostgreSQL Flexible Server hosts the document_embeddings table with a "
    "VECTOR(3072) column for retrieval-augmented generation.",
    "Retrieval-augmented generation (RAG) retrieves the most relevant documents by "
    "cosine similarity, then asks the chat model to answer using that context.",
]


def main() -> None:
    dim = get_settings().embedding_dim
    print(f"Embedding dimension: {dim}")

    with get_conn() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        # Column size is driven by EMBEDDING_DIM so you can switch models
        # (large=3072, small=1536) without editing code.
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id SERIAL PRIMARY KEY,
                content_text TEXT,
                embedding VECTOR({dim})
            );
            """
        )
        _create_index(conn, dim)

        # Fresh load for a repeatable demo.
        conn.execute("TRUNCATE document_embeddings RESTART IDENTITY;")

        for i, text in enumerate(SAMPLE_DOCS, 1):
            vec = Vector(embed(text))
            conn.execute(
                "INSERT INTO document_embeddings (content_text, embedding) VALUES (%s, %s)",
                (text, vec),
            )
            print(f"  inserted {i}/{len(SAMPLE_DOCS)}")
        conn.commit()

    print(f"Done. Seeded {len(SAMPLE_DOCS)} documents.")


def _create_index(conn, dim: int) -> None:
    """Pick an index matching the dimension.

    pgvector's hnsw on the plain `vector` type supports <= 2000 dims, so:
      * dim <= 2000 -> native HNSW (vector_cosine_ops)
      * dim  > 2000 -> HNSW expression index casting to halfvec (needs pgvector >= 0.7.0)
    Either way the column stays VECTOR(dim). Index creation is best-effort: if the
    server can't build it (e.g. old pgvector), the demo still works via exact KNN.
    """
    if dim <= 2000:
        sql = (
            "CREATE INDEX IF NOT EXISTS document_embeddings_embedding_idx "
            "ON document_embeddings USING hnsw (embedding vector_cosine_ops);"
        )
    else:
        sql = (
            "CREATE INDEX IF NOT EXISTS document_embeddings_embedding_idx "
            f"ON document_embeddings USING hnsw ((embedding::halfvec({dim})) halfvec_cosine_ops);"
        )
    try:
        conn.execute(sql)
        conn.commit()
        print("  index ready")
    except Exception as exc:  # noqa: BLE001 - keep seeding even if index fails
        conn.rollback()
        print(f"  WARNING: skipped index ({exc}); exact KNN will be used")


if __name__ == "__main__":
    main()
