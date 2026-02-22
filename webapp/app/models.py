"""
Database Models - Defines structure of tables in PostgreSQL
"""

import uuid
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

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


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_code = Column(String(6), nullable=False)
    number = Column(String(6), nullable=False)
    title = Column(String(255), nullable=False)
    credit_hours = Column(Integer, nullable=False)
    classification = Column(String(10), nullable=False)  # 'core' or 'elective'
    description = Column(Text, nullable=True)
    prerequisites = Column(String(512), nullable=True)
    has_syllabus = Column(Boolean, nullable=False, default=False)

    date_created = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    date_updated = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationship to syllabus (one-to-one)
    syllabus = relationship("Syllabus", back_populates="course", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("department_code", "number", name="uq_course_dept_number"),
    )


class Syllabus(Base):
    __tablename__ = "syllabi"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, unique=True)
    file_name = Column(String(255), nullable=False)
    s3_bucket_name = Column(String(255), nullable=False)
    s3_object_key = Column(String(1024), nullable=False)
    content_type = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    url = Column(String(2048), nullable=False)

    date_created = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    date_updated = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationship back to course
    course = relationship("Course", back_populates="syllabus")
