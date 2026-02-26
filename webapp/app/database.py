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
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
