import inspect
import json
import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, Response, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.testclient import TestClient as StarletteTestClient

from app.auth import get_current_user, hash_password
from app.database import get_db, init_db
from app.models import HealthCheck, User
from app.schemas import UserResponse
from app.exceptions import (
    APIException,
    validation_error_response,
    conflict_error_response,
    unsupported_media_type_response,
    create_error_response
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Patch Starlette TestClient.get to accept `content=` (tests call client.get(..., content=...))
if "content" not in inspect.signature(StarletteTestClient.get).parameters:
    _orig_get = StarletteTestClient.get

    def _patched_get(self, url, **kwargs):
        if "content" in kwargs:
            content = kwargs.pop("content")
            return self.request("GET", url, content=content, **kwargs)
        return _orig_get(self, url, **kwargs)

    StarletteTestClient.get = _patched_get

app = FastAPI(
    title="Cloud-Native Web Application",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
}

_email_adapter = TypeAdapter(EmailStr)


# Create tables on startup
@app.on_event("startup")
async def startup_event():
    init_db()


# Handle APIException (no "detail" wrapper)
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return create_error_response(
        request=request,
        error_type=exc.error_type,
        message=exc.message,
        status_code=exc.status_code,
        headers=exc.headers
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if request.url.path == "/healthz":
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)

    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return validation_error_response(request, "Invalid request")


# Health check endpoint
@app.get("/healthz")
async def health_check(request: Request):
    # Reject query params
    if request.query_params:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)

    # Reject request body (ANY body content)
    body = await request.body()
    if body:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)

    # Verify DB connectivity and insert one record
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            db.add(HealthCheck())
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
            except Exception:
                pass

        return Response(status_code=status.HTTP_200_OK, headers=CACHE_HEADERS)

    except Exception:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)


# Health check unsupported methods
@app.api_route("/healthz", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def healthz_method_not_allowed():
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers=CACHE_HEADERS)


# Create user
@app.post("/v1/user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, response: Response, db: Session = Depends(get_db)):
    # Check Content-Type
    if "application/json" not in request.headers.get("content-type", ""):
        return unsupported_media_type_response(request)

    # Check body exists
    body = await request.body()
    if not body:
        return validation_error_response(request, "Request body is required")

    # Parse JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return validation_error_response(request, "Invalid JSON format")

    # Check required fields
    required = ["username", "password", "first_name", "last_name"]
    missing_fields = [field for field in required if field not in data or data[field] in ("", None)]
    if missing_fields:
        return validation_error_response(request, f"Missing required fields: {', '.join(missing_fields)}")

    # Validate data types
    if not isinstance(data["first_name"], str) or not isinstance(data["last_name"], str):
        return validation_error_response(request, "First name and last name must be strings")
    if not data["first_name"].strip() or not data["last_name"].strip():
        return validation_error_response(request, "First name and last name cannot be empty or whitespace")

    # Validate password
    if not isinstance(data["password"], str):
        return validation_error_response(request, "Password must be a string")
    if not data["password"].strip():
        return validation_error_response(request, "Password cannot be empty or whitespace")
    if len(data["password"]) < 8:
        return validation_error_response(request, "Password must be at least 8 characters")

    # Validate email
    try:
        username = _email_adapter.validate_python(data["username"])
    except ValidationError:
        return validation_error_response(request, "Username must be a valid email address")

    # Check for duplicate
    if db.query(User).filter(func.lower(User.username) == str(username).lower()).first():
        return conflict_error_response(request)

    # Create user
    try:
        user = User(
            username=str(username),
            password=hash_password(data["password"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        response.headers["Location"] = "/v1/user/self"
        return user

    except IntegrityError:
        db.rollback()
        return conflict_error_response(request)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating user: {e}", exc_info=True)
        return validation_error_response(request, "Failed to create user")


# Get authenticated user
@app.get("/v1/user/self", response_model=UserResponse)
async def get_user_self(current_user: User = Depends(get_current_user)):
    return current_user


# Update authenticated user
@app.put("/v1/user/self", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check Content-Type
    if "application/json" not in request.headers.get("content-type", ""):
        return unsupported_media_type_response(request)

    # Get body
    body = await request.body()
    if not body:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Parse JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return validation_error_response(request, "Invalid JSON format")

    # Check for disallowed fields
    allowed = {"first_name", "last_name", "password"}
    disallowed = set(data.keys()) - allowed
    if disallowed:
        return validation_error_response(
            request,
            f"Field '{list(disallowed)[0]}' cannot be updated"
        )

    # Update first_name
    if "first_name" in data:
        if not isinstance(data["first_name"], str):
            return validation_error_response(request, "First name must be a string")
        if not data["first_name"].strip():
            return validation_error_response(request, "First name cannot be empty")
        current_user.first_name = data["first_name"]

    # Update last_name
    if "last_name" in data:
        if not isinstance(data["last_name"], str):
            return validation_error_response(request, "Last name must be a string")
        if not data["last_name"].strip():
            return validation_error_response(request, "Last name cannot be empty")
        current_user.last_name = data["last_name"]

    # Update password
    if "password" in data:
        if not isinstance(data["password"], str):
            return validation_error_response(request, "Password must be a string")
        if not data["password"].strip():
            return validation_error_response(request, "Password cannot be empty or whitespace")
        if len(data["password"]) < 8:
            return validation_error_response(request, "Password must be at least 8 characters")
        current_user.password = hash_password(data["password"])

    # Save changes
    try:
        current_user.account_updated = datetime.now(timezone.utc)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating user: {e}", exc_info=True)
        return validation_error_response(request, "Failed to update user")
