"""
Database Connection - Connects to PostgreSQL using environment variables
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

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
        from app.models import HealthCheck, User
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
