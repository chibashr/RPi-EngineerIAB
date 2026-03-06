"""Unit tests for API response helpers."""

from __future__ import annotations

import json

import pytest

from services.api_gateway.response import error_response, success_response


def _body(response):
    """Extract JSON body from Starlette JSONResponse."""
    return json.loads(response.body.decode())


class TestSuccessResponse:
    """Tests for success_response."""

    def test_returns_response_with_status_code(self):
        data = {"key": "value"}
        result = success_response(data)
        assert result.status_code == 200

    def test_includes_data_and_meta(self):
        data = {"hostname": "test"}
        result = success_response(data)
        body = _body(result)
        assert body["data"] == data
        assert "meta" in body
        assert "timestamp" in body["meta"]

    def test_custom_status_code(self):
        data = {"id": "new-resource"}
        result = success_response(data, status_code=201)
        assert result.status_code == 201

    def test_meta_merge(self):
        data = {"items": []}
        meta = {"total": 0, "page": 1}
        result = success_response(data, meta=meta)
        body = _body(result)
        assert body["meta"]["total"] == 0
        assert body["meta"]["page"] == 1
        assert "timestamp" in body["meta"]


class TestErrorResponse:
    """Tests for error_response."""

    def test_returns_response_with_status_code(self):
        result = error_response("VALIDATION_ERROR", "Invalid input")
        assert result.status_code == 500

    def test_custom_status_code(self):
        result = error_response("NOT_FOUND", "Not found", status_code=404)
        assert result.status_code == 404

    def test_includes_error_structure(self):
        result = error_response("VALIDATION_ERROR", "Field required")
        body = _body(result)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Field required"
        assert "details" in body["error"]

    def test_details_optional(self):
        result = error_response(
            "VALIDATION_ERROR", "Bad", details={"field": "email"}
        )
        body = _body(result)
        assert body["error"]["details"] == {"field": "email"}
