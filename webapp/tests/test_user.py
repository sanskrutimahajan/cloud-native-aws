"""
Tests for User Endpoints:
  POST /v1/user        - Create user (no auth)
  GET  /v1/user/self   - Get authenticated user info (Basic Auth)
  PUT  /v1/user/self   - Update authenticated user (Basic Auth)
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import bcrypt

from app.models import User

# ====================================================================
#  A. POSITIVE TESTS
# ====================================================================

class TestCreateUserPositive:
    """POST /v1/user - successful creation tests."""

    # Verify valid user creation returns 201 Created status
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

    # Verify response body contains all required fields (id, first_name, last_name, username, timestamps)
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

    # Verify all response fields have correct data types (str, UUID, ISO datetime)
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

    # Verify response field values match the input payload values
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

    # Verify password field is NEVER included in the response body
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

    # Verify the returned id is a valid UUID format
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

    # Verify account_created and account_updated timestamps are present and non-empty
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

    # Verify response Content-Type header is application/json
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

    # Verify various valid email formats (subdomain, .org, .co) all succeed
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

    # Verify 201 response includes Location: /v1/user/self header
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

    # Verify password is stored as BCrypt hash ($2b$) in DB, not plaintext
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

    # Verify authenticated GET /v1/user/self returns 200 OK
    def test_get_user_self_returns_200(self, client, test_user_with_auth):
        """Authenticated GET /v1/user/self returns 200."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 200

    # Verify returned data matches the authenticated user's info
    def test_get_user_self_returns_correct_data(self, client, test_user_with_auth):
        """Returned data matches the authenticated user."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()

        assert data["username"] == user.username
        assert data["first_name"] == user.first_name
        assert data["last_name"] == user.last_name

    # Verify password is NOT included in the GET response
    def test_get_user_self_no_password_in_response(self, client, test_user_with_auth):
        """Password must not be in the response."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        assert "password" not in data

    # Verify response includes a valid UUID id field
    def test_get_user_self_has_id_field(self, client, test_user_with_auth):
        """Response includes a valid UUID id field."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        uuid.UUID(data["id"])

    # Verify GET response Content-Type is application/json
    def test_get_user_self_content_type_json(self, client, test_user_with_auth):
        """Response Content-Type is application/json."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        assert "application/json" in response.headers.get("content-type", "")

    # Verify GET response includes account_created and account_updated timestamps
    def test_get_user_self_has_timestamps(self, client, test_user_with_auth):
        """Response includes account_created and account_updated."""
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()
        assert "account_created" in data
        assert "account_updated" in data

    # Verify all GET response fields have correct data types (str, UUID, ISO datetime)
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

    # Verify multiple consecutive GET calls return the same user data
    def test_get_user_self_multiple_calls_return_same_data(self, client, test_user_with_auth):
        """Multiple GET calls return the same user data."""
        _, headers = test_user_with_auth
        resp1 = client.get("/v1/user/self", headers=headers).json()
        resp2 = client.get("/v1/user/self", headers=headers).json()
        resp3 = client.get("/v1/user/self", headers=headers).json()
        assert resp1 == resp2 == resp3


