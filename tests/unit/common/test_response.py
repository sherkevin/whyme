"""Tests for PRD10 response helpers."""

import json

import pytest

from agent_os.common import ApiError, ApiErrorCode, build_pagination
from agent_os.common.response import (
    error_json_response,
    error_response,
    error_response_from,
    paginated_json_response,
    paginated_response,
    success_json_response,
    success_response,
)


def test_success_response_uses_prd10_envelope():
    response = success_response({"id": "item_1"}, request_id="req_test")

    assert response == {
        "success": True,
        "data": {"id": "item_1"},
        "request_id": "req_test",
    }


def test_success_response_allows_empty_object_data():
    response = success_response({}, request_id="req_test")

    assert response["data"] == {}


def test_paginated_response_calculates_has_more():
    response = paginated_response(
        [{"id": "a"}, {"id": "b"}],
        page=2,
        page_size=2,
        total=5,
        request_id="req_test",
    )

    assert response["success"] is True
    assert response["data"]["items"] == [{"id": "a"}, {"id": "b"}]
    assert response["data"]["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total": 5,
        "has_more": True,
    }


def test_build_pagination_validates_inputs():
    with pytest.raises(ValueError, match="page must be >= 1"):
        build_pagination(page=0, page_size=20, total=0)

    with pytest.raises(ValueError, match="page_size must be >= 1"):
        build_pagination(page=1, page_size=0, total=0)

    with pytest.raises(ValueError, match="total must be >= 0"):
        build_pagination(page=1, page_size=20, total=-1)


def test_error_response_uses_prd10_envelope():
    response = error_response(
        ApiErrorCode.VALIDATION_ERROR,
        "Invalid title",
        details={"field": "title"},
        request_id="req_test",
    )

    assert response == {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid title",
            "details": {"field": "title"},
        },
        "request_id": "req_test",
    }


def test_error_json_response_uses_default_status_code():
    response = error_json_response(
        ApiErrorCode.NOT_FOUND,
        "Missing record",
        request_id="req_test",
    )

    assert response.status_code == 404
    assert json.loads(response.body) == {
        "success": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "Missing record",
            "details": {},
        },
        "request_id": "req_test",
    }


def test_error_response_from_accepts_api_error():
    response = error_response_from(
        ApiError(
            ApiErrorCode.FORBIDDEN,
            "No access",
            details={"resource": "document"},
        ),
        request_id="req_test",
    )

    assert response["error"] == {
        "code": "FORBIDDEN",
        "message": "No access",
        "details": {"resource": "document"},
    }


def test_success_json_response_sets_status_and_request_id_header():
    response = success_json_response(
        {"created": True},
        status_code=201,
        request_id="req_test",
    )

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "req_test"
    assert json.loads(response.body)["data"] == {"created": True}


def test_paginated_json_response_sets_status_and_header():
    response = paginated_json_response(
        [],
        page=1,
        page_size=20,
        total=0,
        request_id="req_test",
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_test"
    assert json.loads(response.body)["data"]["pagination"]["has_more"] is False

