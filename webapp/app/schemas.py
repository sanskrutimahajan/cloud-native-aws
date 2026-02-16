"""Response schemas."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer


class UserResponse(BaseModel):
    id: UUID
    username: EmailStr
    first_name: str
    last_name: str
    account_created: datetime
    account_updated: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('account_created', 'account_updated')
    def serialize_datetime(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()


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
