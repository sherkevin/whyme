"""§8.9 — pluggable presign backends (local default + misconfigured S3 path)."""

from __future__ import annotations

import os

import pytest

from agent_os.uploads import presign as presign_mod

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _reset_presign_singleton():
    yield
    presign_mod.set_default_backend(None)


async def test_presign_envelope_includes_contract_extensions(prd10_client):
    r = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={
            "filename": "x.bin",
            "mime_type": "application/octet-stream",
            "size_bytes": 12,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    data = body["data"]
    for key in (
        "upload_id",
        "upload_url",
        "upload_method",
        "file_url",
        "expires_in",
        "expires_at",
        "max_size_bytes",
        "headers",
        "fields",
        "backend",
    ):
        assert key in data
    assert data["upload_method"] == "PUT"
    assert "/api/v1/uploads/local/" in data["upload_url"]
    assert data["backend"] == "local"


async def test_presign_s3_without_bucket_returns_503(prd10_client):
    """S3 backend selected but AWS_S3_BUCKET unset → RuntimeError → 503 envelope."""

    presign_mod.set_default_backend(None)
    prev_backend = os.environ.get("AGENTOS_UPLOAD_BACKEND")
    prev_bucket = os.environ.get("AWS_S3_BUCKET")
    try:
        os.environ["AGENTOS_UPLOAD_BACKEND"] = "s3"
        os.environ.pop("AWS_S3_BUCKET", None)
        presign_mod.set_default_backend(None)

        r = await prd10_client.post(
            "/api/v1/uploads/presign",
            json={
                "filename": "x.bin",
                "mime_type": "application/octet-stream",
                "size_bytes": 10,
            },
        )
        assert r.status_code == 503
        err = r.json()
        assert err.get("success") is False
        assert err["error"]["code"] == "INTERNAL_ERROR"
        assert "AWS_S3_BUCKET" in err["error"]["message"]
    finally:
        presign_mod.set_default_backend(None)
        if prev_backend is None:
            os.environ.pop("AGENTOS_UPLOAD_BACKEND", None)
        else:
            os.environ["AGENTOS_UPLOAD_BACKEND"] = prev_backend
        if prev_bucket is None:
            os.environ.pop("AWS_S3_BUCKET", None)
        else:
            os.environ["AWS_S3_BUCKET"] = prev_bucket
        presign_mod.set_default_backend(None)