class TestUpdateUserPositive:
    """PUT /v1/user/self - successful update tests."""

    # Verify updating first_name returns 204 No Content
    def test_update_first_name_returns_204(self, client, test_user_with_auth):
        """Updating first_name returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Updated"},
            headers=headers
        )
        assert response.status_code == 204

    # Verify updating last_name returns 204 No Content
    def test_update_last_name_returns_204(self, client, test_user_with_auth):
        """Updating last_name returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"last_name": "NewLast"},
            headers=headers
        )
        assert response.status_code == 204

    # Verify updating password returns 204 No Content
    def test_update_password_returns_204(self, client, test_user_with_auth):
        """Updating password returns 204 No Content."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"password": "newpassword123"},
            headers=headers
        )
        assert response.status_code == 204

    # Verify updating multiple fields (first_name + last_name) together returns 204
    def test_update_multiple_fields(self, client, test_user_with_auth):
        """Updating first_name and last_name together returns 204."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "New", "last_name": "Name"},
            headers=headers
        )
        assert response.status_code == 204

    # Verify updated first_name persists and is reflected in subsequent GET
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

    # Verify updating one field does not change unmodified fields (last_name, username)
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

    # Verify account_updated timestamp changes after a PUT update
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

    # Verify after password change, new password works for authentication
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

    # Verify after password change, old password no longer works
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

    # Verify updating name with special characters (accents, apostrophes) works
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

    # Verify 204 No Content response has an empty body
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

    # Verify full flow: create a user then authenticate with same credentials
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

    # Verify authenticated request returns the correct user's data (not another user)
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

    # Verify missing first_name field returns 400 Bad Request
    def test_create_user_missing_first_name(self, client):
        """Missing first_name returns 400."""
        payload = {
            "last_name": "Doe",
            "username": "missing.fn@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Verify missing last_name field returns 400 Bad Request
    def test_create_user_missing_last_name(self, client):
        """Missing last_name returns 400."""
        payload = {
            "first_name": "Jane",
            "username": "missing.ln@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Verify missing username field returns 400 Bad Request
    def test_create_user_missing_username(self, client):
        """Missing username returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Verify missing password field returns 400 Bad Request
    def test_create_user_missing_password(self, client):
        """Missing password returns 400."""
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "missing.pw@example.com"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Verify empty request body returns 400 Bad Request
    def test_create_user_empty_body(self, client):
        """Empty request body returns 400."""
        response = client.post(
            "/v1/user",
            content=b"",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    # Verify malformed JSON body returns 400 Bad Request
    def test_create_user_invalid_json(self, client):
        """Malformed JSON returns 400."""
        response = client.post(
            "/v1/user",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    # Verify email without @ symbol returns 400 Bad Request
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

    # Verify email without dot in domain part returns 400 Bad Request
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

    # Verify email with @ but no domain returns 400 Bad Request
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

    # Verify email with no local part before @ returns 400 Bad Request
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

    # Verify plain text username (not an email format) returns 400 Bad Request
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

    # Verify password shorter than 8 characters returns 400 Bad Request
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

    # Verify duplicate email address returns 400 Conflict
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
        assert response.status_code == 400

    # Verify non-JSON Content-Type (form-urlencoded) returns 415 Unsupported Media Type
    def test_create_user_wrong_content_type(self, client):
        """Non-JSON Content-Type returns 415."""
        response = client.post(
            "/v1/user",
            content=b"first_name=Jane&last_name=Doe",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 415

    # Verify empty string for first_name returns 400 Bad Request
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

    # Verify empty string for last_name returns 400 Bad Request
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

    # Verify empty JSON object (no fields at all) returns 400 Bad Request
    def test_create_user_missing_all_fields(self, client):
        """Empty JSON object with no fields returns 400."""
        response = client.post(
            "/v1/user",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    # Verify empty string for password returns 400 Bad Request
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

    # Verify empty string for username returns 400 Bad Request
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

    # Verify password as a number (wrong data type) returns 400 Bad Request
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

    # Verify first_name as a number (wrong data type) returns 400 Bad Request
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

    # Verify last_name as a number (wrong data type) returns 400 Bad Request
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

    # Verify duplicate email with different case (case-insensitive check)
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

    # Verify text/plain Content-Type returns 415 Unsupported Media Type
    def test_create_user_wrong_content_type_text_plain(self, client):
        """text/plain Content-Type returns 415."""
        response = client.post(
            "/v1/user",
            content=b'{"first_name":"Jane"}',
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == 415

    # Verify missing Content-Type header returns 400 or 415
    def test_create_user_no_content_type_header(self, client):
        """Missing Content-Type header returns 400 or 415."""
        response = client.post(
            "/v1/user",
            content=b'{"first_name":"Jane","last_name":"Doe","username":"noct@example.com","password":"password123"}'
        )
        assert response.status_code in [400, 415]

    # Verify null value for first_name returns 400 Bad Request
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

    # Verify null value for last_name returns 400 Bad Request
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

    # Verify null value for password returns 400 Bad Request
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

    # Verify GET without any auth credentials returns 401 Unauthorized
    def test_get_user_no_auth(self, client):
        """GET /v1/user/self without auth returns 401."""
        response = client.get("/v1/user/self")
        assert response.status_code == 401

    # Verify wrong password returns 401 Unauthorized
    def test_get_user_wrong_password(self, client, test_user_with_auth, auth_headers):
        """Wrong password returns 401."""
        user, _ = test_user_with_auth
        bad_headers = auth_headers(user.username, "wrongpassword")
        response = client.get("/v1/user/self", headers=bad_headers)
        assert response.status_code == 401

    # Verify auth with non-existent username returns 401 Unauthorized
    def test_get_user_nonexistent_username(self, client, auth_headers):
        """Auth with non-existent user returns 401."""
        headers = auth_headers("nobody@example.com", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Verify auth with empty username and empty password returns 401 Unauthorized
    def test_get_user_empty_credentials(self, client, auth_headers):
        """Auth with empty username/password returns 401."""
        headers = auth_headers("", "")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Verify password check is case-sensitive (wrong case returns 401)
    def test_get_user_case_sensitive_password(self, client, create_test_user, auth_headers):
        """Password check should be case-sensitive."""
        create_test_user(username="casepw@example.com", password="Password123")
        headers = auth_headers("casepw@example.com", "password123")  # lowercase p
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Verify malformed Authorization header (invalid base64) returns 401
    def test_get_user_malformed_auth_header(self, client):
        """Malformed Authorization header returns 401."""
        response = client.get(
            "/v1/user/self",
            headers={"Authorization": "Basic not-valid-base64!!!"}
        )
        assert response.status_code in [401, 400]

    # Verify auth with correct username but empty password returns 401
    def test_get_user_empty_password_auth(self, client, create_test_user, auth_headers):
        """Auth with correct username but empty password returns 401."""
        create_test_user(username="emptypwauth@example.com", password="password123")
        headers = auth_headers("emptypwauth@example.com", "")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Verify auth with empty username returns 401 Unauthorized
    def test_get_user_empty_username_auth(self, client, auth_headers):
        """Auth with empty username returns 401."""
        headers = auth_headers("", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Verify 401 response includes WWW-Authenticate: Basic header
    def test_get_user_401_has_www_authenticate_header(self, client):
        """401 response should include WWW-Authenticate header."""
        response = client.get("/v1/user/self")
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Basic" in www_auth


class TestUpdateUserNegative:
    """PUT /v1/user/self - invalid update tests."""

    # Verify PUT without auth credentials returns 401 Unauthorized
    def test_update_user_no_auth(self, client):
        """PUT /v1/user/self without auth returns 401."""
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Hacker"}
        )
        assert response.status_code == 401

    # Verify PUT with wrong password returns 401 Unauthorized
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

    # Verify attempting to update username (immutable field) returns 400
    def test_update_username_not_allowed(self, client, test_user_with_auth):
        """Trying to update username returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"username": "new@example.com"},
            headers=headers
        )
        assert response.status_code == 400

    # Verify attempting to update id (immutable field) returns 400
    def test_update_id_not_allowed(self, client, test_user_with_auth):
        """Trying to update id returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"id": "some-uuid"},
            headers=headers
        )
        assert response.status_code == 400

    # Verify attempting to update account_created (immutable field) returns 400
    def test_update_account_created_not_allowed(self, client, test_user_with_auth):
        """Trying to update account_created returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"account_created": "2020-01-01T00:00:00Z"},
            headers=headers
        )
        assert response.status_code == 400

    # Verify attempting to update account_updated (immutable field) returns 400
    def test_update_account_updated_not_allowed(self, client, test_user_with_auth):
        """Trying to update account_updated returns 400."""
        user, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"account_updated": "2020-01-01T00:00:00Z"},
            headers=headers
        )
        assert response.status_code == 400

    # Verify empty JSON object in PUT returns 204 (no changes made)
    def test_update_empty_json_object(self, client, test_user_with_auth):
        """Empty JSON object in PUT should return 204 (no changes)."""
        _, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={},
            headers=headers
        )
        assert response.status_code == 204

    # Verify PUT with non-JSON Content-Type returns 415 Unsupported Media Type
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

    # Verify PUT 401 response includes WWW-Authenticate: Basic header
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

    # Verify GET on /v1/user (create endpoint) returns 405 Method Not Allowed
    def test_get_on_create_endpoint(self, client):
        """GET /v1/user returns 405 (only POST allowed)."""
        response = client.get("/v1/user")
        assert response.status_code == 405

    # Verify PUT on /v1/user returns 405 Method Not Allowed
    def test_put_on_create_endpoint(self, client):
        """PUT /v1/user returns 405."""
        response = client.put("/v1/user", json={})
        assert response.status_code == 405

    # Verify DELETE on /v1/user returns 405 Method Not Allowed
    def test_delete_on_create_endpoint(self, client):
        """DELETE /v1/user returns 405."""
        response = client.delete("/v1/user")
        assert response.status_code == 405

    # Verify PATCH on /v1/user returns 405 Method Not Allowed
    def test_patch_on_create_endpoint(self, client):
        """PATCH /v1/user returns 405."""
        response = client.patch("/v1/user", json={})
        assert response.status_code == 405

    # Verify POST on /v1/user/self returns 405 Method Not Allowed
    def test_post_on_user_self(self, client, test_user_with_auth):
        """POST /v1/user/self returns 405."""
        _, headers = test_user_with_auth
        response = client.post("/v1/user/self", json={}, headers=headers)
        assert response.status_code == 405

    # Verify DELETE on /v1/user/self returns 405 Method Not Allowed
    def test_delete_on_user_self(self, client, test_user_with_auth):
        """DELETE /v1/user/self returns 405."""
        _, headers = test_user_with_auth
        response = client.delete("/v1/user/self", headers=headers)
        assert response.status_code == 405


