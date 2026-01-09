"""
Database connection and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from pathlib import Path
import os

from app.config import settings
from app.db.models import Base

# Get the backend directory (parent of app/)
BACKEND_DIR = Path(__file__).parent.parent.parent.absolute()

# Create data directory if it doesn't exist
db_dir = BACKEND_DIR / "data" / "db"
db_dir.mkdir(parents=True, exist_ok=True)

# Create absolute database path
db_file = db_dir / "voice_agent.db"
DATABASE_URL = f"sqlite:///{db_file}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session() -> Session:
    """Get a database session (non-context manager version)."""
    return SessionLocal()

