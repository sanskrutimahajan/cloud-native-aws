"""
Response Schemas - Defines what data is returned to the client
"""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer


# User response format - password is NEVER returned
class UserResponse(BaseModel):
    id: UUID
    username: EmailStr
    first_name: str
    last_name: str
    account_created: datetime
    account_updated: datetime

    model_config = ConfigDict(from_attributes=True)  # Allows conversion from SQLAlchemy model

    # Force timestamps to display as UTC (+00:00)
    @field_serializer('account_created', 'account_updated')
    def serialize_datetime(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