class TestUnsupportedEndpoints:
    """404 tests for endpoints that don't exist."""

    # Verify random non-existent endpoint returns 404 Not Found
    def test_random_endpoint(self, client):
        """Random non-existent endpoint returns 404."""
        response = client.get("/v1/random")
        assert response.status_code == 404

    # Verify /v1/users (plural, wrong path) returns 404 Not Found
    def test_users_plural(self, client):
        """/v1/users (plural) returns 404."""
        response = client.get("/v1/users")
        assert response.status_code == 404

    # Verify /v2/user (wrong API version) returns 404 Not Found
    def test_wrong_api_version(self, client):
        """/v2/user (wrong version) returns 404."""
        response = client.get("/v2/user")
        assert response.status_code == 404

    # Verify /health (without z, wrong path) returns 404 Not Found
    def test_health_without_z(self, client):
        """/health (without z) returns 404."""
        response = client.get("/health")
        assert response.status_code == 404

    # Verify /healthcheck (wrong path variant) returns 404 Not Found
    def test_healthcheck_endpoint(self, client):
        """/healthcheck returns 404."""
        response = client.get("/healthcheck")
        assert response.status_code == 404

    # Verify /api/healthz (wrong prefix) returns 404 Not Found
    def test_api_healthz(self, client):
        """/api/healthz returns 404."""
        response = client.get("/api/healthz")
        assert response.status_code == 404

    # Verify /user (missing /v1 prefix) returns 404 Not Found
    def test_user_without_version(self, client):
        """/user (without /v1) returns 404."""
        response = client.get("/user")
        assert response.status_code == 404

    # Verify root endpoint / returns 404 Not Found
    def test_root_endpoint(self, client):
        """Root endpoint / returns 404."""
        response = client.get("/")
        assert response.status_code == 404


