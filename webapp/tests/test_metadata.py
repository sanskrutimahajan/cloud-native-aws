"""Tests for GET /v1/metadata endpoint."""

from unittest.mock import patch

import pytest

ENDPOINT = "/v1/metadata"

MOCK_GCP_METADATA = {
    "cloud_platform": "gcp",
    "instance_id": "1234567890123456789",
    "region": "us-east1-b",
    "machine_type": "e2-medium",
    "network_interfaces": [
        {
            "private_ip": "10.128.0.2",
            "public_ip": "35.231.45.67",
            "network": "default",
        }
    ],
}

MOCK_AWS_METADATA = {
    "cloud_platform": "aws",
    "instance_id": "i-0abcdef1234567890",
    "region": "us-east-1",
    "machine_type": "t2.micro",
    "network_interfaces": [
        {
            "private_ip": "172.31.16.5",
            "public_ip": "54.210.167.89",
            "network": "vpc-0a1b2c3d4e5f6g7h8",
        }
    ],
}


class TestMetadataSuccess:
    """Successful metadata retrieval."""

    def test_gcp_metadata(self, client):
        with patch("app.main.get_metadata", return_value=MOCK_GCP_METADATA):
            r = client.get(ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert data["cloud_platform"] == "gcp"
        assert data["instance_id"] == "1234567890123456789"
        assert data["region"] == "us-east1-b"
        assert data["machine_type"] == "e2-medium"
        assert len(data["network_interfaces"]) == 1
        assert data["network_interfaces"][0]["private_ip"] == "10.128.0.2"
        assert data["network_interfaces"][0]["public_ip"] == "35.231.45.67"
        assert data["network_interfaces"][0]["network"] == "default"

    def test_aws_metadata(self, client):
        with patch("app.main.get_metadata", return_value=MOCK_AWS_METADATA):
            r = client.get(ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert data["cloud_platform"] == "aws"
        assert data["instance_id"] == "i-0abcdef1234567890"
        assert data["region"] == "us-east-1"
        assert data["machine_type"] == "t2.micro"
        assert len(data["network_interfaces"]) == 1
        assert data["network_interfaces"][0]["network"] == "vpc-0a1b2c3d4e5f6g7h8"

    def test_null_public_ip(self, client):
        metadata = {**MOCK_GCP_METADATA}
        metadata["network_interfaces"] = [
            {"private_ip": "10.0.0.2", "public_ip": None, "network": "default"}
        ]
        with patch("app.main.get_metadata", return_value=metadata):
            r = client.get(ENDPOINT)
        assert r.status_code == 200
        assert r.json()["network_interfaces"][0]["public_ip"] is None

    def test_multiple_interfaces(self, client):
        metadata = {**MOCK_AWS_METADATA}
        metadata["network_interfaces"] = [
            {"private_ip": "172.31.16.5", "public_ip": "54.210.167.89", "network": "vpc-1"},
            {"private_ip": "172.31.16.6", "public_ip": None, "network": "vpc-2"},
        ]
        with patch("app.main.get_metadata", return_value=metadata):
            r = client.get(ENDPOINT)
        assert r.status_code == 200
        assert len(r.json()["network_interfaces"]) == 2

    def test_response_content_type(self, client):
        with patch("app.main.get_metadata", return_value=MOCK_GCP_METADATA):
            r = client.get(ENDPOINT)
        assert r.headers["content-type"] == "application/json"


class TestMetadataCacheHeaders:
    """Response cache-control headers."""

    def test_cache_headers_on_success(self, client):
        with patch("app.main.get_metadata", return_value=MOCK_GCP_METADATA):
            r = client.get(ENDPOINT)
        assert r.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"

    def test_cache_headers_on_503(self, client):
        with patch("app.main.get_metadata", return_value=None):
            r = client.get(ENDPOINT)
        assert r.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"

    def test_cache_headers_on_400_query_params(self, client):
        r = client.get(f"{ENDPOINT}?foo=bar")
        assert r.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"

    def test_cache_headers_on_400_body(self, client):
        r = client.request("GET", ENDPOINT, content=b'{"key": "value"}')
        assert r.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"


class TestMetadataMethodNotAllowed:
    """Non-GET methods return 405."""

    @pytest.mark.parametrize("method", ["post", "put", "delete", "patch", "head", "options"])
    def test_method_not_allowed(self, client, method):
        r = getattr(client, method)(ENDPOINT)
        assert r.status_code == 405


class TestMetadataBadRequest:
    """Request body and query params return 400."""

    def test_query_params_rejected(self, client):
        r = client.get(f"{ENDPOINT}?foo=bar")
        assert r.status_code == 400
        data = r.json()
        assert data["error"] == "Bad Request"
        assert "path" in data
        assert "timestamp" in data

    def test_request_body_rejected(self, client):
        r = client.request("GET", ENDPOINT, content=b'{"key": "value"}')
        assert r.status_code == 400
        data = r.json()
        assert data["error"] == "Bad Request"


class TestMetadataServiceUnavailable:
    """503 when platform not detected or metadata retrieval fails."""

    def test_no_cloud_platform(self, client):
        with patch("app.main.get_metadata", return_value=None):
            r = client.get(ENDPOINT)
        assert r.status_code == 503
        data = r.json()
        assert data["error"] == "Service Unavailable"
        assert "timestamp" in data
        assert data["path"] == "/v1/metadata"

    def test_metadata_retrieval_error(self, client):
        with patch("app.main.get_metadata", side_effect=Exception("connection failed")):
            r = client.get(ENDPOINT)
        assert r.status_code == 503
        data = r.json()
        assert data["error"] == "Service Unavailable"


class TestMetadataNoAuth:
    """Endpoint is public, no authentication required."""

    def test_no_auth_needed(self, client):
        with patch("app.main.get_metadata", return_value=MOCK_GCP_METADATA):
            r = client.get(ENDPOINT)
        assert r.status_code == 200
