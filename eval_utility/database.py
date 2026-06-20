"""EU-7 — Database engine and session management.

Supports SQLite (tests/local) and Postgres (deploy) via DATABASE_URL.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

# Module-level engine and session factory (lazily initialized)
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url

        # SQLite-specific: enable foreign keys
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

        # Enable foreign keys for SQLite
        if url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    """Dependency for FastAPI: yields a session, commits on success, rollbacks on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for standalone session usage (non-FastAPI)."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables (for tests/local dev)."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables (for tests)."""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


def reset_engine() -> None:
    """Reset the module-level engine and session factory.

    Use this in tests to switch between different test databases.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def check_db_connectivity() -> bool:
    """Check database connectivity for health endpoint."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
