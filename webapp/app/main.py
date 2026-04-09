import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import Depends, FastAPI, File, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.database import get_db, init_db
from app.metadata import detect_platform, get_metadata
from app.models import Course, HealthCheck, Syllabus, User
from app.schemas import CourseResponse, MetadataResponse, SyllabusResponse, UserResponse
from app.exceptions import (
    APIException,
    bad_request_response,
    conflict_error_response,
    create_error_response,
    not_found_response,
    unsupported_media_type_response,
    validation_error_response,
)
from app import s3
from app import metrics
from app import sns

#This is main.py
# ──────────────────────────────────────────────
# Logging configuration — writes to file + console
# ──────────────────────────────────────────────
LOG_DIR = "/var/log/webapp"
LOG_FILE = os.path.join(LOG_DIR, "csye6225.log")

# Create log directory if it doesn't exist (for local dev)
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except PermissionError:
    LOG_DIR = "."
    LOG_FILE = "csye6225.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    force=True,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("csye6225")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    init_db()
    detect_platform()
    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="Cloud-Native Web Application",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
}

_email_adapter = TypeAdapter(EmailStr)

DEPT_CODE_RE = re.compile(r"^[A-Z]{2,6}$")
VALID_CLASSIFICATIONS = {"core", "elective"}
COURSE_IMMUTABLE_FIELDS = {"id", "department_code", "number", "has_syllabus", "date_created", "date_updated"}
COURSE_UPDATABLE_FIELDS = {"title", "credit_hours", "classification", "description", "prerequisites"}


# ──────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.warning(
        "API exception on %s %s: %s - %s",
        request.method, request.url.path, exc.error_type, exc.message
    )
    return create_error_response(
        request=request,
        error_type=exc.error_type,
        message=exc.message,
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if request.url.path == "/healthz":
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True
    )
    return validation_error_response(request, "Invalid request")


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.get("/healthz")
async def health_check(request: Request):
    metrics.increment("api.healthz.get.count")
    with metrics.Timer("api.healthz.get.duration"):
        if request.query_params:
            logger.warning("Health check rejected: query parameters are not permitted on GET /healthz")
            return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
        body = await request.body()
        if body:
            logger.warning("Health check rejected: request body is not permitted on GET /healthz")
            return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                with metrics.Timer("db.healthz.insert.duration"):
                    db.add(HealthCheck())
                    db.commit()
            except Exception as e:
                logger.error("Health check database write failed: %s", e, exc_info=True)
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
            logger.info("Health check passed — database write verified, application is healthy")
            return Response(status_code=status.HTTP_200_OK, headers=CACHE_HEADERS)
        except Exception as e:
            logger.error("Health check failed — cannot connect to database: %s", e, exc_info=True)
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)


@app.api_route("/healthz", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def healthz_method_not_allowed(request: Request):
    logger.warning(
        "Health check rejected: HTTP %s is not allowed on /healthz; only GET is supported",
        request.method
    )
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers=CACHE_HEADERS)


