
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import json

from app.database import get_db, init_db
from app.models import HealthCheck, User
from app.schemas import UserResponse
from app.auth import hash_password, get_current_user

# Initialize FastAPI app with Swagger disabled
app = FastAPI(
    title="Cloud-Native Web Application",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)

# Headers to prevent caching of responses
CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff"
}


# Runs when server starts - creates database tables
@app.on_event("startup")
async def startup_event():
    init_db()


@app.api_route("/healthz", methods=["GET"])
async def health_check(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if body or request.query_params:
        return Response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=json.dumps({"detail": "Health check does not accept payload or query parameters"}),
            media_type="application/json",
            headers=CACHE_HEADERS
        )

    try:
        db.add(HealthCheck())
        db.commit()
        return Response(status_code=status.HTTP_200_OK, headers=CACHE_HEADERS)
    except Exception:
        db.rollback()
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=json.dumps({"detail": "Database connection failed"}),
            media_type="application/json",
            headers=CACHE_HEADERS
        )


@app.api_route("/healthz", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def health_check_method_not_allowed():
    return Response(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        content=json.dumps({"detail": "Method not allowed. Use GET for health check"}),
        media_type="application/json",
        headers=CACHE_HEADERS
    )


@app.post("/v1/user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, response: Response, db: Session = Depends(get_db)):
    """Create User - Returns 201 with user data, 400/409/415 for errors"""
    try:
        # Check Content-Type header
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                              detail="Content-Type must be application/json")

        body = await request.body()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body is required")

        data = json.loads(body)

        # Validate required fields
        missing_fields = [field for field in ["username", "password", "first_name", "last_name"]
                         if field not in data or not data[field]]
        if missing_fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                              detail=f"Missing required fields: {', '.join(missing_fields)}")

        # Validate email format
        username = data["username"]
        if "@" not in username or "." not in username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format")

        # Validate password min 8 characters
        if len(data["password"]) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                              detail="Password must be at least 8 characters")

        # Check for duplicate username (409 Conflict)
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                              detail="User with this email already exists")

        # Create user with hashed password
        new_user = User(
            username=username,
            password=hash_password(data["password"]),
            first_name=data["first_name"],
            last_name=data["last_name"]
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        response.headers["Location"] = "/v1/user/self"
        return new_user

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON format")
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")


@app.get("/v1/user/self", response_model=UserResponse)
async def get_user_info(current_user: User = Depends(get_current_user)):
    """Get User Info - Returns authenticated user's data (requires Basic Auth)"""
    return current_user


@app.put("/v1/user/self", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update User - Only allows first_name, last_name, password (requires Basic Auth)"""
    try:
        body = await request.body()
        if not body:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        # Check Content-Type header
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                              detail="Content-Type must be application/json")

        data = json.loads(body)

        # Reject non-allowed fields
        allowed_fields = {"first_name", "last_name", "password"}
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                              detail=f"Cannot update fields: {', '.join(invalid_fields)}")

        # Update fields
        if data.get("first_name"):
            current_user.first_name = data["first_name"]
        if data.get("last_name"):
            current_user.last_name = data["last_name"]
        if data.get("password"):
            current_user.password = hash_password(data["password"])

        current_user.account_updated = datetime.now(timezone.utc)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON format")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")
