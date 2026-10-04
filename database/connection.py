"""Database connection, engine configuration, and session management."""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Tuple, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Retrieve and normalize DATABASE_URL for SQLAlchemy and psycopg v3."""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Default placeholder pointing to PostgreSQL
        url = "postgresql+psycopg://postgres:postgres@localhost:5432/tracker_db"

    # Normalize Render or standard postgres URLs to postgresql+psycopg
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url and "+pg8000" not in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


def create_db_engine(url: Optional[str] = None):
    """Create SQLAlchemy engine with appropriate pooling options."""
    db_url = url or get_database_url()

    # SQLite vs PostgreSQL specific settings
    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 3},
    )


# Global engine and sessionmaker
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit and rollback."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Database transaction rolled back due to error")
        raise
    finally:
        session.close()


def init_db(engine_instance=None) -> None:
    """Create all database tables if they do not already exist."""
    target_engine = engine_instance or engine
    Base.metadata.create_all(bind=target_engine)
    logger.info("Database tables initialized successfully")


def check_connection(engine_instance=None) -> Tuple[bool, str]:
    """Check whether database connection is active and healthy."""
    target_engine = engine_instance or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connected successfully."
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        return False, str(e)
