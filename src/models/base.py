"""
Database Models Base Module
=========================

This module provides the base SQLAlchemy configuration for all models.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from contextlib import contextmanager

from ..utils.config import get_settings
from ..database import Base
from ..utils.logging import core_logger  # Import core_logger

logger = core_logger()
settings = get_settings()

# Create the SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Enable connection ping before use to avoid stale connections
    pool_size=5,  # Start with a small pool size for MVP
    max_overflow=10,  # Allow up to 10 additional connections when pool is full
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session() -> Session:
    """
    Get a database session with automatic commit/rollback and cleanup.
    
    Usage:
        with get_db_session() as session:
            session.query(User).all()
    
    Returns:
        SQLAlchemy session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()

def init_db():
    """
    Initialize the database by creating all tables.
    Should be called at application startup.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized with all tables.") 