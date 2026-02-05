import inspect
import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.testclient import TestClient as StarletteTestClient

from app.auth import get_current_user, hash_password
from app.database import get_db, init_db
from app.models import HealthCheck, User
from app.schemas import UserResponse

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


# Convert healthz failures to 503
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if request.url.path == "/healthz":
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)

    return Response(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=json.dumps({"detail": "Invalid request"}),
        media_type="application/json",
        headers=CACHE_HEADERS,
    )


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
    try:
        if "application/json" not in request.headers.get("content-type", ""):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        body = await request.body()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        data = json.loads(body)

        required = ["username", "password", "first_name", "last_name"]
        if any(k not in data or data[k] in ("", None) for k in required):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        if not isinstance(data["first_name"], str) or not isinstance(data["last_name"], str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        if not isinstance(data["password"], str) or len(data["password"]) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        try:
            username = _email_adapter.validate_python(data["username"])
        except ValidationError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        if db.query(User).filter(func.lower(User.username) == str(username).lower()).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT)

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

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


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
    try:
        if "application/json" not in request.headers.get("content-type", ""):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        body = await request.body()
        if not body:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        data = json.loads(body)

        allowed = {"first_name", "last_name", "password"}
        if set(data.keys()) - allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        if "first_name" in data:
            if not isinstance(data["first_name"], str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            # Reject empty strings and whitespace-only
            if not data["first_name"].strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            current_user.first_name = data["first_name"]

        if "last_name" in data:
            if not isinstance(data["last_name"], str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            # Reject empty strings and whitespace-only
            if not data["last_name"].strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            current_user.last_name = data["last_name"]

        if "password" in data:
            if not isinstance(data["password"], str) or len(data["password"]) < 8:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            # Reject empty strings and whitespace-only
            if not data["password"].strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
            current_user.password = hash_password(data["password"])

        current_user.account_updated = datetime.now(timezone.utc)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)