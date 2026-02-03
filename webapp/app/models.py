"""
Database Models - Defines structure of tables in PostgreSQL
"""

from sqlalchemy import Column, String, DateTime, BigInteger, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid


# Table: health_checks - stores each health check request
class HealthCheck(Base):
    __tablename__ = "health_checks"

    check_id = Column(BigInteger, primary_key=True, autoincrement=True)
    check_datetime = Column(DateTime(timezone=True), nullable=False, server_default=text("(NOW() AT TIME ZONE 'UTC')"))

    # Index on check_datetime for query performance
    __table_args__ = (Index('idx_check_datetime', 'check_datetime'),)


# Table: users - stores user account information
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)  # Email address
    password = Column(String(255), nullable=False)  # BCrypt hashed
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    account_created = Column(DateTime(timezone=True), nullable=False, server_default=text("(NOW() AT TIME ZONE 'UTC')"))
    account_updated = Column(DateTime(timezone=True), nullable=False, server_default=text("(NOW() AT TIME ZONE 'UTC')"))
