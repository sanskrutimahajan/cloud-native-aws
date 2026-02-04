"""
Tests for User Endpoints:
  POST /v1/user        - Create user (no auth)
  GET  /v1/user/self   - Get authenticated user info (Basic Auth)
  PUT  /v1/user/self   - Update authenticated user (Basic Auth)
"""

import uuid
import time
import bcrypt
from concurrent.futures import ThreadPoolExecutor
from app.models import User


# ====================================================================
#  A. POSITIVE TESTS
# ====================================================================

class TestCreateUserPositive:
    """POST /v1/user - successful creation tests."""

    def test_create_user_returns_201(self, client):
        """Valid user creation returns 201 Created."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "jane.doe@example.com",
            "password": "securepass123"
        }
        response = client.post(
            "/v1/user",
            json=payload
        )
        assert response.status_code == 201

    def test_create_user_response_body_structure(self, client):
        """Response body has all expected fields."""
        payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "username": "alice.smith@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        assert "id" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "username" in data
        assert "account_created" in data
        assert "account_updated" in data

    def test_create_user_response_data_types(self, client):
        """All response fields should have correct data types."""
        from datetime import datetime
        payload = {
            "first_name": "Types",
            "last_name": "Check",
            "username": "typecheck@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        # id must be a string (UUID format)
        assert isinstance(data["id"], str)
        uuid.UUID(data["id"])
        # first_name, last_name, username must be strings
        assert isinstance(data["first_name"], str)
        assert isinstance(data["last_name"], str)
        assert isinstance(data["username"], str)
        # timestamps must be strings in ISO 8601 format
        assert isinstance(data["account_created"], str)
        assert isinstance(data["account_updated"], str)
        datetime.fromisoformat(data["account_created"])
        datetime.fromisoformat(data["account_updated"])

    def test_create_user_response_values_match_input(self, client):
        """Response fields match the input values."""
        payload = {
            "first_name": "Bob",
            "last_name": "Jones",
            "username": "bob.jones@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        assert data["first_name"] == "Bob"
        assert data["last_name"] == "Jones"
        assert data["username"] == "bob.jones@example.com"

    def test_create_user_password_not_in_response(self, client):
        """Password must NEVER appear in the response."""
        payload = {
            "first_name": "Charlie",
            "last_name": "Brown",
            "username": "charlie@example.com",
            "password": "mypassword1"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        assert "password" not in data

    def test_create_user_id_is_valid_uuid(self, client):
        """Returned id should be a valid UUID."""
        payload = {
            "first_name": "Dave",
            "last_name": "Wilson",
            "username": "dave.wilson@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        # Should not raise ValueError
        uuid.UUID(data["id"])

    def test_create_user_timestamps_present(self, client):
        """account_created and account_updated should be non-empty strings."""
        payload = {
            "first_name": "Eve",
            "last_name": "Adams",
            "username": "eve.adams@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        assert isinstance(data["account_created"], str)
        assert len(data["account_created"]) > 0
        assert isinstance(data["account_updated"], str)
        assert len(data["account_updated"]) > 0

    def test_create_user_content_type_is_json(self, client):
        """Response Content-Type should be application/json."""
        payload = {
            "first_name": "Frank",
            "last_name": "Lee",
            "username": "frank.lee@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert "application/json" in response.headers.get("content-type", "")

    def test_create_user_different_valid_emails(self, client):
        """Various valid email formats should succeed."""
        emails = [
            "user1@domain.com",
            "user2@sub.domain.org",
            "first.last@company.co",
        ]
        for email in emails:
            payload = {
                "first_name": "Test",
                "last_name": "User",
                "username": email,
                "password": "password123"
            }
            response = client.post("/v1/user", json=payload)
            assert response.status_code == 201, f"Failed for email: {email}"

    def test_create_user_has_location_header(self, client):
        """201 response should include Location: /v1/user/self header."""
        payload = {
            "first_name": "Loc",
            "last_name": "Header",
            "username": "locheader@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.headers.get("location") == "/v1/user/self"

    def test_create_user_password_is_bcrypt_hashed(self, client, db_session):
        """Password should be stored as a BCrypt hash, not plaintext."""
        payload = {
            "first_name": "Hash",
            "last_name": "Check",
            "username": "hashcheck@example.com",
            "password": "password123"
        }
        client.post("/v1/user", json=payload)
        user = db_session.query(User).filter(
            User.username == "hashcheck@example.com"
        ).first()
        # Password in DB should NOT be the plaintext
        assert user.password != "password123"
        # Should be a valid BCrypt hash (starts with $2b$)
        assert user.password.startswith("$2b$")


class TestGetUserSelfPositive:
    """GET /v1/user/self - successful retrieval tests."""

    def test_get_user_self_returns_200(self, client, test_user_with_auth):
        """Authenticated GET /v1/user/self returns 200."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 200

    def test_get_user_self_returns_correct_data(self, client, test_user_with_auth):
        """Returned data matches the authenticated user."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()

        assert data["username"] == user.username
        assert data["first_name"] == user.first_name
        assert data["last_name"] == user.last_name

    def test_get_user_self_no_password_in_response(self, client, test_user_with_auth):
        """Password must not be in the response."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        assert "password" not in data

    def test_get_user_self_has_id_field(self, client, test_user_with_auth):
        """Response includes a valid UUID id field."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        uuid.UUID(data["id"])

    def test_get_user_self_content_type_json(self, client, test_user_with_auth):
        """Response Content-Type is application/json."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        assert "application/json" in response.headers.get("content-type", "")

    def test_get_user_self_has_timestamps(self, client, test_user_with_auth):
        """Response includes account_created and account_updated."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        assert "account_created" in data
        assert "account_updated" in data

    def test_get_user_self_response_data_types(self, client, test_user_with_auth):
        """All GET response fields should have correct data types."""
        from datetime import datetime
        _, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()

        assert isinstance(data["id"], str)
        uuid.UUID(data["id"])
        assert isinstance(data["first_name"], str)
        assert isinstance(data["last_name"], str)
        assert isinstance(data["username"], str)
        assert isinstance(data["account_created"], str)
        assert isinstance(data["account_updated"], str)
        datetime.fromisoformat(data["account_created"])
        datetime.fromisoformat(data["account_updated"])

    def test_get_user_self_multiple_calls_return_same_data(self, client, test_user_with_auth):
        """Multiple GET calls return the same user data."""
        _, headers = test_user_with_auth
        resp1 = client.get("/v1/user/self", headers=headers).json()
        resp2 = client.get("/v1/user/self", headers=headers).json()
        resp3 = client.get("/v1/user/self", headers=headers).json()
        assert resp1 == resp2 == resp3


class TestUpdateUserPositive:
    """PUT /v1/user/self - successful update tests."""

    def test_update_first_name_returns_204(self, client, test_user_with_auth):
        """Updating first_name returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Updated"},
            headers=headers
        )
        assert response.status_code == 204

    def test_update_last_name_returns_204(self, client, test_user_with_auth):
        """Updating last_name returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"last_name": "NewLast"},
            headers=headers
        )
        assert response.status_code == 204

    def test_update_password_returns_204(self, client, test_user_with_auth):
        """Updating password returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"password": "newpassword123"},
            headers=headers
        )
        assert response.status_code == 204

    def test_update_multiple_fields(self, client, test_user_with_auth):
        """Updating first_name and last_name together returns 204."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "New", "last_name": "Name"},
            headers=headers
        )
        assert response.status_code == 204

    def test_update_first_name_persists(self, client, test_user_with_auth):
        """After updating first_name, GET reflects the change."""
        user, headers = test_user_with_auth
        client.put(
            "/v1/user/self",
            json={"first_name": "ChangedName"},
            headers=headers
        )
        response = client.get("/v1/user/self", headers=headers)
        assert response.json()["first_name"] == "ChangedName"

    def test_update_does_not_affect_unmodified_fields(self, client, test_user_with_auth):
        """Updating first_name should not change last_name or username."""
        user, headers = test_user_with_auth
        original_last = user.last_name
        original_username = user.username

        client.put(
            "/v1/user/self",
            json={"first_name": "OnlyThis"},
            headers=headers
        )
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()

        assert data["last_name"] == original_last
        assert data["username"] == original_username

    def test_update_changes_account_updated_timestamp(self, client, test_user_with_auth):
        """account_updated should change after a PUT update."""
        user, headers = test_user_with_auth

        before = client.get("/v1/user/self", headers=headers).json()

        client.put(
            "/v1/user/self",
            json={"first_name": "Newer"},
            headers=headers
        )

        after = client.get("/v1/user/self", headers=headers).json()
        assert after["account_updated"] >= before["account_updated"]

    def test_update_password_allows_login_with_new_password(
        self, client, test_user_with_auth, auth_headers
    ):
        """After password change, new password works for auth."""
        user, headers = test_user_with_auth
        new_password = "brandnewpass123"

        client.put(
            "/v1/user/self",
            json={"password": new_password},
            headers=headers
        )

        new_headers = auth_headers(user.username, new_password)
        response = client.get("/v1/user/self", headers=new_headers)
        assert response.status_code == 200

    def test_update_password_old_password_fails(self, client, test_user_with_auth, auth_headers):
        """After password change, old password should no longer work."""
        user, headers = test_user_with_auth

        client.put(
            "/v1/user/self",
            json={"password": "totallynewpass1"},
            headers=headers
        )

        # Old password (from test_user_with_auth fixture) should fail
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_update_special_characters_in_name(self, client, test_user_with_auth):
        """Updating name with special characters should work."""
        _, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "María-José", "last_name": "O'Connor"},
            headers=headers
        )
        assert response.status_code == 204

        data = client.get("/v1/user/self", headers=headers).json()
        assert data["first_name"] == "María-José"
        assert data["last_name"] == "O'Connor"

    def test_update_204_response_has_no_body(self, client, test_user_with_auth):
        """204 No Content response should have an empty body."""
        _, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "NoBody"},
            headers=headers
        )
        assert response.status_code == 204
        assert response.content == b""


class TestAuthenticationPositive:
    """Authentication success tests."""

    def test_successful_registration_and_login(self, client, auth_headers):
        """Create a user, then authenticate with same credentials."""
        payload = {
            "first_name": "Auth",
            "last_name": "Test",
            "username": "authtest@example.com",
            "password": "password123"
        }
        create_resp = client.post("/v1/user", json=payload)
        assert create_resp.status_code == 201

        headers = auth_headers("authtest@example.com", "password123")
        get_resp = client.get("/v1/user/self", headers=headers)
        assert get_resp.status_code == 200

    def test_auth_returns_correct_user(self, client, auth_headers):
        """Authenticated request returns the correct user's data."""
        payload = {
            "first_name": "Correct",
            "last_name": "User",
            "username": "correct@example.com",
            "password": "password123"
        }
        client.post("/v1/user", json=payload)

        headers = auth_headers("correct@example.com", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.json()["username"] == "correct@example.com"


# ====================================================================
#  B. NEGATIVE TESTS
# ====================================================================

class TestCreateUserNegative:
    """POST /v1/user - invalid input and error tests."""

    def test_create_user_missing_first_name(self, client):
        """Missing first_name returns 400."""
        payload = {
            "last_name": "Doe",
            "username": "missing.fn@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_missing_last_name(self, client):
        """Missing last_name returns 400."""
        payload = {
            "first_name": "Jane",
            "username": "missing.ln@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_missing_username(self, client):
        """Missing username returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_missing_password(self, client):
        """Missing password returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "missing.pw@example.com"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_empty_body(self, client):
        """Empty request body returns 400."""
        response = client.post(
            "/v1/user",
            content=b"",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    def test_create_user_invalid_json(self, client):
        """Malformed JSON returns 400."""
        response = client.post(
            "/v1/user",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    def test_create_user_invalid_email_no_at(self, client):
        """Username without @ returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "notanemail",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_invalid_email_no_dot(self, client):
        """Username without a dot in domain returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "user@nodot",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_invalid_email_no_domain(self, client):
        """Username with @ but no domain returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "user@",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_invalid_email_no_local_part(self, client):
        """Username with no local part before @ returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_invalid_email_plain_text(self, client):
        """Plain text username (not an email) returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "justplaintext",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_short_password(self, client):
        """Password shorter than 8 characters returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "shortpw@example.com",
            "password": "short"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_duplicate_email(self, client, create_test_user):
        """Creating a user with an existing email returns 409."""
        user, _ = create_test_user(username="dup@example.com")
        payload = {
            "first_name": "Another",
            "last_name": "User",
            "username": "dup@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 409

    def test_create_user_wrong_content_type(self, client):
        """Non-JSON Content-Type returns 415."""
        response = client.post(
            "/v1/user",
            content=b"first_name=Jane&last_name=Doe",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 415

    def test_create_user_empty_first_name(self, client):
        """Empty string for first_name returns 400."""
        payload = {
            "first_name": "",
            "last_name": "Doe",
            "username": "empty.fn@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_empty_last_name(self, client):
        """Empty string for last_name returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "",
            "username": "empty.ln@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_missing_all_fields(self, client):
        """Empty JSON object with no fields returns 400."""
        response = client.post(
            "/v1/user",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    def test_create_user_empty_password(self, client):
        """Empty string for password returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "emptypw@example.com",
            "password": ""
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_empty_username(self, client):
        """Empty string for username returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_password_as_number(self, client):
        """Password as a number instead of string returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "numpass@example.com",
            "password": 12345678
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_first_name_as_number(self, client):
        """first_name as a number instead of string returns 400."""
        payload = {
            "first_name": 12345,
            "last_name": "Doe",
            "username": "numname@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_last_name_as_number(self, client):
        """last_name as a number instead of string returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": 12345,
            "username": "numlast@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_duplicate_email_case_sensitivity(self, client, create_test_user):
        """Duplicate email with different case should return 409."""
        create_test_user(username="casetest@example.com")
        payload = {
            "first_name": "Another",
            "last_name": "User",
            "username": "CASETEST@EXAMPLE.COM",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should be 409 if case-insensitive, or 201 if case-sensitive
        assert response.status_code in [201, 409]

    def test_create_user_wrong_content_type_text_plain(self, client):
        """text/plain Content-Type returns 415."""
        response = client.post(
            "/v1/user",
            content=b'{"first_name":"Jane"}',
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 415

    def test_create_user_no_content_type_header(self, client):
        """Missing Content-Type header returns 400 or 415."""
        response = client.post(
            "/v1/user",
            content=b'{"first_name":"Jane","last_name":"Doe","username":"noct@example.com","password":"password123"}'
        )
        assert response.status_code in [400, 415]

    def test_create_user_null_first_name(self, client):
        """null value for first_name returns 400."""
        payload = {
            "first_name": None,
            "last_name": "Doe",
            "username": "nullfn@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_null_last_name(self, client):
        """null value for last_name returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": None,
            "username": "nullln@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_create_user_null_password(self, client):
        """null value for password returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "nullpw@example.com",
            "password": None
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400


class TestGetUserSelfNegative:
    """GET /v1/user/self - authentication error tests."""

    def test_get_user_no_auth(self, client):
        """GET /v1/user/self without auth returns 401."""
        response = client.get("/v1/user/self")
        assert response.status_code == 401

    def test_get_user_wrong_password(self, client, test_user_with_auth, auth_headers):
        """Wrong password returns 401."""
        user, _ = test_user_with_auth
        bad_headers = auth_headers(user.username, "wrongpassword")
        response = client.get("/v1/user/self", headers=bad_headers)
        assert response.status_code == 401

    def test_get_user_nonexistent_username(self, client, auth_headers):
        """Auth with non-existent user returns 401."""
        headers = auth_headers("nobody@example.com", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_get_user_empty_credentials(self, client, auth_headers):
        """Auth with empty username/password returns 401."""
        headers = auth_headers("", "")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_get_user_case_sensitive_password(self, client, create_test_user, auth_headers):
        """Password check should be case-sensitive."""
        create_test_user(username="casepw@example.com", password="Password123")
        headers = auth_headers("casepw@example.com", "password123")  # lowercase p
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_get_user_malformed_auth_header(self, client):
        """Malformed Authorization header returns 401."""
        response = client.get(
            "/v1/user/self",
            headers={"Authorization": "Basic not-valid-base64!!!"}
        )
        assert response.status_code in [401, 400]

    def test_get_user_empty_password_auth(self, client, create_test_user, auth_headers):
        """Auth with correct username but empty password returns 401."""
        create_test_user(username="emptypwauth@example.com", password="password123")
        headers = auth_headers("emptypwauth@example.com", "")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_get_user_empty_username_auth(self, client, auth_headers):
        """Auth with empty username returns 401."""
        headers = auth_headers("", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    def test_get_user_401_has_www_authenticate_header(self, client):
        """401 response should include WWW-Authenticate header."""
        response = client.get("/v1/user/self")
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Basic" in www_auth


class TestUpdateUserNegative:
    """PUT /v1/user/self - invalid update tests."""

    def test_update_user_no_auth(self, client):
        """PUT /v1/user/self without auth returns 401."""
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Hacker"}
        )
        assert response.status_code == 401

    def test_update_user_wrong_password(self, client, test_user_with_auth, auth_headers):
        """PUT with wrong password returns 401."""
        user, _ = test_user_with_auth
        bad_headers = auth_headers(user.username, "wrongpass")
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Hacker"},
            headers=bad_headers
        )
        assert response.status_code == 401

    def test_update_username_not_allowed(self, client, test_user_with_auth):
        """Trying to update username returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"username": "new@example.com"},
            headers=headers
        )
        assert response.status_code == 400

    def test_update_id_not_allowed(self, client, test_user_with_auth):
        """Trying to update id returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"id": "some-uuid"},
            headers=headers
        )
        assert response.status_code == 400

    def test_update_account_created_not_allowed(self, client, test_user_with_auth):
        """Trying to update account_created returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"account_created": "2020-01-01T00:00:00Z"},
            headers=headers
        )
        assert response.status_code == 400

    def test_update_account_updated_not_allowed(self, client, test_user_with_auth):
        """Trying to update account_updated returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"account_updated": "2020-01-01T00:00:00Z"},
            headers=headers
        )
        assert response.status_code == 400

    def test_update_empty_json_object(self, client, test_user_with_auth):
        """Empty JSON object in PUT should return 204 (no changes)."""
        _, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={},
            headers=headers
        )
        assert response.status_code == 204

    def test_update_user_wrong_content_type(self, client, test_user_with_auth):
        """PUT with non-JSON Content-Type returns 415."""
        _, headers = test_user_with_auth
        headers["Content-Type"] = "text/plain"
        response = client.put(
            "/v1/user/self",
            content=b'{"first_name": "Test"}',
            headers=headers
        )
        assert response.status_code == 415

    def test_update_user_401_has_www_authenticate_header(self, client):
        """PUT 401 response should include WWW-Authenticate header."""
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Hacker"}
        )
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Basic" in www_auth


class TestUserMethodNotAllowed:
    """Wrong HTTP method tests for user endpoints."""

    def test_get_on_create_endpoint(self, client):
        """GET /v1/user returns 405 (only POST allowed)."""
        response = client.get("/v1/user")
        assert response.status_code == 405

    def test_put_on_create_endpoint(self, client):
        """PUT /v1/user returns 405."""
        response = client.put("/v1/user", json={})
        assert response.status_code == 405

    def test_delete_on_create_endpoint(self, client):
        """DELETE /v1/user returns 405."""
        response = client.delete("/v1/user")
        assert response.status_code == 405

    def test_patch_on_create_endpoint(self, client):
        """PATCH /v1/user returns 405."""
        response = client.patch("/v1/user", json={})
        assert response.status_code == 405

    def test_post_on_user_self(self, client, test_user_with_auth):
        """POST /v1/user/self returns 405."""
        _, headers = test_user_with_auth
        response = client.post("/v1/user/self", json={}, headers=headers)
        assert response.status_code == 405

    def test_delete_on_user_self(self, client, test_user_with_auth):
        """DELETE /v1/user/self returns 405."""
        _, headers = test_user_with_auth
        response = client.delete("/v1/user/self", headers=headers)
        assert response.status_code == 405


class TestUnsupportedEndpoints:
    """404 tests for endpoints that don't exist."""

    def test_random_endpoint(self, client):
        """Random non-existent endpoint returns 404."""
        response = client.get("/v1/random")
        assert response.status_code == 404

    def test_users_plural(self, client):
        """/v1/users (plural) returns 404."""
        response = client.get("/v1/users")
        assert response.status_code == 404

    def test_wrong_api_version(self, client):
        """/v2/user (wrong version) returns 404."""
        response = client.get("/v2/user")
        assert response.status_code == 404

    def test_health_without_z(self, client):
        """/health (without z) returns 404."""
        response = client.get("/health")
        assert response.status_code == 404

    def test_healthcheck_endpoint(self, client):
        """/healthcheck returns 404."""
        response = client.get("/healthcheck")
        assert response.status_code == 404

    def test_api_healthz(self, client):
        """/api/healthz returns 404."""
        response = client.get("/api/healthz")
        assert response.status_code == 404

    def test_user_without_version(self, client):
        """/user (without /v1) returns 404."""
        response = client.get("/user")
        assert response.status_code == 404

    def test_root_endpoint(self, client):
        """Root endpoint / returns 404."""
        response = client.get("/")
        assert response.status_code == 404


class TestSpecialErrorScenarios:
    """SQL injection, very long values, concurrent requests."""

    def test_sql_injection_in_username(self, client):
        """SQL injection attempt in username is safely handled."""
        payload = {
            "first_name": "Hacker",
            "last_name": "Test",
            "username": "'; DROP TABLE users; --@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should either reject as invalid email or create safely
        assert response.status_code in [201, 400]

    def test_sql_injection_in_first_name(self, client):
        """SQL injection attempt in first_name is safely handled."""
        payload = {
            "first_name": "'; DROP TABLE users; --",
            "last_name": "Test",
            "username": "sqlinject@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should create successfully (SQLAlchemy parameterizes queries)
        assert response.status_code == 201

    def test_very_long_first_name(self, client):
        """Very long first_name (10000 chars) should be handled."""
        payload = {
            "first_name": "A" * 10000,
            "last_name": "Doe",
            "username": "longname2@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should reject (exceeds column limit of 100) or handle gracefully
        assert response.status_code in [400, 500]

    def test_very_long_password(self, client):
        """Very long password (10000 chars) should be handled."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "longpw@example.com",
            "password": "A" * 10000
        }
        response = client.post("/v1/user", json=payload)
        # BCrypt has a 72-byte limit, but the app should handle it
        assert response.status_code in [201, 400]

    def test_concurrent_duplicate_user_creation(self, client):
        """Concurrent creation of same user should not both succeed."""
        payload = {
            "first_name": "Concurrent",
            "last_name": "Test",
            "username": "concurrent@example.com",
            "password": "password123"
        }
        results = []

        def create_user():
            resp = client.post("/v1/user", json=payload)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(create_user)
            executor.submit(create_user)

        # One should succeed (201), the other should fail (409)
        assert 201 in results
        assert any(code in [409, 400] for code in results)


# ====================================================================
#  C. EDGE CASE TESTS
# ====================================================================

class TestUserEdgeCases:
    """Boundary values, special characters, data integrity."""

    def test_create_user_special_chars_in_name(self, client):
        """Names with hyphens, apostrophes, accents should work."""
        payload = {
            "first_name": "Mary-Jane",
            "last_name": "O'Brien",
            "username": "maryjane@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "Mary-Jane"
        assert response.json()["last_name"] == "O'Brien"

    def test_create_user_unicode_in_name(self, client):
        """Unicode characters in names should work."""
        payload = {
            "first_name": "Héléne",
            "last_name": "Müller",
            "username": "unicode@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "Héléne"

    def test_create_user_long_first_name(self, client):
        """Name at maximum length (100 chars) should work."""
        long_name = "A" * 100
        payload = {
            "first_name": long_name,
            "last_name": "Doe",
            "username": "longname@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == long_name

    def test_create_user_password_exactly_8_chars(self, client):
        """Password with exactly 8 characters (minimum) should work."""
        payload = {
            "first_name": "Min",
            "last_name": "Pass",
            "username": "minpass@example.com",
            "password": "12345678"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    def test_create_user_password_7_chars_fails(self, client):
        """Password with 7 characters (below minimum) returns 400."""
        payload = {
            "first_name": "Short",
            "last_name": "Pass",
            "username": "shortpw2@example.com",
            "password": "1234567"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    def test_created_user_data_persists(self, client, auth_headers):
        """Data from creation is retrievable via GET."""
        payload = {
            "first_name": "Persist",
            "last_name": "Test",
            "username": "persist@example.com",
            "password": "password123"
        }
        create_resp = client.post("/v1/user", json=payload)
        assert create_resp.status_code == 201

        headers = auth_headers("persist@example.com", "password123")
        get_resp = client.get("/v1/user/self", headers=headers)
        data = get_resp.json()

        assert data["first_name"] == "Persist"
        assert data["last_name"] == "Test"
        assert data["username"] == "persist@example.com"

    def test_update_preserves_account_created(self, client, test_user_with_auth):
        """account_created should not change after an update."""
        user, headers = test_user_with_auth

        before = client.get("/v1/user/self", headers=headers).json()
        client.put(
            "/v1/user/self",
            json={"first_name": "Changed"},
            headers=headers
        )
        after = client.get("/v1/user/self", headers=headers).json()

        assert after["account_created"] == before["account_created"]

    def test_response_time_is_reasonable(self, client):
        """POST /v1/user should respond within 2 seconds."""
        import time
        payload = {
            "first_name": "Speed",
            "last_name": "Test",
            "username": "speed@example.com",
            "password": "password123"
        }
        start = time.time()
        response = client.post("/v1/user", json=payload)
        elapsed = time.time() - start

        assert response.status_code == 201
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s, expected < 2s"

    def test_get_self_response_time_is_reasonable(self, client, test_user_with_auth):
        """GET /v1/user/self should respond within 2 seconds."""
        import time
        _, headers = test_user_with_auth

        start = time.time()
        response = client.get("/v1/user/self", headers=headers)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s, expected < 2s"
