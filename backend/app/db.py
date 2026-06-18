"""Connection pool + pgvector registration for Azure PostgreSQL Flexible Server."""
from contextlib import contextmanager

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from .config import get_settings

_pool: ConnectionPool | None = None


def _configure(conn) -> None:
    # pgvector type adapters must be registered per connection.
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=10,
            configure=_configure,
            open=True,
        )
    return _pool


@contextmanager
def get_conn():
    with get_pool().connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
