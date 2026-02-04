"""
Tests for GET /healthz - Health Check Endpoint
"""

import time
from unittest.mock import patch
from app.models import HealthCheck


# ==================== POSITIVE TESTS ====================

class TestHealthzPositive:

    # GET /healthz returns 200 when database is healthy
    def test_healthz_returns_200(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200

    # GET /healthz response body should be empty on success
    def test_healthz_returns_empty_body(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.content == b""

    # Response includes Cache-Control: no-cache, no-store, must-revalidate
    def test_healthz_has_cache_control_header(self, client):
        response = client.get("/healthz")
        assert "no-cache" in response.headers.get("cache-control", "")
        assert "no-store" in response.headers.get("cache-control", "")
        assert "must-revalidate" in response.headers.get("cache-control", "")

    # Response includes Pragma: no-cache
    def test_healthz_has_pragma_header(self, client):
        response = client.get("/healthz")
        assert response.headers.get("pragma") == "no-cache"

    # Response includes X-Content-Type-Options: nosniff
    def test_healthz_has_x_content_type_options_header(self, client):
        response = client.get("/healthz")
        assert response.headers.get("x-content-type-options") == "nosniff"

    # Multiple consecutive health checks all return 200
    def test_healthz_multiple_calls_succeed(self, client):
        for _ in range(3):
            response = client.get("/healthz")
            assert response.status_code == 200

    # Each health check should create one database record
    def test_healthz_creates_database_record(self, client, db_session):
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 1

    # Multiple calls should create multiple records
    def test_healthz_each_call_creates_new_record(self, client, db_session):
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        client.get("/healthz")
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 3

    # Health check should respond in under 1 second
    def test_healthz_response_time_under_1_second(self, client):
        start = time.time()
        response = client.get("/healthz")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0

    # Successful response confirms database connectivity
    def test_healthz_verifies_database_connectivity(self, client, db_session):
        response = client.get("/healthz")
        assert response.status_code == 200
        records = db_session.query(HealthCheck).all()
        assert len(records) >= 1


# ==================== NEGATIVE TESTS ====================

class TestHealthzNegative:

    # GET /healthz with request body returns 400
    def test_healthz_rejects_request_body(self, client):
        response = client.request("GET", "/healthz", content=b'{"key": "value"}')
        assert response.status_code == 400

    # GET /healthz with query parameters returns 400
    def test_healthz_rejects_query_params(self, client):
        response = client.get("/healthz?foo=bar")
        assert response.status_code == 400

    # POST /healthz returns 405
    def test_healthz_post_not_allowed(self, client):
        response = client.post("/healthz")
        assert response.status_code == 405

    # PUT /healthz returns 405
    def test_healthz_put_not_allowed(self, client):
        response = client.put("/healthz")
        assert response.status_code == 405

    # DELETE /healthz returns 405
    def test_healthz_delete_not_allowed(self, client):
        response = client.delete("/healthz")
        assert response.status_code == 405

    # PATCH /healthz returns 405
    def test_healthz_patch_not_allowed(self, client):
        response = client.patch("/healthz")
        assert response.status_code == 405

    # HEAD /healthz returns 405
    def test_healthz_head_not_allowed(self, client):
        response = client.head("/healthz")
        assert response.status_code == 405

    # OPTIONS /healthz returns 405
    def test_healthz_options_not_allowed(self, client):
        response = client.options("/healthz")
        assert response.status_code == 405

    # GET /healthz returns 503 when database is unavailable
    def test_healthz_returns_503_when_db_unavailable(self, client):
        with patch("app.main.get_db") as mock_db:
            mock_db.side_effect = Exception("DB connection failed")

            from fastapi.testclient import TestClient
            from app.main import app
            from app.database import get_db

            def broken_db():
                raise Exception("DB connection failed")

            app.dependency_overrides[get_db] = broken_db
            with TestClient(app, raise_server_exceptions=False) as broken_client:
                response = broken_client.get("/healthz")

            assert response.status_code == 503
            app.dependency_overrides.clear()
