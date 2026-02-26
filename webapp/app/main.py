import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    detect_platform()
    yield


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

# Regex for department_code: 2-6 uppercase letters
DEPT_CODE_RE = re.compile(r"^[A-Z]{2,6}$")
VALID_CLASSIFICATIONS = {"core", "elective"}
COURSE_IMMUTABLE_FIELDS = {"id", "department_code", "number", "has_syllabus", "date_created", "date_updated"}
COURSE_UPDATABLE_FIELDS = {"title", "credit_hours", "classification", "description", "prerequisites"}



# ──────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
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
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return validation_error_response(request, "Invalid request")


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.get("/healthz")
async def health_check(request: Request):
    if request.query_params:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
    body = await request.body()
    if body:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
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


@app.api_route("/healthz", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def healthz_method_not_allowed():
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers=CACHE_HEADERS)


# ──────────────────────────────────────────────
# Metadata
# ──────────────────────────────────────────────
@app.get("/v1/metadata", response_model=MetadataResponse)
async def get_instance_metadata(request: Request):
    if request.query_params:
        return create_error_response(request, "Bad Request", "Query parameters are not allowed",
                                     status.HTTP_400_BAD_REQUEST, headers=CACHE_HEADERS)
    body = await request.body()
    if body:
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
        return create_error_response(request, "Service Unavailable",
                                     "Unable to retrieve instance metadata. The application may not be running on a supported cloud platform.",
                                     status.HTTP_503_SERVICE_UNAVAILABLE, headers=CACHE_HEADERS)
    return JSONResponse(content=metadata, headers=CACHE_HEADERS)


