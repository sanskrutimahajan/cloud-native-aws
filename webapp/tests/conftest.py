"""
Test Configuration - Sets up test database, fixtures, and FastAPI test client
"""

import base64
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Course, Syllabus, User

DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5432")
DB_NAME = os.getenv("DATABASE_NAME", "webapp_db")
DB_USER = os.getenv("DATABASE_USER", "webapp_user")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")

TEST_DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables before tests, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Transactional session per test with savepoint-based isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with DB dependency overridden and S3 mocked."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock S3 operations so tests don't need real AWS credentials
    with patch("app.s3.get_s3_client") as mock_client, \
         patch("app.s3.get_bucket_name", return_value="test-bucket-uuid"):
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture
def create_test_user(db_session):
    """Factory fixture to create a user directly in the DB."""
    def _create(
        username="testuser@example.com",
        password="password123",
        first_name="Test",
        last_name="User"
    ):
        user = User(
            username=username,
            password=hash_password(password),
            first_name=first_name,
            last_name=last_name
        )
        db_session.add(user)
        db_session.flush()
        return user, password
    return _create


@pytest.fixture
def auth_headers():
    """Factory fixture to build Basic Auth headers."""
    def _auth(username, password):
        credentials = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()
        return {"Authorization": f"Basic {credentials}"}
    return _auth


@pytest.fixture
def test_user_with_auth(create_test_user, auth_headers):
    """Creates a user and returns (user, auth_headers_dict)."""
    user, password = create_test_user()
    headers = auth_headers(user.username, password)
    return user, headers


@pytest.fixture
def create_test_course(db_session):
    """Factory fixture to create a course directly in the DB."""
    _counter = [0]

    def _create(
        department_code="CSYE",
        number=None,
        title="Test Course",
        credit_hours=4,
        classification="core",
        description=None,
        prerequisites=None,
    ):
        _counter[0] += 1
        if number is None:
            number = str(6200 + _counter[0])
        course = Course(
            department_code=department_code,
            number=number,
            title=title,
            credit_hours=credit_hours,
            classification=classification,
            description=description,
            prerequisites=prerequisites,
            has_syllabus=False,
        )
        db_session.add(course)
        db_session.flush()
        return course
    return _create


@pytest.fixture
def sample_course_payload():
    """Returns a valid course creation payload."""
    return {
        "department_code": "ACCT",
        "number": "3220",
        "title": "Data Analytics for Advisory Services",
        "credit_hours": 4,
        "classification": "elective",
        "description": "Covers data analytics in advisory services.",
        "prerequisites": "ACCT 2301 with minimum grade D-",
    }