# ──────────────────────────────────────────────
# Metadata
# ──────────────────────────────────────────────
@app.get("/v1/metadata", response_model=MetadataResponse)
async def get_instance_metadata(request: Request):
    metrics.increment("api.metadata.get.count")
    with metrics.Timer("api.metadata.get.duration"):
        if request.query_params:
            logger.warning("Metadata request rejected: query parameters are not permitted on GET /v1/metadata")
            return create_error_response(request, "Bad Request", "Query parameters are not allowed",
                                         status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
        body = await request.body()
        if body:
            logger.warning("Metadata request rejected: request body is not permitted on GET /v1/metadata")
            return create_error_response(request, "Bad Request", "Request body is not allowed",
                                         status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
        try:
            metadata = get_metadata()
        except Exception:
            logger.error("Failed to retrieve instance metadata", exc_info=True)
            return create_error_response(request, "Service Unavailable",
                                         "Unable to retrieve instance metadata. The application may not be running on a supported cloud platform.",
                                         status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)
        if metadata is None:
            logger.warning("Instance metadata unavailable — not running on a supported cloud platform")
            return create_error_response(request, "Service Unavailable",
                                         "Unable to retrieve instance metadata. The application may not be running on a supported cloud platform.",
                                         status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)
        logger.info("Metadata retrieved successfully for platform: %s", metadata.get("cloud_platform"))
        return JSONResponse(content=metadata, headers=CACHE_HEADERS)


@app.api_route("/v1/metadata", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def metadata_method_not_allowed(request: Request):
    logger.warning(
        "Metadata request rejected: HTTP %s is not allowed on /v1/metadata; only GET is supported",
        request.method
    )
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers=CACHE_HEADERS)


# ──────────────────────────────────────────────
# User endpoints
# ──────────────────────────────────────────────
@app.post("/v1/user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, response: Response, db: Session = Depends(get_db)):
    metrics.increment("api.user.post.count")
    with metrics.Timer("api.user.post.duration"):
        logger.info("POST /v1/user — creating new user")
        if "application/json" not in request.headers.get("content-type", ""):
            return unsupported_media_type_response(request)
        body = await request.body()
        if not body:
            return validation_error_response(request, "Request body is required")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return validation_error_response(request, "Invalid JSON format")

        required = ["username", "password", "first_name", "last_name"]
        missing = [f for f in required if f not in data or data[f] in ("", None)]
        if missing:
            return validation_error_response(request, f"Missing required fields: {', '.join(missing)}")
        if not isinstance(data["first_name"], str) or not isinstance(data["last_name"], str):
            return validation_error_response(request, "First name and last name must be strings")
        if not data["first_name"].strip() or not data["last_name"].strip():
            return validation_error_response(request, "First name and last name cannot be empty or whitespace")
        if len(data["first_name"]) > 100:
            return validation_error_response(request, "First name must be 100 characters or fewer")
        if len(data["last_name"]) > 100:
            return validation_error_response(request, "Last name must be 100 characters or fewer")
        if not isinstance(data["password"], str):
            return validation_error_response(request, "Password must be a string")
        if not data["password"].strip():
            return validation_error_response(request, "Password cannot be empty or whitespace")
        if len(data["password"]) < 8:
            return validation_error_response(request, "Password must be at least 8 characters")
        try:
            username = _email_adapter.validate_python(data["username"])
        except ValidationError:
            return validation_error_response(request, "Username must be a valid email address")

        with metrics.Timer("db.user.select.duration"):
            existing = db.query(User).filter(func.lower(User.username) == str(username).lower()).first()
        if existing:
            logger.warning("User creation failed: account with email %s already exists", str(username))
            return conflict_error_response(request)

        try:
            token = str(uuid.uuid4())
            expiry = datetime.now(timezone.utc) + timedelta(minutes=1)
            user = User(
                username=str(username),
                password=hash_password(data["password"]),
                first_name=data["first_name"],
                last_name=data["last_name"],
                email_verified=False,
                verification_token=token,
                token_expiry=expiry,
            )
            with metrics.Timer("db.user.insert.duration"):
                db.add(user)
                db.commit()
                db.refresh(user)
            response.headers["Location"] = "/v1/user/self"
            logger.info("User created successfully: %s", str(username))
            sns.publish_verification_email(str(username), data["first_name"], token)
            return user
        except IntegrityError:
            db.rollback()
            logger.warning("User creation failed: database integrity error for email %s", str(username))
            return conflict_error_response(request)
        except Exception as e:
            db.rollback()
            logger.error("Database error creating user: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to create user")


@app.get("/v1/user/self", response_model=UserResponse)
async def get_user_self(current_user: User = Depends(get_current_user)):
    metrics.increment("api.user.self.get.count")
    with metrics.Timer("api.user.self.get.duration"):
        logger.info("Fetching profile for authenticated user: %s", current_user.username)
        logger.info("User profile retrieved successfully for account: %s", current_user.username)
        return current_user


@app.put("/v1/user/self", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.user.self.put.count")
    with metrics.Timer("api.user.self.put.duration"):
        logger.info("PUT /v1/user/self — user: %s", current_user.username)
        if "application/json" not in request.headers.get("content-type", ""):
            return unsupported_media_type_response(request)
        body = await request.body()
        if not body:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return validation_error_response(request, "Invalid JSON format")

        allowed = {"first_name", "last_name", "password"}
        disallowed = set(data.keys()) - allowed
        if disallowed:
            return bad_request_response(request, f"Field '{list(disallowed)[0]}' cannot be updated")

        if "first_name" in data:
            if not isinstance(data["first_name"], str):
                return validation_error_response(request, "First name must be a string")
            if not data["first_name"].strip():
                return validation_error_response(request, "First name cannot be empty")
            if len(data["first_name"]) > 100:
                return validation_error_response(request, "First name must be 100 characters or fewer")
            current_user.first_name = data["first_name"]
        if "last_name" in data:
            if not isinstance(data["last_name"], str):
                return validation_error_response(request, "Last name must be a string")
            if not data["last_name"].strip():
                return validation_error_response(request, "Last name cannot be empty")
            if len(data["last_name"]) > 100:
                return validation_error_response(request, "Last name must be 100 characters or fewer")
            current_user.last_name = data["last_name"]
        if "password" in data:
            if not isinstance(data["password"], str):
                return validation_error_response(request, "Password must be a string")
            if not data["password"].strip():
                return validation_error_response(request, "Password cannot be empty or whitespace")
            if len(data["password"]) < 8:
                return validation_error_response(request, "Password must be at least 8 characters")
            current_user.password = hash_password(data["password"])

        try:
            current_user.account_updated = datetime.now(timezone.utc)
            with metrics.Timer("db.user.update.duration"):
                db.commit()
            logger.info("User updated successfully: %s", current_user.username)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            db.rollback()
            logger.error("Database error updating user: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to update user")


@app.get("/v1/validateEmail")
async def validate_email(request: Request, db: Session = Depends(get_db)):
    email = request.query_params.get("email")
    token = request.query_params.get("token")

    if not email or not token:
        return bad_request_response(request, "Missing required query parameters: email and token")

    user = db.query(User).filter(func.lower(User.username) == email.lower()).first()
    if not user:
        logger.warning("Email validation failed: no user found for email %s", email)
        return bad_request_response(request, "Invalid or expired verification link")

    if user.email_verified:
        logger.info("Email already verified for: %s", email)
        return JSONResponse(content={"message": "Email already verified"}, headers=CACHE_HEADERS)

    now = datetime.now(timezone.utc)
    expiry = user.token_expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if user.verification_token != token or expiry is None or now > expiry:
        logger.warning("Email validation failed: invalid or expired token for %s", email)
        return bad_request_response(request, "Invalid or expired verification link")

    user.email_verified = True
    user.verification_token = None
    user.token_expiry = None
    try:
        db.commit()
        logger.info("Email verified successfully for: %s", email)
        return JSONResponse(content={"message": "Email verified successfully"}, headers=CACHE_HEADERS)
    except Exception as e:
        db.rollback()
        logger.error("Error verifying email for %s: %s", email, e, exc_info=True)
        return create_error_response(request, "Internal Error", "Failed to verify email",
                                     status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────
# Course helpers
# ──────────────────────────────────────────────
def _validate_course_fields(data: dict, request: Request, is_update: bool = False):
    if is_update:
        immutable_sent = set(data.keys()) & COURSE_IMMUTABLE_FIELDS
        if immutable_sent:
            field = list(immutable_sent)[0]
            return bad_request_response(request, f"Field '{field}' cannot be updated")
        updatable_sent = set(data.keys()) & COURSE_UPDATABLE_FIELDS
        if not updatable_sent:
            return bad_request_response(request, "At least one updatable field must be provided")
        unknown = set(data.keys()) - COURSE_UPDATABLE_FIELDS
        if unknown:
            return bad_request_response(request, f"Unknown field: '{list(unknown)[0]}'")

    if "department_code" in data:
        dc = data["department_code"]
        if not isinstance(dc, str) or not DEPT_CODE_RE.match(dc):
            return validation_error_response(request, "department_code must be 2–6 uppercase letters")
    if "number" in data:
        num = data["number"]
        if not isinstance(num, str) or len(num) < 1 or len(num) > 6:
            return validation_error_response(request, "number must be 1–6 characters")
    if "title" in data:
        t = data["title"]
        if not isinstance(t, str) or len(t) < 1 or len(t) > 255:
            return validation_error_response(request, "title must be 1–255 characters")
    if "credit_hours" in data:
        ch = data["credit_hours"]
        if not isinstance(ch, int) or isinstance(ch, bool) or ch < 1 or ch > 8:
            return validation_error_response(request, "credit_hours must be an integer between 1 and 8")
    if "classification" in data:
        cl = data["classification"]
        if not isinstance(cl, str) or cl not in VALID_CLASSIFICATIONS:
            return validation_error_response(request, "classification must be 'core' or 'elective'")
    if "description" in data and data["description"] is not None:
        d = data["description"]
        if not isinstance(d, str) or len(d) > 2000:
            return validation_error_response(request, "description must be a string of max 2000 characters")
    if "prerequisites" in data and data["prerequisites"] is not None:
        p = data["prerequisites"]
        if not isinstance(p, str) or len(p) > 512:
            return validation_error_response(request, "prerequisites must be a string of max 512 characters")
    return None


# ──────────────────────────────────────────────
# Course CRUD endpoints
# ──────────────────────────────────────────────
@app.get("/v1/courses", response_model=List[CourseResponse])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.courses.get.count")
    with metrics.Timer("api.courses.get.duration"):
        logger.info("GET /v1/courses — user: %s", current_user.username)
        with metrics.Timer("db.courses.select_all.duration"):
            courses = (
                db.query(Course)
                .order_by(Course.department_code.asc(), Course.number.asc())
                .all()
            )
        logger.info("Retrieved %d courses", len(courses))
        return courses


@app.post("/v1/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.courses.post.count")
    with metrics.Timer("api.courses.post.duration"):
        logger.info("POST /v1/courses — user: %s", current_user.username)
        ct = request.headers.get("content-type", "")
        if "application/json" not in ct:
            return unsupported_media_type_response(request)
        body = await request.body()
        if not body:
            return validation_error_response(request, "Request body is required")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return validation_error_response(request, "Invalid JSON format")

        required = ["department_code", "number", "title", "credit_hours", "classification"]
        missing = [f for f in required if f not in data or data[f] is None]
        if missing:
            return validation_error_response(request, f"Missing required fields: {', '.join(missing)}")

        server_fields = {"id", "has_syllabus", "date_created", "date_updated"}
        sent_server = set(data.keys()) & server_fields
        if sent_server:
            return validation_error_response(request, f"Field '{list(sent_server)[0]}' must not be set by the client")

        err = _validate_course_fields(data, request, is_update=False)
        if err:
            return err

        with metrics.Timer("db.courses.select.duration"):
            exists = (
                db.query(Course)
                .filter(Course.department_code == data["department_code"], Course.number == data["number"])
                .first()
            )
        if exists:
            logger.warning("Course creation failed: course %s %s already exists", data["department_code"], data["number"])
            return conflict_error_response(request, f"Course {data['department_code']} {data['number']} already exists")

        try:
            course = Course(
                department_code=data["department_code"],
                number=data["number"],
                title=data["title"],
                credit_hours=data["credit_hours"],
                classification=data["classification"],
                description=data.get("description"),
                prerequisites=data.get("prerequisites"),
                has_syllabus=False,
            )
            with metrics.Timer("db.courses.insert.duration"):
                db.add(course)
                db.commit()
                db.refresh(course)
            response.headers["Location"] = f"/v1/courses/{course.id}"
            logger.info("Course created: %s %s — %s", course.department_code, course.number, course.title)
            return course
        except IntegrityError:
            db.rollback()
            return conflict_error_response(request, f"Course {data['department_code']} {data['number']} already exists")
        except Exception as e:
            db.rollback()
            logger.error("Error creating course: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to create course")


@app.get("/v1/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.courses.id.get.count")
    with metrics.Timer("api.courses.id.get.duration"):
        logger.info("Fetching course with ID %s for user: %s", course_id, current_user.username)
        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.warning("Course not found: no course exists with ID %s", course_id)
            return not_found_response(request, "Course not found")
        logger.info("Course retrieved successfully: %s %s — '%s'", course.department_code, course.number, course.title)
        return course


@app.put("/v1/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.courses.id.put.count")
    with metrics.Timer("api.courses.id.put.duration"):
        logger.info("PUT /v1/courses/%s — user: %s", course_id, current_user.username)
        ct = request.headers.get("content-type", "")
        if "application/json" not in ct:
            return unsupported_media_type_response(request)
        body = await request.body()
        if not body:
            return bad_request_response(request, "Request body is required")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return validation_error_response(request, "Invalid JSON format")
        if not data:
            return bad_request_response(request, "At least one updatable field must be provided")

        err = _validate_course_fields(data, request, is_update=True)
        if err:
            return err

        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.warning("Course update failed: no course exists with ID %s", course_id)
            return not_found_response(request, "Course not found")

        updated_fields = []
        if "title" in data:
            course.title = data["title"]
            updated_fields.append("title")
        if "credit_hours" in data:
            course.credit_hours = data["credit_hours"]
            updated_fields.append("credit_hours")
        if "classification" in data:
            course.classification = data["classification"]
            updated_fields.append("classification")
        if "description" in data:
            course.description = data["description"]
            updated_fields.append("description")
        if "prerequisites" in data:
            course.prerequisites = data["prerequisites"]
            updated_fields.append("prerequisites")

        try:
            course.date_updated = datetime.now(timezone.utc)
            with metrics.Timer("db.courses.update.duration"):
                db.commit()
                db.refresh(course)
            logger.info(
                "Course %s %s updated successfully; modified fields: %s",
                course.department_code, course.number, ", ".join(updated_fields)
            )
            return course
        except Exception as e:
            db.rollback()
            logger.error("Error updating course: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to update course")


@app.delete("/v1/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.courses.id.delete.count")
    with metrics.Timer("api.courses.id.delete.duration"):
        logger.info("DELETE /v1/courses/%s — user: %s", course_id, current_user.username)
        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.warning("Course deletion failed: no course exists with ID %s", course_id)
            return not_found_response(request, "Course not found")

        if course.has_syllabus:
            logger.warning("Course deletion rejected: course %s %s has an attached syllabus that must be deleted first", course.department_code, course.number)
            return conflict_error_response(
                request,
                f"Cannot delete course {course.department_code} {course.number} because it has a syllabus attached. Delete the syllabus first.",
            )

        try:
            with metrics.Timer("db.courses.delete.duration"):
                db.delete(course)
                db.commit()
            logger.info(
                "Course %s %s deleted successfully by user: %s",
                course.department_code, course.number, current_user.username
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            db.rollback()
            logger.error("Error deleting course: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to delete course")


# ──────────────────────────────────────────────
# Syllabus endpoints
# ──────────────────────────────────────────────
@app.get("/v1/courses/{course_id}/syllabus", response_model=SyllabusResponse)
async def get_syllabus(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.syllabus.get.count")
    with metrics.Timer("api.syllabus.get.duration"):
        logger.info("Fetching syllabus for course ID %s requested by user: %s", course_id, current_user.username)
        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            logger.warning("Syllabus fetch failed: no course exists with ID %s", course_id)
            return not_found_response(request, "Course not found")
        with metrics.Timer("db.syllabus.select.duration"):
            syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
        if not syllabus:
            logger.warning("Syllabus fetch failed: course %s %s has no syllabus on record", course.department_code, course.number)
            return not_found_response(request, "No syllabus found for this course")
        logger.info(
            "Syllabus '%s' retrieved successfully for course %s %s",
            syllabus.file_name, course.department_code, course.number
        )
        return syllabus


@app.post("/v1/courses/{course_id}/syllabus", response_model=SyllabusResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus(
    course_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(None),
):
    metrics.increment("api.syllabus.post.count")
    with metrics.Timer("api.syllabus.post.duration"):
        logger.info("POST /v1/courses/%s/syllabus — user: %s", course_id, current_user.username)

        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return not_found_response(request, "Course not found")
        if course.has_syllabus:
            logger.warning(
                "Syllabus upload rejected: course %s %s already has a syllabus on record; delete it before uploading a new one",
                course.department_code, course.number
            )
            return conflict_error_response(
                request,
                f"Course {course.department_code} {course.number} already has a syllabus. Delete the existing syllabus first.",
            )
        if file is None or file.filename is None or file.filename == "":
            return bad_request_response(request, "A syllabus file must be provided in the 'file' form field")

        content = await file.read()
        if len(content) == 0:
            return bad_request_response(request, "The uploaded file is empty")

        bucket = s3.get_bucket_name()
        obj_key = s3.build_object_key(str(course.id), file.filename)
        content_type = file.content_type or "application/octet-stream"

        try:
            with metrics.Timer("s3.syllabus.upload.duration"):
                s3.upload_file(obj_key, content, content_type)
            logger.info(
                "Syllabus file '%s' (%d bytes, %s) uploaded to S3 bucket '%s' at key: %s",
                file.filename, len(content), content_type, bucket, obj_key
            )
        except Exception as e:
            logger.error("S3 upload failed: %s", e, exc_info=True)
            return create_error_response(request, "Internal Error", "Failed to upload file to storage",
                                         status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            syllabus = Syllabus(
                course_id=course.id,
                file_name=file.filename,
                s3_bucket_name=bucket,
                s3_object_key=obj_key,
                content_type=content_type,
                file_size=len(content),
                url=s3.build_object_url(bucket, obj_key),
            )
            with metrics.Timer("db.syllabus.insert.duration"):
                db.add(syllabus)
                course.has_syllabus = True
                course.date_updated = datetime.now(timezone.utc)
                db.commit()
                db.refresh(syllabus)

            response.headers["Location"] = f"/v1/courses/{course_id}/syllabus"
            logger.info(
                "Syllabus '%s' metadata persisted to database for course %s %s; course marked as has_syllabus=True",
                file.filename, course.department_code, course.number
            )
            return syllabus
        except Exception as e:
            db.rollback()
            try:
                s3.delete_file(obj_key)
            except Exception:
                pass
            logger.error("Error saving syllabus metadata: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to save syllabus metadata")


@app.delete("/v1/courses/{course_id}/syllabus", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syllabus(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metrics.increment("api.syllabus.delete.count")
    with metrics.Timer("api.syllabus.delete.duration"):
        logger.info("DELETE /v1/courses/%s/syllabus — user: %s", course_id, current_user.username)

        with metrics.Timer("db.courses.select_by_id.duration"):
            course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return not_found_response(request, "Course not found")
        with metrics.Timer("db.syllabus.select.duration"):
            syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
        if not syllabus:
            return not_found_response(request, "No syllabus found for this course")

        s3_key = syllabus.s3_object_key

        try:
            with metrics.Timer("db.syllabus.delete.duration"):
                db.delete(syllabus)
                course.has_syllabus = False
                course.date_updated = datetime.now(timezone.utc)
                db.commit()
            logger.info(
                "Syllabus metadata removed from database for course %s %s; course marked as has_syllabus=False",
                course.department_code, course.number
            )
        except Exception as e:
            db.rollback()
            logger.error("Error deleting syllabus metadata: %s", e, exc_info=True)
            return validation_error_response(request, "Failed to delete syllabus")

        try:
            with metrics.Timer("s3.syllabus.delete.duration"):
                s3.delete_file(s3_key)
            logger.info("Syllabus file deleted from S3: %s", s3_key)
        except Exception as e:
            logger.error("Failed to delete S3 object %s: %s", s3_key, e, exc_info=True)

        return Response(status_code=status.HTTP_204_NO_CONTENT)
