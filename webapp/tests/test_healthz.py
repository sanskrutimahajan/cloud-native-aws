"""
Tests for GET /healthz - Health Check Endpoint
"""

import time
from unittest.mock import patch
from app.models import HealthCheck


# ==================== POSITIVE TESTS ====================

class TestHealthzPositive:

    def test_healthz_returns_200(self, client):
        """GET /healthz returns 200 when database is healthy."""
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_healthz_returns_empty_body(self, client):
        """GET /healthz response body should be empty on success."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.content == b""

    def test_healthz_has_cache_control_header(self, client):
        """Response includes Cache-Control: no-cache, no-store, must-revalidate."""
        response = client.get("/healthz")
        assert "no-cache" in response.headers.get("cache-control", "")
        assert "no-store" in response.headers.get("cache-control", "")
        assert "must-revalidate" in response.headers.get("cache-control", "")

    def test_healthz_has_pragma_header(self, client):
        """Response includes Pragma: no-cache."""
        response = client.get("/healthz")
        assert response.headers.get("pragma") == "no-cache"

    def test_healthz_has_x_content_type_options_header(self, client):
        """Response includes X-Content-Type-Options: nosniff."""
        response = client.get("/healthz")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_healthz_multiple_calls_succeed(self, client):
        """Multiple consecutive health checks all return 200."""
        for _ in range(3):
            response = client.get("/healthz")
            assert response.status_code == 200

    def test_healthz_creates_database_record(self, client, db_session):
        """Each health check should create a record in the database."""
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 1

    def test_healthz_each_call_creates_new_record(self, client, db_session):
        """Multiple calls should create multiple records."""
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        client.get("/healthz")
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 3

    def test_healthz_response_time_under_1_second(self, client):
        """Health check should respond in under 1 second."""
        start = time.time()
        response = client.get("/healthz")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, expected < 1s"

    def test_healthz_verifies_database_connectivity(self, client, db_session):
        """A successful 200 confirms the database is reachable."""
        response = client.get("/healthz")
        assert response.status_code == 200
        # Verify we can actually query the DB after the health check
        records = db_session.query(HealthCheck).all()
        assert len(records) >= 1


# ==================== NEGATIVE TESTS ====================

class TestHealthzNegative:

    def test_healthz_rejects_request_body(self, client):
        """GET /healthz with a body returns 400."""
        response = client.get("/healthz", content=b'{"key": "value"}')
        assert response.status_code == 400

    def test_healthz_rejects_query_params(self, client):
        """GET /healthz with query parameters returns 400."""
        response = client.get("/healthz?foo=bar")
        assert response.status_code == 400

    def test_healthz_post_not_allowed(self, client):
        """POST /healthz returns 405 Method Not Allowed."""
        response = client.post("/healthz")
        assert response.status_code == 405

    def test_healthz_put_not_allowed(self, client):
        """PUT /healthz returns 405 Method Not Allowed."""
        response = client.put("/healthz")
        assert response.status_code == 405

    def test_healthz_delete_not_allowed(self, client):
        """DELETE /healthz returns 405 Method Not Allowed."""
        response = client.delete("/healthz")
        assert response.status_code == 405

    def test_healthz_patch_not_allowed(self, client):
        """PATCH /healthz returns 405 Method Not Allowed."""
        response = client.patch("/healthz")
        assert response.status_code == 405

    def test_healthz_head_not_allowed(self, client):
        """HEAD /healthz returns 405 Method Not Allowed."""
        response = client.head("/healthz")
        assert response.status_code == 405

    def test_healthz_options_not_allowed(self, client):
        """OPTIONS /healthz returns 405 Method Not Allowed."""
        response = client.options("/healthz")
        assert response.status_code == 405

    def test_healthz_returns_503_when_db_unavailable(self, client):
        """GET /healthz returns 503 when database connection fails."""
        with patch("app.main.get_db") as mock_db:
            mock_db.side_effect = Exception("DB connection failed")
            # Use a fresh client call that triggers the mocked dependency
            from fastapi.testclient import TestClient
            from app.main import app
            from app.database import get_db

            def broken_db():
                raise Exception("DB connection failed")

            app.dependency_overrides[get_db] = broken_db
            with TestClient(app) as broken_client:
                response = broken_client.get("/healthz")
            assert response.status_code == 503
            # Restore overrides (client fixture will clear them anyway)
            app.dependency_overrides.clear()
