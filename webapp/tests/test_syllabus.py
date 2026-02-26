"""Tests for /v1/courses/{course_id}/syllabus endpoints."""

import uuid
from io import BytesIO
import pytest


def _upload_file(client, course_id, headers, filename="syllabus.pdf", content=b"fake pdf content", content_type="application/pdf"):
    """Helper to upload a syllabus file."""
    return client.post(
        f"/v1/courses/{course_id}/syllabus",
        headers=headers,
        files={"file": (filename, BytesIO(content), content_type)},
    )


class TestUploadSyllabusPositive:

    def test_upload_returns_201(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = _upload_file(client, course.id, headers)
        assert r.status_code == 201
        data = r.json()
        assert data["course_id"] == str(course.id)
        assert data["file_name"] == "syllabus.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["file_size"] == len(b"fake pdf content")
        assert data["s3_bucket_name"] == "test-bucket-uuid"
        assert str(course.id) in data["s3_object_key"]
        assert "id" in data
        uuid.UUID(data["id"])

    def test_upload_sets_has_syllabus_true(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        r = client.get(f"/v1/courses/{course.id}", headers=headers)
        assert r.json()["has_syllabus"] is True

    def test_upload_has_location_header(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = _upload_file(client, course.id, headers)
        assert r.status_code == 201
        assert r.headers.get("location") == f"/v1/courses/{course.id}/syllabus"

    def test_upload_different_courses_unique_keys(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        c1 = create_test_course(department_code="AAA", number="100")
        c2 = create_test_course(department_code="BBB", number="200")
        r1 = _upload_file(client, c1.id, headers, filename="syllabus.pdf")
        r2 = _upload_file(client, c2.id, headers, filename="syllabus.pdf")
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["s3_object_key"] != r2.json()["s3_object_key"]

    def test_upload_various_file_types(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = _upload_file(client, course.id, headers, filename="notes.docx", content=b"docx bytes",
                         content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert r.status_code == 201
        assert r.json()["content_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class TestUploadSyllabusNegative:

    def test_upload_no_auth(self, client, create_test_course):
        course = create_test_course()
        r = _upload_file(client, course.id, {})
        assert r.status_code == 401

    def test_upload_nonexistent_course(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = _upload_file(client, uuid.uuid4(), headers)
        assert r.status_code == 404

    def test_upload_duplicate_returns_409(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        r = _upload_file(client, course.id, headers, filename="another.pdf")
        assert r.status_code == 409

    def test_upload_no_file(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.post(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code in [400, 422]

    def test_upload_empty_file(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = _upload_file(client, course.id, headers, content=b"")
        assert r.status_code == 400


class TestGetSyllabusPositive:

    def test_get_syllabus_metadata(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        r = client.get(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["course_id"] == str(course.id)
        assert data["file_name"] == "syllabus.pdf"
        assert "url" in data
        assert "s3_bucket_name" in data
        assert "s3_object_key" in data


class TestGetSyllabusNegative:

    def test_get_syllabus_no_auth(self, client, create_test_course):
        course = create_test_course()
        r = client.get(f"/v1/courses/{course.id}/syllabus")
        assert r.status_code == 401

    def test_get_syllabus_course_not_found(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.get(f"/v1/courses/{uuid.uuid4()}/syllabus", headers=headers)
        assert r.status_code == 404

    def test_get_syllabus_no_syllabus_attached(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.get(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code == 404


class TestDeleteSyllabusPositive:

    def test_delete_syllabus(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        r = client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code == 204

    def test_delete_sets_has_syllabus_false(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        r = client.get(f"/v1/courses/{course.id}", headers=headers)
        assert r.json()["has_syllabus"] is False

    def test_delete_then_get_returns_404(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        r = client.get(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code == 404

    def test_delete_then_reupload(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        r = _upload_file(client, course.id, headers, filename="v2.pdf")
        assert r.status_code == 201
        assert r.json()["file_name"] == "v2.pdf"

    def test_delete_syllabus_allows_course_deletion(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        _upload_file(client, course.id, headers)
        # Can't delete course with syllabus
        r = client.delete(f"/v1/courses/{course.id}", headers=headers)
        assert r.status_code == 409
        # Delete syllabus first
        client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        # Now can delete course
        r = client.delete(f"/v1/courses/{course.id}", headers=headers)
        assert r.status_code == 204


class TestDeleteSyllabusNegative:

    def test_delete_no_auth(self, client, create_test_course):
        course = create_test_course()
        r = client.delete(f"/v1/courses/{course.id}/syllabus")
        assert r.status_code == 401

    def test_delete_course_not_found(self, client, test_user_with_auth):
        _, headers = test_user_with_auth
        r = client.delete(f"/v1/courses/{uuid.uuid4()}/syllabus", headers=headers)
        assert r.status_code == 404

    def test_delete_no_syllabus_returns_404(self, client, test_user_with_auth, create_test_course):
        _, headers = test_user_with_auth
        course = create_test_course()
        r = client.delete(f"/v1/courses/{course.id}/syllabus", headers=headers)
        assert r.status_code == 404
