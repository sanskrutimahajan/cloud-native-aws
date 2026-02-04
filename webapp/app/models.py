"""
Database Models - Defines structure of tables in PostgreSQL
"""

import uuid
from sqlalchemy import BigInteger, Column, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class HealthCheck(Base):
    __tablename__ = "health_checks"

    check_id = Column(BigInteger, primary_key=True, autoincrement=True)
    check_datetime = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (Index("idx_check_datetime", "check_datetime"),)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    account_created = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    account_updated = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=text("NOW()"),
    )