@app.api_route("/v1/metadata", methods=["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def metadata_method_not_allowed():
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers=CACHE_HEADERS)


# ──────────────────────────────────────────────
# User endpoints (unchanged)
# ──────────────────────────────────────────────
@app.post("/v1/user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, response: Response, db: Session = Depends(get_db)):
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

    if db.query(User).filter(func.lower(User.username) == str(username).lower()).first():
        return conflict_error_response(request)

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


@app.get("/v1/user/self", response_model=UserResponse)
async def get_user_self(current_user: User = Depends(get_current_user)):
    return current_user


@app.put("/v1/user/self", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating user: {e}", exc_info=True)
        return validation_error_response(request, "Failed to update user")


# ──────────────────────────────────────────────
# Course helpers
# ──────────────────────────────────────────────
def _validate_course_fields(data: dict, request: Request, is_update: bool = False):
    """Validate course fields. Returns an error response or None if valid."""

    if is_update:
        # Check for immutable fields
        immutable_sent = set(data.keys()) & COURSE_IMMUTABLE_FIELDS
        if immutable_sent:
            field = list(immutable_sent)[0]
            return bad_request_response(request, f"Field '{field}' cannot be updated")
        # Check at least one updatable field
        updatable_sent = set(data.keys()) & COURSE_UPDATABLE_FIELDS
        if not updatable_sent:
            return bad_request_response(request, "At least one updatable field must be provided")
        # Reject unknown fields
        unknown = set(data.keys()) - COURSE_UPDATABLE_FIELDS
        if unknown:
            return bad_request_response(request, f"Unknown field: '{list(unknown)[0]}'")

    # Validate department_code (only on create)
    if "department_code" in data:
        dc = data["department_code"]
        if not isinstance(dc, str) or not DEPT_CODE_RE.match(dc):
            return validation_error_response(request, "department_code must be 2–6 uppercase letters")

    # Validate number (only on create)
    if "number" in data:
        num = data["number"]
        if not isinstance(num, str) or len(num) < 1 or len(num) > 6:
            return validation_error_response(request, "number must be 1–6 characters")

    # Validate title
    if "title" in data:
        t = data["title"]
        if not isinstance(t, str) or len(t) < 1 or len(t) > 255:
            return validation_error_response(request, "title must be 1–255 characters")

    # Validate credit_hours
    if "credit_hours" in data:
        ch = data["credit_hours"]
        if not isinstance(ch, int) or isinstance(ch, bool) or ch < 1 or ch > 8:
            return validation_error_response(request, "credit_hours must be an integer between 1 and 8")

    # Validate classification
    if "classification" in data:
        cl = data["classification"]
        if not isinstance(cl, str) or cl not in VALID_CLASSIFICATIONS:
            return validation_error_response(request, "classification must be 'core' or 'elective'")

    # Validate description (optional)
    if "description" in data and data["description"] is not None:
        d = data["description"]
        if not isinstance(d, str) or len(d) > 2000:
            return validation_error_response(request, "description must be a string of max 2000 characters")

    # Validate prerequisites (optional)
    if "prerequisites" in data and data["prerequisites"] is not None:
        p = data["prerequisites"]
        if not isinstance(p, str) or len(p) > 512:
            return validation_error_response(request, "prerequisites must be a string of max 512 characters")

    return None  # All valid


# ──────────────────────────────────────────────
# Course CRUD endpoints
# ──────────────────────────────────────────────
@app.get("/v1/courses", response_model=List[CourseResponse])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    courses = (
        db.query(Course)
        .order_by(Course.department_code.asc(), Course.number.asc())
        .all()
    )
    return courses


@app.post("/v1/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check Content-Type
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

    # Check required fields
    required = ["department_code", "number", "title", "credit_hours", "classification"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return validation_error_response(request, f"Missing required fields: {', '.join(missing)}")

    # Reject server-managed fields from client
    server_fields = {"id", "has_syllabus", "date_created", "date_updated"}
    sent_server = set(data.keys()) & server_fields
    if sent_server:
        return validation_error_response(request, f"Field '{list(sent_server)[0]}' must not be set by the client")

    # Validate fields
    err = _validate_course_fields(data, request, is_update=False)
    if err:
        return err

    # Check uniqueness of department_code + number
    exists = (
        db.query(Course)
        .filter(Course.department_code == data["department_code"], Course.number == data["number"])
        .first()
    )
    if exists:
        return conflict_error_response(
            request, f"Course {data['department_code']} {data['number']} already exists"
        )

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
        db.add(course)
        db.commit()
        db.refresh(course)

        response.headers["Location"] = f"/v1/courses/{course.id}"
        return course

    except IntegrityError:
        db.rollback()
        return conflict_error_response(
            request, f"Course {data['department_code']} {data['number']} already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating course: {e}", exc_info=True)
        return validation_error_response(request, "Failed to create course")


@app.get("/v1/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")
    return course


@app.put("/v1/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    # Validate
    err = _validate_course_fields(data, request, is_update=True)
    if err:
        return err

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")

    # Apply updates
    if "title" in data:
        course.title = data["title"]
    if "credit_hours" in data:
        course.credit_hours = data["credit_hours"]
    if "classification" in data:
        course.classification = data["classification"]
    if "description" in data:
        course.description = data["description"]
    if "prerequisites" in data:
        course.prerequisites = data["prerequisites"]

    try:
        course.date_updated = datetime.now(timezone.utc)
        db.commit()
        db.refresh(course)
        return course
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating course: {e}", exc_info=True)
        return validation_error_response(request, "Failed to update course")


@app.delete("/v1/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")

    if course.has_syllabus:
        return conflict_error_response(
            request,
            f"Cannot delete course {course.department_code} {course.number} because it has a syllabus attached. Delete the syllabus first.",
        )

    try:
        db.delete(course)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting course: {e}", exc_info=True)
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
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")

    syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
    if not syllabus:
        return not_found_response(request, "No syllabus found for this course")

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
    # Check course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")

    # Check if syllabus already exists
    if course.has_syllabus:
        return conflict_error_response(
            request,
            f"Course {course.department_code} {course.number} already has a syllabus. Delete the existing syllabus first.",
        )

    # Validate file
    if file is None or file.filename is None or file.filename == "":
        return bad_request_response(request, "A syllabus file must be provided in the 'file' form field")

    # Read file content
    content = await file.read()
    if len(content) == 0:
        return bad_request_response(request, "The uploaded file is empty")

    # Build S3 key and upload
    bucket = s3.get_bucket_name()
    obj_key = s3.build_object_key(str(course.id), file.filename)
    content_type = file.content_type or "application/octet-stream"

    try:
        s3.upload_file(obj_key, content, content_type)
    except Exception as e:
        logger.error(f"S3 upload failed: {e}", exc_info=True)
        return create_error_response(request, "Internal Error", "Failed to upload file to storage",
                                     status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Persist metadata in DB
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
        db.add(syllabus)
        course.has_syllabus = True
        course.date_updated = datetime.now(timezone.utc)
        db.commit()
        db.refresh(syllabus)

        response.headers["Location"] = f"/v1/courses/{course_id}/syllabus"
        return syllabus

    except Exception as e:
        db.rollback()
        # Best-effort cleanup of S3 object
        try:
            s3.delete_file(obj_key)
        except Exception:
            pass
        logger.error(f"Error saving syllabus metadata: {e}", exc_info=True)
        return validation_error_response(request, "Failed to save syllabus metadata")


@app.delete("/v1/courses/{course_id}/syllabus", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syllabus(
    course_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return not_found_response(request, "Course not found")

    syllabus = db.query(Syllabus).filter(Syllabus.course_id == course_id).first()
    if not syllabus:
        return not_found_response(request, "No syllabus found for this course")

    s3_key = syllabus.s3_object_key

    try:
        # Delete from DB first
        db.delete(syllabus)
        course.has_syllabus = False
        course.date_updated = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting syllabus metadata: {e}", exc_info=True)
        return validation_error_response(request, "Failed to delete syllabus")

    # Delete from S3 (after DB commit succeeds)
    try:
        s3.delete_file(s3_key)
    except Exception as e:
        logger.error(f"Failed to delete S3 object {s3_key}: {e}", exc_info=True)
        # DB is already committed — log but don't fail the request

    return Response(status_code=status.HTTP_204_NO_CONTENT)
