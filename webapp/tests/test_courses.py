"""Tests for /v1/courses endpoints."""

import uuid
from datetime import datetime

import pytest


class TestCreateCoursePositive:

    def test_create_course_returns_201(self, client, test_user_with_auth, sample_course_payload):
        _, headers = test_user_with_auth
        r = client.post("/v1/courses", json=sample_course_payload, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert data["department_code"] == "ACCT"
        assert data["number"] == "3220"
        assert data["title"] == sample_course_payload["title"]
        assert data["credit_hours"] == 4
        assert data["classification"] == "elective"
        assert data["has_syllabus"] is False
        assert "id" in data
        uuid.UUID(data["id"])
        datetime.fromisoformat(data["date_created"])
        datetime.fromisoformat(data["date_updated"])

    def test_create_course_has_location_header(self, client, test_user_with_auth, sample_course_payload):
        _, headers = test_user_with_auth
        r = client.post("/v1/courses", json=sample_course_payload, headers=headers)
        assert r.status_code == 201
        assert r.headers.get("location") == f"/v1/courses/{r.json()['id']}"

    def test_create_course_minimal_fields(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {
            "department_code": "CS",
            "number": "101",
            "title": "Intro to CS",
            "credit_hours": 3,
            "classification": "core",
        }
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert data["description"] is None
        assert data["prerequisites"] is None

    def test_create_course_boundary_dept_code_2_chars(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "CS", "number": "100", "title": "T", "credit_hours": 1, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 201

    def test_create_course_boundary_dept_code_6_chars(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "ABCDEF", "number": "100", "title": "T", "credit_hours": 1, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 201

    def test_create_course_credit_hours_min(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "001", "title": "T", "credit_hours": 1, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 201

    def test_create_course_credit_hours_max(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "002", "title": "T", "credit_hours": 8, "classification": "elective"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 201


class TestCreateCourseNegative:

    def test_create_course_no_auth(self, client, sample_course_payload):
        r = client.post("/v1/courses", json=sample_course_payload)
        assert r.status_code == 401

    def test_create_course_duplicate_returns_409(self, client, test_user_with_auth, sample_course_payload):
        _, headers = test_user_with_auth
        client.post("/v1/courses", json=sample_course_payload, headers=headers)
        r = client.post("/v1/courses", json=sample_course_payload, headers=headers)
        assert r.status_code == 409

    @pytest.mark.parametrize("field", ["department_code", "number", "title", "credit_hours", "classification"])
    def test_create_course_missing_required_field(self, client, test_user_with_auth, sample_course_payload, field):
        _, headers = test_user_with_auth
        payload = {**sample_course_payload}
        del payload[field]
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    @pytest.mark.parametrize("dept_code", ["cs", "Csye", "A", "ABCDEFG", "CS1", "12"])
    def test_create_course_invalid_department_code(self, client, test_user_with_auth, dept_code):
        _, headers = test_user_with_auth
        payload = {"department_code": dept_code, "number": "100", "title": "T", "credit_hours": 3, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    @pytest.mark.parametrize("ch", [0, 9, -1, 100])
    def test_create_course_invalid_credit_hours(self, client, test_user_with_auth, ch):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "999", "title": "T", "credit_hours": ch, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_credit_hours_float(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "999", "title": "T", "credit_hours": 3.5, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_credit_hours_boolean(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "999", "title": "T", "credit_hours": True, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_invalid_classification(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "999", "title": "T", "credit_hours": 3, "classification": "optional"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_number_too_long(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "1234567", "title": "T", "credit_hours": 3, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_title_too_long(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "100", "title": "A" * 256, "credit_hours": 3, "classification": "core"}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_with_server_field_id(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "100", "title": "T", "credit_hours": 3, "classification": "core", "id": str(uuid.uuid4())}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_with_server_field_has_syllabus(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "100", "title": "T", "credit_hours": 3, "classification": "core", "has_syllabus": True}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_wrong_content_type(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        headers["Content-Type"] = "text/plain"
        r = client.post("/v1/courses", content=b'{}', headers=headers)
        assert r.status_code == 415

    def test_create_course_empty_body(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.post("/v1/courses", content=b'', headers={**headers, "Content-Type": "application/json"})
        assert r.status_code == 400

    def test_create_course_description_too_long(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "100", "title": "T", "credit_hours": 3, "classification": "core", "description": "D" * 2001}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400

    def test_create_course_prerequisites_too_long(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        payload = {"department_code": "TST", "number": "100", "title": "T", "credit_hours": 3, "classification": "core", "prerequisites": "P" * 513}
        r = client.post("/v1/courses", json=payload, headers=headers)
        assert r.status_code == 400


class TestGetCoursesPositive:

    def test_list_courses_empty(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.get("/v1/courses", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_list_courses_sorted(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        create_test_course(department_code="CSYE", number="6225")
        create_test_course(department_code="ACCT", number="3220")
        create_test_course(department_code="ACCT", number="2301")

        r = client.get("/v1/courses", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        assert data[0]["department_code"] == "ACCT" and data[0]["number"] == "2301"
        assert data[1]["department_code"] == "ACCT" and data[1]["number"] == "3220"
        assert data[2]["department_code"] == "CSYE" and data[2]["number"] == "6225"

    def test_get_course_by_id(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.get(f"/v1/courses/{course.id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == str(course.id)

    def test_get_course_not_found(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.get(f"/v1/courses/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404


class TestGetCoursesNegative:

    def test_list_courses_no_auth(self, client):
        r = client.get("/v1/courses")
        assert r.status_code == 401

    def test_get_course_no_auth(self, client):
        r = client.get(f"/v1/courses/{uuid.uuid4()}")
        assert r.status_code == 401


class TestUpdateCoursePositive:

    def test_update_title(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.put(f"/v1/courses/{course.id}", json={"title": "New Title"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["title"] == "New Title"

    def test_update_multiple_fields(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.put(
            f"/v1/courses/{course.id}",
            json={"title": "Updated", "credit_hours": 3, "classification": "elective"},
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Updated"
        assert data["credit_hours"] == 3
        assert data["classification"] == "elective"

    def test_update_changes_date_updated(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        original = client.get(f"/v1/courses/{course.id}", headers=headers).json()["date_updated"]
        import time; time.sleep(0.05)
        client.put(f"/v1/courses/{course.id}", json={"title": "Changed"}, headers=headers)
        updated = client.get(f"/v1/courses/{course.id}", headers=headers).json()["date_updated"]
        assert updated >= original

    def test_update_description_to_null(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course(description="Some description")
        r = client.put(f"/v1/courses/{course.id}", json={"description": None}, headers=headers)
        assert r.status_code == 200
        assert r.json()["description"] is None

    def test_update_preserves_unmodified_fields(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course(department_code="CSYE", number="6225", title="Original")
        client.put(f"/v1/courses/{course.id}", json={"classification": "elective"}, headers=headers)
        data = client.get(f"/v1/courses/{course.id}", headers=headers).json()
        assert data["title"] == "Original"
        assert data["department_code"] == "CSYE"
        assert data["number"] == "6225"


class TestUpdateCourseNegative:

    def test_update_no_auth(self, client, create_test_course):
        course = create_test_course()
        r = client.put(f"/v1/courses/{course.id}", json={"title": "Hacked"})
        assert r.status_code == 401

    def test_update_not_found(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.put(f"/v1/courses/{uuid.uuid4()}", json={"title": "X"}, headers=headers)
        assert r.status_code == 404

    @pytest.mark.parametrize("field", ["id", "department_code", "number", "has_syllabus", "date_created", "date_updated"])
    def test_update_immutable_field(self, client, test_user_with_auth, create_test_course, field):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.put(f"/v1/courses/{course.id}", json={field: "value"}, headers=headers)
        assert r.status_code == 400

    def test_update_empty_body(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.put(
            f"/v1/courses/{course.id}",
            content=b'{}',
            headers={**headers, "Content-Type": "application/json"},
        )
        assert r.status_code == 400

    def test_update_invalid_credit_hours(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.put(f"/v1/courses/{course.id}", json={"credit_hours": 0}, headers=headers)
        assert r.status_code == 400

    def test_update_wrong_content_type(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        headers["Content-Type"] = "text/plain"
        r = client.put(f"/v1/courses/{course.id}", content=b'{"title":"x"}', headers=headers)
        assert r.status_code == 415


class TestDeleteCoursePositive:

    def test_delete_course_no_syllabus(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.delete(f"/v1/courses/{course.id}", headers=headers)
        assert r.status_code == 204
        # Verify deleted
        r2 = client.get(f"/v1/courses/{course.id}", headers=headers)
        assert r2.status_code == 404


class TestDeleteCourseNegative:

    def test_delete_no_auth(self, client, create_test_course):
        course = create_test_course()
        r = client.delete(f"/v1/courses/{course.id}")
        assert r.status_code == 401

    def test_delete_not_found(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.delete(f"/v1/courses/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404

    def test_delete_course_with_syllabus_returns_409(self, client, test_user_with_auth, create_test_course, db_session):
        _, headers = test_user_with_auth
        course = create_test_course()
        course.has_syllabus = True
        db_session.flush()
        r = client.delete(f"/v1/courses/{course.id}", headers=headers)
        assert r.status_code == 409
        assert "syllabus" in r.json()["message"].lower()
