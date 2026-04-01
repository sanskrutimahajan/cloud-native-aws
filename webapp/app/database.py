"""
Database Connection - Connects to PostgreSQL using environment variables
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# pool_pre_ping: reconnects if DB restarts, connect_timeout: 3 sec max wait
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    connect_args={"connect_timeout": 3}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()  # Base class for all models


# Returns a database session, auto-closes after request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Creates tables on startup, skips if DB is down
def init_db():
    try:
        from app.models import Course, HealthCheck, Syllabus, User
        Base.metadata.create_all(bind=engine)
        _migrate()
        logger.info("Database tables created/migrated successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)


def _migrate():
    """Add any missing columns to existing tables (safe to run on every startup)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_expiry TIMESTAMPTZ",
    ]
    with engine.begin() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Migration skipped: {e}")
