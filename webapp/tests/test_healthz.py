import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from app.models import HealthCheck


class TestHealthzPositive:

    # Service is healthy and database connection successful
    def test_healthz_returns_200_with_empty_body(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.content == b""

    # Response headers - Cache-Control, Pragma, X-Content-Type-Options
    def test_healthz_has_required_security_headers(self, client):
        response = client.get("/healthz")
        
        cache_control = response.headers.get("cache-control", "")
        assert "no-cache" in cache_control
        assert "no-store" in cache_control
        assert "must-revalidate" in cache_control
        assert response.headers.get("pragma") == "no-cache"
        assert response.headers.get("x-content-type-options") == "nosniff"

    # Must verify database connectivity by creating health check record
    def test_healthz_creates_database_record(self, client, db_session):
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 1

    # Multiple consecutive calls should all succeed (idempotent operation)
    def test_healthz_multiple_calls_succeed(self, client):
        for _ in range(3):
            response = client.get("/healthz")
            assert response.status_code == 200

    # Performance: Health check must respond quickly for load balancer polling
    def test_healthz_response_time_under_1_second(self, client):
        start = time.time()
        response = client.get("/healthz")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0


class TestHealthzNegative:

    # 400 - Bad Request when request contains body
    def test_healthz_rejects_request_body(self, client):
        response = client.request("GET", "/healthz", content=b'{"key": "value"}')
        assert response.status_code == 400

    # 400 - Bad Request when request contains query parameters
    def test_healthz_rejects_query_params(self, client):
        response = client.get("/healthz?foo=bar")
        assert response.status_code == 400

    # 405 - Method Not Allowed for POST, PUT, DELETE, PATCH, HEAD, OPTIONS
    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    def test_healthz_only_allows_get_method(self, client, method):
        response = client.request(method, "/healthz")
        assert response.status_code == 405

    # 503 - Service Unavailable when database connection fails
    def test_healthz_returns_503_when_db_unavailable(self, client):
        with patch("app.main.get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("DB connection failed")
            response = client.get("/healthz")
            assert response.status_code == 503


class TestHealthzEdgeCases:

    # Edge Case: Whitespace-only body should be rejected (not truly empty)
    def test_healthz_rejects_whitespace_only_body(self, client):
        whitespace_bodies = [b"   ", b"\t\t\t", b"\n\n\n", b"  \t\n  "]
        for body in whitespace_bodies:
            response = client.request("GET", "/healthz", content=body)
            assert response.status_code == 400

    # Edge Case: Multiple query parameters should all be rejected
    def test_healthz_rejects_multiple_query_parameters(self, client):
        test_queries = [
            "?a=1&b=2",
            "?foo=bar&baz=qux&test=value",
            "?x=1&x=2&x=3",
        ]
        for query in test_queries:
            response = client.get(f"/healthz{query}")
            assert response.status_code == 400

    # Concurrency: 50 concurrent requests should complete without deadlock
    def test_concurrent_healthz_no_deadlock(self, client):
        results = []

        def call_healthz():
            resp = client.get("/healthz")
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(call_healthz) for _ in range(50)]
            for f in futures:
                f.result(timeout=30)

        assert results.count(200) == 50
        assert len(results) == 50

    # Performance: Rapid sequential requests should all succeed
    def test_rapid_sequential_health_checks(self, client):
        for i in range(20):
            response = client.get("/healthz")
            assert response.status_code == 200, f"Failed on request {i+1}"

    # Database: Verify health check records have timestamps
    def test_healthz_records_have_timestamps(self, client, db_session):
        client.get("/healthz")
        record = db_session.query(HealthCheck).order_by(HealthCheck.check_id.desc()).first()
        assert record is not None
        assert record.check_datetime is not None

    #  Very large request body should be rejected
    def test_healthz_rejects_large_request_body(self, client):
        large_body = b"x" * 10000
        response = client.request("GET", "/healthz", content=large_body)
        assert response.status_code == 400