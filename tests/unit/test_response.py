"""Unit tests for API response helpers."""

from __future__ import annotations

import json

import pytest

from services.api_gateway.response import error_response, success_response


class TestSuccessResponse:
    """Tests for success_response (requires app context)."""

    def test_returns_tuple_with_status_code(self, app):
        with app.app_context():
            data = {"key": "value"}
            result, status = success_response(data)
            assert status == 200

    def test_includes_data_and_meta(self, app):
        with app.app_context():
            data = {"hostname": "test"}
            result, _ = success_response(data)
            body = json.loads(result.get_data(as_text=True))
            assert body["data"] == data
            assert "meta" in body
            assert "timestamp" in body["meta"]

    def test_custom_status_code(self, app):
        with app.app_context():
            data = {"id": "new-resource"}
            result, status = success_response(data, status_code=201)
            assert status == 201

    def test_meta_merge(self, app):
        with app.app_context():
            data = {"items": []}
            meta = {"total": 0, "page": 1}
            result, _ = success_response(data, meta=meta)
            body = json.loads(result.get_data(as_text=True))
            assert body["meta"]["total"] == 0
            assert body["meta"]["page"] == 1
            assert "timestamp" in body["meta"]


class TestErrorResponse:
    """Tests for error_response (requires app context)."""

    def test_returns_tuple_with_status_code(self, app):
        with app.app_context():
            result, status = error_response("VALIDATION_ERROR", "Invalid input")
            assert status == 500

    def test_custom_status_code(self, app):
        with app.app_context():
            result, status = error_response("NOT_FOUND", "Not found", status_code=404)
            assert status == 404

    def test_includes_error_structure(self, app):
        with app.app_context():
            result, _ = error_response("VALIDATION_ERROR", "Field required")
            body = json.loads(result.get_data(as_text=True))
            assert body["error"]["code"] == "VALIDATION_ERROR"
            assert body["error"]["message"] == "Field required"
            assert "details" in body["error"]

    def test_details_optional(self, app):
        with app.app_context():
            result, _ = error_response(
                "VALIDATION_ERROR", "Bad", details={"field": "email"}
            )
            body = json.loads(result.get_data(as_text=True))
            assert body["error"]["details"] == {"field": "email"}
