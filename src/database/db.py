"""Database initialization and session management."""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from src.database.models import Base
from src.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Database configuration
DATABASE_URL = settings.get_database_url

logger.info(f"Database driver: {settings.db_driver}")
logger.info(f"Database host: {settings.db_host if settings.db_driver == 'postgresql' else 'local'}")

# Create engine with appropriate configuration for each database type
if "sqlite" in DATABASE_URL:
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.db_echo_enabled,
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        echo=settings.db_echo_enabled,
        pool_pre_ping=True,  # Test connections before using them
        pool_size=10,
        max_overflow=20,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get database session.
    
    Yields:
        SQLAlchemy session for database operations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    logger.info(f"Initializing database: {DATABASE_URL}")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_all_tables():
    """Drop all tables (for testing/cleanup)."""
    logger.warning("Dropping all database tables")
    Base.metadata.drop_all(bind=engine)
