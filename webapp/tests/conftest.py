"""
Test Configuration - Sets up test database, fixtures, and FastAPI test client
"""

import base64
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User

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
    """FastAPI TestClient with DB dependency overridden to use test session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
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