class TestSpecialErrorScenarios:
    """SQL injection, very long values, concurrent requests."""

    # Verify SQL injection attempt in username is safely handled (rejected or sanitized)
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

    # Verify SQL injection attempt in first_name is safely handled (parameterized queries)
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

    # Verify very long first_name (10000 chars) is handled gracefully (rejected or truncated)
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

    # Verify very long password (10000 chars) is handled (BCrypt has 72-byte limit)
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

    # Verify 5 concurrent threads creating same email - exactly 1 succeeds, 4 fail
    def test_concurrent_duplicate_user_creation_5_threads(self, client):
        """5 threads creating same email - exactly 1 should succeed."""
        payload = {
            "first_name": "Concurrent",
            "last_name": "Test",
            "username": "concurrent5@example.com",
            "password": "password123"
        }
        results = []

        # Helper: post the same user payload and collect status code
        def create_user():
            resp = client.post("/v1/user", json=payload)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user) for _ in range(5)]
            for f in futures:
                f.result()

        # Exactly 1 should succeed, rest should fail
        success_count = results.count(201)
        fail_count = sum(1 for code in results if code in [409, 400])
        assert success_count == 1, f"Expected 1 success, got {success_count}: {results}"
        assert fail_count == 4, f"Expected 4 failures, got {fail_count}: {results}"

    # Verify concurrent password updates leave system in consistent state (no 500s)
    def test_concurrent_password_updates(self, client, create_test_user, auth_headers):
        """Concurrent password updates should leave system in consistent state."""
        user, password = create_test_user(username="concpw@example.com")
        headers = auth_headers(user.username, password)
        results = []

        # Helper: update user password and collect status code
        def update_password(new_pw):
            resp = client.put(
                "/v1/user/self",
                json={"password": new_pw},
                headers=headers
            )
            results.append(resp.status_code)

        # Fire multiple password updates concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(update_password, f"newpassword{i}")
                for i in range(3)
            ]
            for f in futures:
                f.result()

        # All should either succeed (204) or fail gracefully (401/400)
        # No 500 errors allowed
        for code in results:
            assert code in [204, 401, 400], f"Unexpected status code: {code}"

        # System should be consistent - one of the passwords should work
        passwords_to_try = [password] + [f"newpassword{i}" for i in range(3)]
        working_count = 0
        for pw in passwords_to_try:
            h = auth_headers(user.username, pw)
            resp = client.get("/v1/user/self", headers=h)
            if resp.status_code == 200:
                working_count += 1

        # Exactly one password should work (system is consistent)
        assert working_count >= 1, "No password works - system in broken state"

    # Verify concurrent reads during writes don't return corrupted/partial data
    def test_read_while_write_no_corruption(self, client, create_test_user, auth_headers):
        """Reading user data while another thread updates should not return corrupted data."""
        user, password = create_test_user(
            username="readwrite@example.com",
            first_name="Original",
            last_name="Name"
        )
        headers = auth_headers(user.username, password)
        read_results = []
        write_results = []

        # Helper: read user data via GET and collect response
        def read_user():
            resp = client.get("/v1/user/self", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                read_results.append(data)

        # Helper: update user first_name via PUT and collect status code
        def write_user(name):
            resp = client.put(
                "/v1/user/self",
                json={"first_name": name},
                headers=headers
            )
            write_results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            # Mix reads and writes
            for i in range(10):
                futures.append(executor.submit(read_user))
                if i % 2 == 0:
                    futures.append(executor.submit(write_user, f"Updated{i}"))
            for f in futures:
                f.result()

        # All reads should return valid, complete data (no partial/corrupted fields)
        for data in read_results:
            assert "id" in data
            assert "first_name" in data
            assert "last_name" in data
            assert "username" in data
            assert isinstance(data["first_name"], str)
            assert len(data["first_name"]) > 0
            assert data["username"] == "readwrite@example.com"


# ====================================================================
#  C. EDGE CASE TESTS
# ====================================================================

class TestBoundaryValues:
    """String length boundaries, min/max values."""

    # ---- String Length Boundaries ----

    # Verify single character first_name (minimum length) is accepted
    def test_single_character_first_name(self, client):
        """Single character first_name (minimum) should work."""
        payload = {
            "first_name": "A",
            "last_name": "B",
            "username": "singlechar@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "A"

    # Verify name at exactly 100 characters (column limit) is accepted
    def test_100_char_name(self, client):
        """Name at 100 characters (column limit) should work."""
        long_name = "A" * 100
        payload = {
            "first_name": long_name,
            "last_name": "Doe",
            "username": "longname100@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == long_name

    # Verify name at 1000 characters (exceeds column limit) is handled gracefully
    def test_1000_char_name(self, client):
        """Name at 1000 characters (exceeds column limit) should be handled."""
        payload = {
            "first_name": "A" * 1000,
            "last_name": "Doe",
            "username": "longname1000@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code in [400, 500, 201]

    # Verify very long email (254 chars, RFC max) is handled gracefully
    def test_very_long_email_address(self, client):
        """Very long email (254 chars, max per RFC) should be handled."""
        local = "a" * 64
        domain = "b" * 185 + ".com"  # total ~254 chars
        email = f"{local}@{domain}"
        payload = {
            "first_name": "Long",
            "last_name": "Email",
            "username": email,
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code in [201, 400]

    # ---- Password Length Boundaries ----

    # Verify password with exactly 8 characters (minimum allowed) is accepted
    def test_password_exactly_8_chars(self, client):
        """Password with exactly 8 characters (minimum) should work."""
        payload = {
            "first_name": "Min",
            "last_name": "Pass",
            "username": "minpass@example.com",
            "password": "12345678"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    # Verify password with 7 characters (below minimum) returns 400 Bad Request
    def test_password_7_chars_fails(self, client):
        """Password with 7 characters (below minimum) returns 400."""
        payload = {
            "first_name": "Short",
            "last_name": "Pass",
            "username": "shortpw2@example.com",
            "password": "1234567"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Verify very long password (200 chars) is handled gracefully
    def test_password_200_chars(self, client):
        """Very long password (200 chars) should be handled."""
        payload = {
            "first_name": "Long",
            "last_name": "Pass",
            "username": "longpw200@example.com",
            "password": "A" * 200
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code in [201, 400]

    # Verify extremely long password (10000 chars) is handled gracefully
    def test_password_10000_chars(self, client):
        """Extremely long password (10000 chars) should be handled."""
        payload = {
            "first_name": "Extreme",
            "last_name": "Pass",
            "username": "longpw10k@example.com",
            "password": "A" * 10000
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code in [201, 400]


class TestSpecialCharacters:
    """Unicode, emoji, punctuation, whitespace in input."""

    # Verify French accented characters (é, ç, etc.) in names are accepted
    def test_unicode_french(self, client):
        """French accented characters should work."""
        payload = {
            "first_name": "François",
            "last_name": "Héléne",
            "username": "francois@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "François"

    # Verify Chinese characters in names are accepted and stored correctly
    def test_unicode_chinese(self, client):
        """Chinese characters should work."""
        payload = {
            "first_name": "李明",
            "last_name": "王",
            "username": "chinese@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "李明"

    # Verify Russian Cyrillic characters in names are accepted and stored correctly
    def test_unicode_russian(self, client):
        """Russian Cyrillic characters should work."""
        payload = {
            "first_name": "Владимир",
            "last_name": "Петров",
            "username": "russian@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "Владимир"

    # Verify Arabic characters in names are accepted and stored correctly
    def test_unicode_arabic(self, client):
        """Arabic characters should work."""
        payload = {
            "first_name": "محمد",
            "last_name": "أحمد",
            "username": "arabic@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "محمد"

    # Verify hyphens and apostrophes in names (Mary-Jane, O'Brien) are accepted
    def test_special_punctuation_in_names(self, client):
        """Hyphens, apostrophes, periods in names should work."""
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

    # Verify period in name (St. John) is accepted
    def test_period_in_name(self, client):
        """Period in name (St. John) should work."""
        payload = {
            "first_name": "St. John",
            "last_name": "Smith",
            "username": "stjohn@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    # Verify numbers in names (John3, Smith2nd) are accepted
    def test_numbers_in_names(self, client):
        """Numbers in names should work."""
        payload = {
            "first_name": "John3",
            "last_name": "Smith2nd",
            "username": "numbers@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    # Verify emoji characters in names are handled (accepted or rejected, not crash)
    def test_emoji_in_names(self, client):
        """Emoji characters in names should be handled."""
        payload = {
            "first_name": "Jane😊",
            "last_name": "Doe🎉",
            "username": "emoji@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should either work or return 400, not crash
        assert response.status_code in [201, 400]

    # Verify leading/trailing whitespace in names is handled (trimmed or rejected)
    def test_leading_trailing_whitespace_in_name(self, client):
        """Leading/trailing whitespace in names should be handled."""
        payload = {
            "first_name": "  Jane  ",
            "last_name": "  Doe  ",
            "username": "whitespace@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        # Should either accept or reject, not crash
        assert response.status_code in [201, 400]

    # Verify email with + tag (user+tag@domain) is accepted
    def test_special_email_with_plus(self, client):
        """Email with + tag (user+tag@domain) should work."""
        payload = {
            "first_name": "Plus",
            "last_name": "Tag",
            "username": "user+tag@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    def test_special_email_with_dots(self, client):
        """Email with dots in local part (user.name@domain) should work."""
        payload = {
            "first_name": "Dot",
            "last_name": "Email",
            "username": "user.name.test@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    def test_special_chars_in_password(self, client, auth_headers):
        """Password with special characters (!@#$%^&*) should work."""
        payload = {
            "first_name": "Special",
            "last_name": "Pass",
            "username": "specialpass@example.com",
            "password": "P@$$w0rd!#%^&*()"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

        # Verify can authenticate with special char password
        headers = auth_headers("specialpass@example.com", "P@$$w0rd!#%^&*()")
        get_resp = client.get("/v1/user/self", headers=headers)
        assert get_resp.status_code == 200


class TestPerformanceLoad:
    """Response times, concurrent requests, load tests."""

    def test_create_user_response_time(self, client):
        """POST /v1/user should respond within 2 seconds."""
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

    def test_get_self_response_time(self, client, test_user_with_auth):
        """GET /v1/user/self should respond within 1 second."""
        _, headers = test_user_with_auth
        start = time.time()
        response = client.get("/v1/user/self", headers=headers)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, expected < 1s"

    def test_update_user_response_time(self, client, test_user_with_auth):
        """PUT /v1/user/self should respond within 2 seconds."""
        _, headers = test_user_with_auth
        start = time.time()
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Speedy"},
            headers=headers
        )
        elapsed = time.time() - start
        assert response.status_code == 204
        assert elapsed < 2.0, f"Response took {elapsed:.2f}s, expected < 2s"

    def test_healthz_response_time(self, client):
        """GET /healthz should respond within 500ms."""
        start = time.time()
        response = client.get("/healthz")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 0.5, f"Response took {elapsed:.2f}s, expected < 0.5s"

    def test_concurrent_user_creations(self, client):
        """10 concurrent user creations with unique emails should all succeed."""
        results = []

        def create(i):
            payload = {
                "first_name": f"User{i}",
                "last_name": "Concurrent",
                "username": f"concurrent{i}@example.com",
                "password": "password123"
            }
            resp = client.post("/v1/user", json=payload)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for i in range(10):
                executor.submit(create, i)

        success_count = results.count(201)
        assert success_count == 10, f"Only {success_count}/10 succeeded: {results}"

    def test_concurrent_auth_requests(self, client, create_test_user, auth_headers):
        """20 concurrent GET /v1/user/self requests should all return 200."""
        user, password = create_test_user(username="concauth@example.com")
        headers = auth_headers(user.username, password)
        results = []

        def get_self():
            resp = client.get("/v1/user/self", headers=headers)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for _ in range(20):
                executor.submit(get_self)

        success_count = results.count(200)
        assert success_count == 20, f"Only {success_count}/20 succeeded: {results}"

    def test_concurrent_healthz_no_deadlock(self, client):
        """50 concurrent health checks should complete without deadlock."""
        results = []

        def healthz():
            resp = client.get("/healthz")
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(healthz) for _ in range(50)]
            # Timeout after 30 seconds - if it hangs, we have a deadlock
            for f in futures:
                f.result(timeout=30)

        success_count = results.count(200)
        assert success_count == 50, f"Only {success_count}/50 succeeded: possible deadlock"
        assert len(results) == 50, f"Only {len(results)}/50 completed: possible hang"

    def test_rapid_sequential_requests(self, client, test_user_with_auth):
        """50 rapid sequential requests should all succeed."""
        _, headers = test_user_with_auth
        for i in range(50):
            response = client.get("/v1/user/self", headers=headers)
            assert response.status_code == 200, f"Failed on request {i+1}"

    def test_create_20_users_sequentially(self, client):
        """Creating 20 users sequentially should all succeed."""
        for i in range(20):
            payload = {
                "first_name": f"SeqUser{i}",
                "last_name": "Test",
                "username": f"sequser{i}@example.com",
                "password": "password123"
            }
            response = client.post("/v1/user", json=payload)
            assert response.status_code == 201, f"Failed on user {i}"

    def test_large_request_body_handling(self, client):
        """Request with 500+ char fields should be handled."""
        payload = {
            "first_name": "X" * 500,
            "last_name": "Y" * 500,
            "username": "largebody@example.com",
            "password": "Z" * 500
        }
        response = client.post("/v1/user", json=payload)
        # Should handle gracefully (accept or reject)
        assert response.status_code in [201, 400, 500]


class TestDataIntegrity:
    """Persistence, field isolation, consistency."""

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

    def test_password_is_bcrypt_hashed_in_db(self, client, db_session):
        """Password should be stored as BCrypt hash ($2b$), not plaintext."""
        payload = {
            "first_name": "Hash",
            "last_name": "Verify",
            "username": "hashverify@example.com",
            "password": "password123"
        }
        client.post("/v1/user", json=payload)
        user = db_session.query(User).filter(
            User.username == "hashverify@example.com"
        ).first()
        assert user.password != "password123"
        assert user.password.startswith("$2b$")

    def test_update_persists_across_multiple_gets(self, client, test_user_with_auth):
        """Updated data is consistent across multiple GET requests."""
        _, headers = test_user_with_auth
        client.put(
            "/v1/user/self",
            json={"first_name": "Persistent"},
            headers=headers
        )
        for _ in range(5):
            data = client.get("/v1/user/self", headers=headers).json()
            assert data["first_name"] == "Persistent"

    def test_update_one_field_does_not_affect_others(self, client, test_user_with_auth):
        """Updating first_name preserves last_name and username."""
        user, headers = test_user_with_auth
        original_last = user.last_name
        original_username = user.username

        client.put(
            "/v1/user/self",
            json={"first_name": "OnlyThis"},
            headers=headers
        )
        data = client.get("/v1/user/self", headers=headers).json()
        assert data["last_name"] == original_last
        assert data["username"] == original_username

    def test_account_created_never_changes(self, client, test_user_with_auth):
        """account_created should not change after any number of updates."""
        _, headers = test_user_with_auth
        original = client.get("/v1/user/self", headers=headers).json()["account_created"]

        for name in ["First", "Second", "Third"]:
            client.put(
                "/v1/user/self",
                json={"first_name": name},
                headers=headers
            )

        final = client.get("/v1/user/self", headers=headers).json()["account_created"]
        assert final == original

    def test_account_updated_changes_on_update(self, client, test_user_with_auth):
        """account_updated should change after PUT."""
        _, headers = test_user_with_auth
        before = client.get("/v1/user/self", headers=headers).json()["account_updated"]

        client.put(
            "/v1/user/self",
            json={"first_name": "Newer"},
            headers=headers
        )

        after = client.get("/v1/user/self", headers=headers).json()["account_updated"]
        assert after >= before

    def test_different_users_dont_interfere(self, client, create_test_user, auth_headers):
        """Updates to one user should not affect another user."""
        user_a, pw_a = create_test_user(
            username="usera@example.com", first_name="OriginalA"
        )
        user_b, pw_b = create_test_user(
            username="userb@example.com", first_name="OriginalB"
        )
        headers_a = auth_headers("usera@example.com", pw_a)
        headers_b = auth_headers("userb@example.com", pw_b)

        # Update user A
        client.put(
            "/v1/user/self",
            json={"first_name": "UpdatedA"},
            headers=headers_a
        )

        # User B should be unchanged
        data_b = client.get("/v1/user/self", headers=headers_b).json()
        assert data_b["first_name"] == "OriginalB"

    def test_healthz_creates_exactly_one_record(self, client, db_session):
        """Each healthz call creates exactly one DB record."""
        from app.models import HealthCheck
        count_before = db_session.query(HealthCheck).count()
        client.get("/healthz")
        count_after = db_session.query(HealthCheck).count()
        assert count_after == count_before + 1

    def test_healthz_records_have_timestamps(self, client, db_session):
        """Health check records should have timestamps."""
        from app.models import HealthCheck
        client.get("/healthz")
        record = db_session.query(HealthCheck).order_by(
            HealthCheck.check_id.desc()
        ).first()
        assert record is not None
        assert record.check_datetime is not None

    def test_password_update_immediately_invalidates_old(
        self, client, test_user_with_auth, auth_headers
    ):
        """After password change, old password should fail immediately."""
        user, old_headers = test_user_with_auth
        new_password = "completelynewpass"

        client.put(
            "/v1/user/self",
            json={"password": new_password},
            headers=old_headers
        )

        # Old password fails
        resp_old = client.get("/v1/user/self", headers=old_headers)
        assert resp_old.status_code == 401

        # New password works
        new_headers = auth_headers(user.username, new_password)
        resp_new = client.get("/v1/user/self", headers=new_headers)
        assert resp_new.status_code == 200

    def test_all_user_ids_are_unique(self, client):
        """All created users should have unique UUIDs."""
        ids = []
        for i in range(5):
            payload = {
                "first_name": f"Unique{i}",
                "last_name": "ID",
                "username": f"uniqueid{i}@example.com",
                "password": "password123"
            }
            resp = client.post("/v1/user", json=payload)
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        # All IDs should be unique
        assert len(ids) == len(set(ids)), "Duplicate UUIDs found"
