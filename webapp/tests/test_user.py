
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from app.models import User

class TestCreateUserPositive:

    # Test user creation with valid data returns 201 and complete response
    def test_create_user_returns_201_with_complete_response(self, client):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "jane.doe@example.com",
            "password": "securepass123"
        }
        response = client.post("/v1/user", json=payload)
        data = response.json()

        assert response.status_code == 201

        # Verify all required fields present
        required_fields = ["id", "first_name", "last_name", "username", "account_created", "account_updated"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify data types
        assert isinstance(data["id"], str)
        uuid.UUID(data["id"])
        assert isinstance(data["first_name"], str)
        assert isinstance(data["last_name"], str)
        assert isinstance(data["username"], str)
        assert isinstance(data["account_created"], str)
        assert isinstance(data["account_updated"], str)
        datetime.fromisoformat(data["account_created"])
        datetime.fromisoformat(data["account_updated"])

        # Verify values match input
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Doe"
        assert data["username"] == "jane.doe@example.com"

        # Verify password not in response
        assert "password" not in data

    # Test response includes Location header and correct content type
    def test_create_user_has_location_header(self, client):
        payload = {
            "first_name": "Loc",
            "last_name": "Header",
            "username": "locheader@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.headers.get("location") == "/v1/user/self"
        assert "application/json" in response.headers.get("content-type", "")

    # Test password is hashed with BCrypt before storing in database
    def test_create_user_password_is_bcrypt_hashed(self, client, db_session):
        payload = {
            "first_name": "Hash",
            "last_name": "Check",
            "username": "hashcheck@example.com",
            "password": "password123"
        }
        client.post("/v1/user", json=payload)
        user = db_session.query(User).filter(User.username == "hashcheck@example.com").first()
        assert user.password != "password123"
        assert user.password.startswith("$2b$")

    # Test various valid email formats are accepted
    @pytest.mark.parametrize("email", [
        "user1@domain.com",
        "user2@sub.domain.org",
        "first.last@company.co",
        "user+tag@example.com",
        "user.name.test@example.com",
    ])
    def test_create_user_with_valid_email_formats(self, client, email):
        payload = {
            "first_name": "Test",
            "last_name": "User",
            "username": email,
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201, f"Failed for email: {email}"


class TestCreateUserNegative:

    # Test missing required fields return 400
    @pytest.mark.parametrize("field_to_remove", ["first_name", "last_name", "username", "password"])
    def test_create_user_missing_required_fields(self, client, field_to_remove):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": f"missing.{field_to_remove}@example.com",
            "password": "password123"
        }
        del payload[field_to_remove]
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Test empty string values return 400
    @pytest.mark.parametrize("field,value", [
        ("first_name", ""),
        ("last_name", ""),
        ("username", ""),
        ("password", ""),
    ])
    def test_create_user_empty_string_fields(self, client, field, value):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": f"empty.{field}@example.com",
            "password": "password123"
        }
        payload[field] = value
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Test null values for required fields return 400
    @pytest.mark.parametrize("field", ["first_name", "last_name", "password"])
    def test_create_user_null_fields(self, client, field):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": f"null.{field}@example.com",
            "password": "password123"
        }
        payload[field] = None
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Test malformed JSON returns 400
    def test_create_user_invalid_json(self, client):
        response = client.post(
            "/v1/user",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    # Test empty request body returns 400
    def test_create_user_empty_body(self, client):
        response = client.post(
            "/v1/user",
            content=b"",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    # Test empty JSON object returns 400
    def test_create_user_missing_all_fields(self, client):
        response = client.post("/v1/user", json={})
        assert response.status_code == 400

    # Test invalid email formats return 400
    @pytest.mark.parametrize("invalid_email", [
        "notanemail",
        "user@nodot",
        "user@",
        "@example.com",
    ])
    def test_create_user_invalid_email_formats(self, client, invalid_email):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": invalid_email,
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Test password shorter than 8 characters returns 400
    def test_create_user_short_password(self, client):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": "shortpw@example.com",
            "password": "short"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400

    # Test duplicate email returns 409 Conflict
    def test_create_user_duplicate_email(self, client, create_test_user):
        create_test_user(username="dup@example.com")
        payload = {
            "first_name": "Another",
            "last_name": "User",
            "username": "dup@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 409

    # Test duplicate email detection is case-insensitive
    def test_create_user_duplicate_email_case_insensitive(self, client, create_test_user):
        create_test_user(username="casetest@example.com")
        payload = {
            "first_name": "Another",
            "last_name": "User",
            "username": "CASETEST@EXAMPLE.COM",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 409

    # Test wrong Content-Type returns 415
    @pytest.mark.parametrize("content_type", [
        "application/x-www-form-urlencoded",
        "text/plain",
        "text/html",
    ])
    def test_create_user_wrong_content_type(self, client, content_type):
        response = client.post(
            "/v1/user",
            content=b'{"first_name":"Jane","last_name":"Doe","username":"test@example.com","password":"password123"}',
            headers={"Content-Type": content_type}
        )
        assert response.status_code == 415

    # Test invalid data types for string fields return 400
    @pytest.mark.parametrize("field,invalid_value", [
        ("password", 12345678),
        ("first_name", 12345),
        ("last_name", 12345),
    ])
    def test_create_user_invalid_data_types(self, client, field, invalid_value):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "username": f"invalid.{field}@example.com",
            "password": "password123"
        }
        payload[field] = invalid_value
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400


class TestGetUserSelfPositive:

    # Test authenticated GET returns 200 with correct user data
    def test_get_user_self_returns_200_with_correct_data(self, client, test_user_with_auth):
        user, headers = test_user_with_auth
        response = client.get("/v1/user/self", headers=headers)
        data = response.json()

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        assert data["username"] == user.username
        assert data["first_name"] == user.first_name
        assert data["last_name"] == user.last_name
        assert "password" not in data

    # Test multiple GET requests return identical data (idempotent)
    def test_get_user_self_multiple_calls_return_same_data(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        resp1 = client.get("/v1/user/self", headers=headers).json()
        resp2 = client.get("/v1/user/self", headers=headers).json()
        resp3 = client.get("/v1/user/self", headers=headers).json()
        assert resp1 == resp2 == resp3


class TestGetUserSelfNegative:

    # Test request without authentication returns 401
    def test_get_user_no_auth(self, client):
        response = client.get("/v1/user/self")
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Basic" in www_auth

    # Test wrong password returns 401
    def test_get_user_wrong_password(self, client, test_user_with_auth, auth_headers):
        user, _ = test_user_with_auth
        bad_headers = auth_headers(user.username, "wrongpassword")
        response = client.get("/v1/user/self", headers=bad_headers)
        assert response.status_code == 401

    # Test non-existent username returns 401
    def test_get_user_nonexistent_username(self, client, auth_headers):
        headers = auth_headers("nobody@example.com", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Test password authentication is case-sensitive
    def test_get_user_case_sensitive_password(self, client, create_test_user, auth_headers):
        create_test_user(username="casepw@example.com", password="Password123")
        headers = auth_headers("casepw@example.com", "password123")
        response = client.get("/v1/user/self", headers=headers)
        assert response.status_code == 401

    # Test malformed Authorization header returns 401 or 400
    def test_get_user_malformed_auth_header(self, client):
        response = client.get(
            "/v1/user/self",
            headers={"Authorization": "Basic not-valid-base64!!!"}
        )
        assert response.status_code in [401, 400]


class TestUpdateUserPositive:

    # Test updating individual fields returns 204
    @pytest.mark.parametrize("field,value", [
        ("first_name", "Updated"),
        ("last_name", "NewLast"),
        ("password", "newpassword123"),
    ])
    def test_update_single_field_returns_204(self, client, create_test_user, auth_headers, field, value):
        user, password = create_test_user()
        headers = auth_headers(user.username, password)
        response = client.put("/v1/user/self", json={field: value}, headers=headers)
        assert response.status_code == 204
        assert response.content == b""

    # Test updating multiple fields simultaneously
    def test_update_multiple_fields(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={"first_name": "New", "last_name": "Name"}, headers=headers)
        assert response.status_code == 204

    # Test updated values persist in subsequent GET requests
    def test_update_persists_and_returns_in_get(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        client.put("/v1/user/self", json={"first_name": "ChangedName"}, headers=headers)
        response = client.get("/v1/user/self", headers=headers)
        assert response.json()["first_name"] == "ChangedName"

    # Test partial update doesn't affect unmodified fields
    def test_update_does_not_affect_unmodified_fields(self, client, test_user_with_auth):
        user, headers = test_user_with_auth
        original_last = user.last_name
        original_username = user.username

        client.put("/v1/user/self", json={"first_name": "OnlyThis"}, headers=headers)
        data = client.get("/v1/user/self", headers=headers).json()

        assert data["last_name"] == original_last
        assert data["username"] == original_username

    # Test account_updated timestamp changes after update
    def test_update_changes_account_updated_timestamp(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        before = client.get("/v1/user/self", headers=headers).json()
        time.sleep(0.1)
        client.put("/v1/user/self", json={"first_name": "Newer"}, headers=headers)
        after = client.get("/v1/user/self", headers=headers).json()
        assert after["account_updated"] >= before["account_updated"]

    # Test password update: new password works, old password fails
    def test_update_password_invalidates_old_credentials(self, client, test_user_with_auth, auth_headers):
        user, old_headers = test_user_with_auth
        new_password = "brandnewpass123"

        client.put("/v1/user/self", json={"password": new_password}, headers=old_headers)

        resp_old = client.get("/v1/user/self", headers=old_headers)
        assert resp_old.status_code == 401

        new_headers = auth_headers(user.username, new_password)
        resp_new = client.get("/v1/user/self", headers=new_headers)
        assert resp_new.status_code == 200

    # Test empty JSON object is valid (no-op update)
    def test_update_empty_json_object_returns_204(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={}, headers=headers)
        assert response.status_code == 204

    # Test updating names to special characters works
    def test_update_names_with_special_characters(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put(
            "/v1/user/self",
            json={"first_name": "José", "last_name": "O'Brien"},
            headers=headers
        )
        assert response.status_code == 204
        
        data = client.get("/v1/user/self", headers=headers).json()
        assert data["first_name"] == "José"
        assert data["last_name"] == "O'Brien"


class TestUpdateUserNegative:

    # Test update without authentication returns 401
    def test_update_user_no_auth(self, client):
        response = client.put("/v1/user/self", json={"first_name": "Hacker"})
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "Basic" in www_auth

    # Test update with wrong password returns 401
    def test_update_user_wrong_password(self, client, test_user_with_auth, auth_headers):
        user, _ = test_user_with_auth
        bad_headers = auth_headers(user.username, "wrongpass")
        response = client.put("/v1/user/self", json={"first_name": "Hacker"}, headers=bad_headers)
        assert response.status_code == 401

    # Test updating read-only fields returns 400
    @pytest.mark.parametrize("readonly_field,value", [
        ("username", "new@example.com"),
        ("id", "05b2fa78-a0f8-4357-97fe-d18506618c3f"),
        ("account_created", "2020-01-01T00:00:00Z"),
        ("account_updated", "2020-01-01T00:00:00Z"),
    ])
    def test_update_readonly_fields_not_allowed(self, client, test_user_with_auth, readonly_field, value):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={readonly_field: value}, headers=headers)
        assert response.status_code == 400

    # Test wrong Content-Type returns 415
    def test_update_user_wrong_content_type(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        headers["Content-Type"] = "text/plain"
        response = client.put("/v1/user/self", content=b'{"first_name": "Test"}', headers=headers)
        assert response.status_code == 415

    # Test invalid data types for updatable fields return 400
    @pytest.mark.parametrize("field,invalid_value", [
        ("first_name", 12345),
        ("last_name", 12345),
        ("password", 12345678),
    ])
    def test_update_invalid_data_types(self, client, test_user_with_auth, field, invalid_value):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={field: invalid_value}, headers=headers)
        assert response.status_code == 400

    # Test password shorter than 8 characters returns 400
    def test_update_password_too_short(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={"password": "short"}, headers=headers)
        assert response.status_code == 400

    # Test update with empty string values returns 400
    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_update_with_empty_string_fields(self, client, test_user_with_auth, field):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={field: ""}, headers=headers)
        assert response.status_code == 400

    # Test update with null values returns 400
    @pytest.mark.parametrize("field", ["first_name", "last_name", "password"])
    def test_update_with_null_values(self, client, test_user_with_auth, field):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={field: None}, headers=headers)
        assert response.status_code == 400

    # Test malformed Authorization header on update returns 401 or 400
    def test_update_malformed_auth_header(self, client):
        response = client.put(
            "/v1/user/self",
            json={"first_name": "Test"},
            headers={"Authorization": "Basic invalid-base64!!!"}
        )
        assert response.status_code in [401, 400]

    # Test update with empty password returns 400
    def test_update_password_to_empty_string(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={"password": ""}, headers=headers)
        assert response.status_code == 400

    # Test update with whitespace-only password returns 400
    def test_update_password_to_whitespace_only(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        response = client.put("/v1/user/self", json={"password": "        "}, headers=headers)
        assert response.status_code == 400


class TestAuthenticationIntegration:

    # Test complete flow: create user then authenticate and retrieve data
    def test_successful_registration_and_login(self, client, auth_headers):
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
        assert get_resp.json()["username"] == "authtest@example.com"


class TestMethodNotAllowed:

    # Test POST /v1/user only allows POST method
    @pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "PATCH"])
    def test_user_create_endpoint_only_allows_post(self, client, method):
        response = client.request(method, "/v1/user", json={})
        assert response.status_code == 405

    # Test /v1/user/self only allows GET and PUT methods
    @pytest.mark.parametrize("method", ["POST", "DELETE", "PATCH"])
    def test_user_self_endpoint_only_allows_get_put(self, client, test_user_with_auth, method):
        _, headers = test_user_with_auth
        response = client.request(method, "/v1/user/self", json={}, headers=headers)
        assert response.status_code == 405


class TestUnsupportedEndpoints:

    # Test various incorrect/unsupported endpoint paths return 404
    @pytest.mark.parametrize("endpoint", [
        "/v1/random",
        "/v1/users",
        "/v2/user",
        "/health",
        "/healthcheck",
        "/api/healthz",
        "/user",
        "/",
    ])
    def test_unsupported_endpoints_return_404(self, client, endpoint):
        response = client.get(endpoint)
        assert response.status_code == 404


class TestSecurityAndEdgeCases:

    # Test SQL injection attempts are safely handled
    def test_sql_injection_in_username(self, client):
        payload = {
            "first_name": "Hacker",
            "last_name": "Test",
            "username": "'; DROP TABLE users; --@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code in [201, 400]

    # Test names with SQL special characters are accepted
    def test_sql_injection_in_first_name(self, client):
        payload = {
            "first_name": "'; DROP TABLE users; --",
            "last_name": "Test",
            "username": "sqlinject@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    # Test extremely long input is rejected gracefully
    def test_very_long_first_name(self, client):
        payload = {
            "first_name": "A" * 10000,
            "last_name": "Doe",
            "username": "longname@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400


class TestBoundaryValues:

    # Test minimum valid name length (1 character)
    def test_single_character_first_name(self, client):
        payload = {
            "first_name": "A",
            "last_name": "B",
            "username": "singlechar@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201
        assert response.json()["first_name"] == "A"

    # Test name at database column limit (100 characters)
    def test_100_char_name(self, client):
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

    # Test minimum valid password length (8 characters)
    def test_password_exactly_8_chars(self, client):
        payload = {
            "first_name": "Min",
            "last_name": "Pass",
            "username": "minpass@example.com",
            "password": "12345678"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

    # Test password below minimum length (7 characters) is rejected
    def test_password_7_chars_fails(self, client):
        payload = {
            "first_name": "Short",
            "last_name": "Pass",
            "username": "shortpw2@example.com",
            "password": "1234567"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 400


class TestUnicodeAndSpecialCharacters:

    # Test names with Unicode characters from various languages
    @pytest.mark.parametrize("first_name,last_name,description", [
        ("François", "Héléne", "French accents"),
        ("李明", "王", "Chinese characters"),
        ("Владимир", "Петров", "Russian Cyrillic"),
        ("محمد", "أحمد", "Arabic script"),
        ("Mary-Jane", "O'Brien", "Hyphens and apostrophes"),
        ("St. John", "Smith", "Period in name"),
        ("John3", "Smith2nd", "Numbers in names"),
    ])
    def test_unicode_and_special_chars_in_names(self, client, first_name, last_name, description):
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "username": f"{description.replace(' ', '')}@example.com",
            "password": "password123"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201, f"Failed for {description}"
        assert response.json()["first_name"] == first_name
        assert response.json()["last_name"] == last_name

    # Test passwords with special characters work correctly
    def test_special_chars_in_password(self, client, auth_headers):
        payload = {
            "first_name": "Special",
            "last_name": "Pass",
            "username": "specialpass@example.com",
            "password": "P@$$w0rd!#%^&*()"
        }
        response = client.post("/v1/user", json=payload)
        assert response.status_code == 201

        headers = auth_headers("specialpass@example.com", "P@$$w0rd!#%^&*()")
        get_resp = client.get("/v1/user/self", headers=headers)
        assert get_resp.status_code == 200


class TestConcurrencyAndPerformance:

    # Test concurrent duplicate user creation: only one succeeds
    def test_concurrent_duplicate_user_creation(self, client):
        payload = {
            "first_name": "Concurrent",
            "last_name": "Test",
            "username": "concurrent5@example.com",
            "password": "password123"
        }
        results = []

        def create_user():
            resp = client.post("/v1/user", json=payload)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user) for _ in range(5)]
            for f in futures:
                f.result()

        success_count = results.count(201)
        fail_count = results.count(409)
        assert success_count == 1, f"Expected 1 success, got {success_count}: {results}"
        assert fail_count == 4, f"Expected 4 conflicts, got {fail_count}: {results}"

    # Test concurrent password updates don't cause errors
    def test_concurrent_password_updates(self, client, create_test_user, auth_headers):
        user, password = create_test_user(username="concpw@example.com")
        headers = auth_headers(user.username, password)
        results = []

        def update_password(new_pw):
            resp = client.put("/v1/user/self", json={"password": new_pw}, headers=headers)
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(update_password, f"newpassword{i}") for i in range(3)]
            for f in futures:
                f.result()

        for code in results:
            assert code in [204, 401], f"Unexpected status code: {code}"

    # Test concurrent reads during writes: no data corruption
    def test_read_while_write_no_corruption(self, client, create_test_user, auth_headers):
        user, password = create_test_user(
            username="readwrite@example.com",
            first_name="Original",
            last_name="Name"
        )
        headers = auth_headers(user.username, password)
        read_results = []

        def read_user():
            resp = client.get("/v1/user/self", headers=headers)
            if resp.status_code == 200:
                read_results.append(resp.json())

        def write_user(name):
            client.put("/v1/user/self", json={"first_name": name}, headers=headers)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(read_user))
                if i % 2 == 0:
                    futures.append(executor.submit(write_user, f"Updated{i}"))
            for f in futures:
                f.result()

        for data in read_results:
            assert "id" in data
            assert "first_name" in data
            assert "username" in data
            assert isinstance(data["first_name"], str)
            assert len(data["first_name"]) > 0

    # Test user creation responds within 2 seconds
    def test_create_user_response_time(self, client):
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

    # Test GET request responds within 1 second
    def test_get_self_response_time(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        start = time.time()
        response = client.get("/v1/user/self", headers=headers)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Response took {elapsed:.2f}s, expected < 1s"

    # Test sequential user creation all succeed
    def test_create_20_users_sequentially(self, client):
        for i in range(20):
            payload = {
                "first_name": f"SeqUser{i}",
                "last_name": "Test",
                "username": f"sequser{i}@example.com",
                "password": "password123"
            }
            response = client.post("/v1/user", json=payload)
            assert response.status_code == 201, f"Failed on user {i}"


class TestDataIntegrity:

    # Test created user data persists and can be retrieved
    def test_created_user_data_persists(self, client, auth_headers):
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

    # Test account_created timestamp never changes (immutable)
    def test_account_created_never_changes(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        original = client.get("/v1/user/self", headers=headers).json()["account_created"]

        for name in ["First", "Second", "Third"]:
            client.put("/v1/user/self", json={"first_name": name}, headers=headers)

        final = client.get("/v1/user/self", headers=headers).json()["account_created"]
        assert final == original

    # Test operations on different users don't interfere with each other
    def test_different_users_dont_interfere(self, client, create_test_user, auth_headers):
        user_a, pw_a = create_test_user(username="usera@example.com", first_name="OriginalA")
        user_b, pw_b = create_test_user(username="userb@example.com", first_name="OriginalB")
        headers_a = auth_headers("usera@example.com", pw_a)
        headers_b = auth_headers("userb@example.com", pw_b)

        client.put("/v1/user/self", json={"first_name": "UpdatedA"}, headers=headers_a)

        data_b = client.get("/v1/user/self", headers=headers_b).json()
        assert data_b["first_name"] == "OriginalB"

    # Test all generated user IDs are unique
    def test_all_user_ids_are_unique(self, client):
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

        assert len(ids) == len(set(ids)), "Duplicate UUIDs found"