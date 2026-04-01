"""Response schemas."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer


def _serialize_dt(dt: datetime) -> str:
    """Ensure datetime is UTC and ISO-formatted."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class UserResponse(BaseModel):
    id: UUID
    username: EmailStr
    first_name: str
    last_name: str
    email_verified: bool
    account_created: datetime
    account_updated: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('account_created', 'account_updated')
    def serialize_datetime(self, dt: datetime) -> str:
        return _serialize_dt(dt)


class NetworkInterface(BaseModel):
    private_ip: str
    public_ip: Optional[str] = None
    network: str


class MetadataResponse(BaseModel):
    cloud_platform: str
    instance_id: str
    region: str
    machine_type: str
    network_interfaces: List[NetworkInterface]


class CourseResponse(BaseModel):
    id: UUID
    department_code: str
    number: str
    title: str
    credit_hours: int
    classification: str
    description: Optional[str] = None
    prerequisites: Optional[str] = None
    has_syllabus: bool
    date_created: datetime
    date_updated: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('date_created', 'date_updated')
    def serialize_datetime(self, dt: datetime) -> str:
        return _serialize_dt(dt)


class SyllabusResponse(BaseModel):
    id: UUID
    course_id: UUID
    file_name: str
    s3_bucket_name: str
    s3_object_key: str
    content_type: str
    file_size: int
    url: str
    date_created: datetime
    date_updated: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('date_created', 'date_updated')
    def serialize_datetime(self, dt: datetime) -> str:
        return _serialize_dt(dt)
