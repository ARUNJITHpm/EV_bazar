"""Engine and session dependency.

Shared by the web app and by ``workers/`` entrypoints. The poller imports
this module too - same models, different process (STACK.md section 1).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

# Neon drops idle connections silently; without TCP keepalives a long gap
# between queries (the ingest's parse/resolve phase, a quiet worker) leaves the
# next query blocked forever on a dead socket. Harmless for local Postgres.
_connect_args = (
    {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "connect_timeout": 15,
    }
    if _settings.database_url.startswith("postgresql")
    else {}
)

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    echo=_settings.debug,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency. One session per request, always closed."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
