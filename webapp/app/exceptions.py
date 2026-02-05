"""Standardized error responses per Swagger spec"""

from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.responses import JSONResponse


# Custom exception that bypasses HTTPException's "detail" wrapper
class APIException(Exception):
    def __init__(self, error_type: str, message: str, status_code: int, headers: dict = None):
        self.error_type = error_type
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}
        super().__init__(self.message)


# Build standard error JSON response
def create_error_response(request: Request, error_type: str, message: str, status_code: int, headers: dict = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path)
        },
        headers=headers or {}
    )


# 400 Bad Request
def validation_error_response(request: Request, message: str = "Validation error"):
    return create_error_response(request, "Validation Error", message, status.HTTP_400_BAD_REQUEST)


# 409 Conflict
def conflict_error_response(request: Request, message: str = "A user with this email address already exists"):
    return create_error_response(request, "Conflict", message, status.HTTP_409_CONFLICT)


# 415 Unsupported Media Type
def unsupported_media_type_response(request: Request, message: str = "Content-Type must be application/json"):
    return create_error_response(request, "Unsupported Media Type", message, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
