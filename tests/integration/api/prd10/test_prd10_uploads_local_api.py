"""PRD10 §22.2 local upload-storage tests.

Covers ``PUT /api/v1/uploads/local/{upload_id}`` and the matching
``GET /api/v1/uploads/local/{upload_id}/raw`` download endpoint, plus the
end-to-end roundtrip with ``POST /api/v1/capture/file/commit``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_storage(tmp_path_factory):
    """Point the upload singleton at a fresh temp directory per test."""

    from agent_os.uploads.storage import UploadStorage, set_default_storage

    tmp = tmp_path_factory.mktemp("uploads")
    storage = UploadStorage(base=tmp)
    set_default_storage(storage)
    try:
        yield tmp
    finally:
        set_default_storage(None)


async def _presign(client, *, filename: str = "spec.pdf", mime: str = "application/pdf", size: int = 12) -> dict:
    resp = await client.post(
        "/api/v1/uploads/presign",
        json={"filename": filename, "mime_type": mime, "size_bytes": size},
    )
    resp.raise_for_status()
    return resp.json()["data"]


async def test_presign_returns_put_url_and_local_file_url(prd10_client, isolated_storage):
    presign = await _presign(prd10_client)
    assert presign["upload_method"] == "PUT"
    assert "/api/v1/uploads/local/" in presign["upload_url"]
    assert presign["file_url"].endswith(f"/api/v1/uploads/local/{presign['upload_id']}/raw")


async def test_put_upload_persists_bytes_to_disk(prd10_client, isolated_storage):
    presign = await _presign(prd10_client, filename="hello.txt", mime="text/plain", size=5)

    put = await prd10_client.put(
        f"/api/v1/uploads/local/{presign['upload_id']}",
        content=b"hello",
        headers={"X-Filename": "hello.txt", "Content-Type": "text/plain"},
    )
    assert put.status_code == 200
    body = put.json()["data"]
    assert body["upload_id"] == presign["upload_id"]
    assert body["size_bytes"] == 5
    assert body["filename"] == "hello.txt"

    # Bytes really hit the disk under the per-user / per-upload tree.
    files = list(Path(isolated_storage).rglob("hello.txt"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"hello"


async def test_put_then_get_raw_round_trips_bytes(prd10_client, isolated_storage):
    presign = await _presign(prd10_client, filename="r.txt", mime="text/plain", size=4)
    await prd10_client.put(
        f"/api/v1/uploads/local/{presign['upload_id']}",
        content=b"yolo",
        headers={"X-Filename": "r.txt", "Content-Type": "text/plain"},
    )

    raw = await prd10_client.get(f"/api/v1/uploads/local/{presign['upload_id']}/raw")
    assert raw.status_code == 200
    assert raw.content == b"yolo"
    assert raw.headers["content-type"].startswith("text/plain")


async def test_put_empty_body_returns_validation_error(prd10_client, isolated_storage):
    presign = await _presign(prd10_client)
    resp = await prd10_client.put(
        f"/api/v1/uploads/local/{presign['upload_id']}", content=b""
    )
    assert resp.status_code == 400


async def test_get_raw_404_when_not_uploaded(prd10_client, isolated_storage):
    resp = await prd10_client.get(f"/api/v1/uploads/local/{uuid.uuid4()}/raw")
    assert resp.status_code == 404


async def test_other_user_cannot_read_my_upload(prd10_client, prd10_other_client, isolated_storage):
    presign = await _presign(prd10_client, filename="secret.txt", mime="text/plain", size=6)
    await prd10_client.put(
        f"/api/v1/uploads/local/{presign['upload_id']}",
        content=b"secret",
        headers={"X-Filename": "secret.txt", "Content-Type": "text/plain"},
    )

    leaked = await prd10_other_client.get(
        f"/api/v1/uploads/local/{presign['upload_id']}/raw"
    )
    assert leaked.status_code == 404


async def test_full_capture_file_commit_uses_real_upload(prd10_client, isolated_storage):
    presign = await _presign(prd10_client, filename="brief.pdf", mime="application/pdf", size=7)
    await prd10_client.put(
        f"/api/v1/uploads/local/{presign['upload_id']}",
        content=b"PDFDATA",
        headers={"X-Filename": "brief.pdf", "Content-Type": "application/pdf"},
    )

    commit = await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": presign["upload_id"],
            "filename": "brief.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 7,
        },
    )
    assert commit.status_code == 200
    document_id = commit.json()["data"]["document_id"]

    # The committed document points at the real download URL and the
    # original bytes are still streamable via /raw.
    doc = await prd10_client.get(f"/api/v1/kb/documents/{document_id}")
    assert doc.status_code == 200

    raw = await prd10_client.get(
        f"/api/v1/uploads/local/{presign['upload_id']}/raw"
    )
    assert raw.status_code == 200
    assert raw.content == b"PDFDATA"
