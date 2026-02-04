"""
Test Configuration - Sets up test database, fixtures, and FastAPI test client
"""

import os
import pytest
import base64
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.auth import hash_password
from app.models import User

# Database configuration - reuses the same DB from .env, tests are
# isolated via per-test transaction rollback (no data is permanently written)
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5432")
DB_NAME = os.getenv("DATABASE_NAME", "webapp_db")
DB_USER = os.getenv("DATABASE_USER", "webapp_user")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "cloud2026")

TEST_DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Fixture: Creates all DB tables once before the test session starts,
# drops them after all tests finish. Runs automatically (autouse=True).
@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the entire test session, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# Fixture: Provides a fresh DB session per test. Uses savepoints so
# app code can call commit() without actually persisting data.
# Everything is rolled back after each test for complete isolation.
@pytest.fixture(scope="function")
def db_session():
    """
    Provide a transactional database session for each test.
    Uses savepoint so app code can call commit() without
    actually committing the outer transaction.
    Rolled back after each test for isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    # Use nested transaction (SAVEPOINT) so session.commit() in app code
    # does not commit the outer transaction
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Fixture: Creates a FastAPI TestClient that sends HTTP requests to the app.
# Overrides the get_db dependency so the app uses the test DB session.
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


# Fixture: Factory function to insert a user directly into the test DB.
# Returns (user_object, plaintext_password) so tests can use both.
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
        return user, password  # return user object + plaintext password
    return _create


# Fixture: Factory function to build HTTP Basic Auth headers
# from a username and password (base64 encoded).
@pytest.fixture
def auth_headers():
    """Factory fixture to build Basic Auth headers."""
    def _auth(username, password):
        credentials = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()
        return {"Authorization": f"Basic {credentials}"}
    return _auth


# Fixture: Convenience shortcut - creates a test user AND returns
# the matching auth headers in one step. Returns (user, headers_dict).
@pytest.fixture
def test_user_with_auth(create_test_user, auth_headers):
    """Convenience: creates a user and returns (user, auth_headers_dict)."""
    user, password = create_test_user()
    headers = auth_headers(user.username, password)
    return user, headers
