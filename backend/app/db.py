"""Database session creation. Schema changes belong to Alembic."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import database_url


class RegistryUnavailable(Exception):
    """The model metadata store cannot be reached."""


# Bounds for the rate-limit path only: it runs before every public request and must
# never be able to hold a request, or the pool, longer than these.
LIMITER_STATEMENT_TIMEOUT_MS = 500
LIMITER_LOCK_TIMEOUT_MS = 300
LIMITER_POOL_TIMEOUT_SECONDS = 2


@lru_cache
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(database_url(), pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def limiter_session_factory() -> sessionmaker[Session]:
    """Separate small pool with server-side timeouts.

    The rate limit is on the hot path of every public request and contends on one
    shared counter row. Without its own pool a stalled counter update would consume
    the connections the endpoints need; without statement and lock timeouts
    "fail closed" would mean "hang first, then refuse everyone".
    """
    engine = create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_timeout=LIMITER_POOL_TIMEOUT_SECONDS,
    )
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    try:
        with session_factory()() as session:
            yield session
    except (RuntimeError, OSError, ConnectionError) as exc:
        raise RegistryUnavailable() from exc
