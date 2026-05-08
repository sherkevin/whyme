"""PRD10 §12.5 / §16.3 multipart upload + resume integration tests.

Covers the five-endpoint multipart contract introduced for §12.5:

* ``POST   /api/v1/uploads/multipart/init``                 — start session
* ``PUT    /api/v1/uploads/multipart/{upload_id}/{index}``  — push chunk
* ``GET    /api/v1/uploads/multipart/{upload_id}``          — resume status
* ``POST   /api/v1/uploads/multipart/{upload_id}/complete`` — assemble + Source
* ``DELETE /api/v1/uploads/multipart/{upload_id}``          — cancel session

All tests use the per-test in-memory SQLite + temp-storage fixtures from
``tests/integration/api/prd10/conftest.py`` so cross-test state can never
leak. The ``isolated_multipart_storage`` fixture below is local to this
file (mirrors ``isolated_storage`` in ``test_prd10_uploads_local_api.py``)
so the multipart staging tree is also redirected to a temp directory.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures — temp storage + temp multipart staging
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def isolated_storage(tmp_path_factory):
    """Point the singleton ``UploadStorage`` at a fresh temp directory."""

    from agent_os.uploads.storage import UploadStorage, set_default_storage

    tmp = tmp_path_factory.mktemp("uploads_final")
    storage = UploadStorage(base=tmp)
    set_default_storage(storage)
    try:
        yield tmp
    finally:
        set_default_storage(None)


@pytest_asyncio.fixture
async def isolated_multipart_storage(tmp_path_factory):
    """Point the singleton ``MultipartStorage`` at a fresh temp directory.

    Tests use a 1 KiB chunk size so we can exercise multi-chunk paths
    cheaply without allocating multi-megabyte test bodies.
    """

    from agent_os.uploads.storage import (
        MultipartStorage,
        set_default_multipart_storage,
    )

    tmp = tmp_path_factory.mktemp("uploads_multipart")
    storage = MultipartStorage(
        base=tmp,
        chunk_size=1024,
        ttl_seconds=3600,
        max_total_size_bytes=10 * 1024 * 1024,
    )
    set_default_multipart_storage(storage)
    try:
        yield tmp
    finally:
        set_default_multipart_storage(None)


async def _init_session(
    client,
    *,
    filename: str = "big.bin",
    total_size: int = 2560,  # 2.5 KiB → 3 chunks at 1 KiB each
    mime: str = "application/octet-stream",
    chunk_size: int | None = None,
) -> dict:
    body: dict = {
        "filename": filename,
        "total_size_bytes": total_size,
        "mime_type": mime,
    }
    if chunk_size is not None:
        body["chunk_size"] = chunk_size
    resp = await client.post("/api/v1/uploads/multipart/init", json=body)
    resp.raise_for_status()
    return resp.json()["data"]


def _make_payload(total_size: int, *, seed: int = 0) -> bytes:
    """Deterministic payload of ``total_size`` bytes for assembly assertions."""

    pattern = bytes((seed + i) & 0xFF for i in range(min(total_size, 256)))
    if total_size <= 256:
        return pattern[:total_size]
    repeats = (total_size + 255) // 256
    return (pattern * repeats)[:total_size]


def _split_chunks(blob: bytes, chunk_size: int) -> list[bytes]:
    return [blob[i : i + chunk_size] for i in range(0, len(blob), chunk_size)]


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


async def test_init_returns_envelope_with_session_descriptor(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    body = await _init_session(prd10_client, total_size=2560, chunk_size=1024)
    assert uuid.UUID(body["upload_id"])
    assert body["chunk_size"] == 1024
    assert body["total_chunks"] == 3
    assert body["total_size_bytes"] == 2560
    assert body["filename"] == "big.bin"
    assert body["status"] == "in_progress"
    assert body["received_count"] == 0
    assert body["received_chunks"] == []
    assert body["missing_chunks"] == [0, 1, 2]
    assert "expires_at" in body and "created_at" in body


async def test_init_zero_size_returns_400(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    resp = await prd10_client.post(
        "/api/v1/uploads/multipart/init",
        json={"filename": "x", "total_size_bytes": 0},
    )
    assert resp.status_code == 422  # Pydantic gt=0


async def test_init_too_large_returns_400(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    resp = await prd10_client.post(
        "/api/v1/uploads/multipart/init",
        json={
            "filename": "huge.bin",
            "total_size_bytes": 50 * 1024 * 1024,  # 50 MiB > 10 MiB test cap
        },
    )
    assert resp.status_code == 400


async def test_init_rejects_unknown_fields(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """``extra="forbid"`` on the init schema blocks side-channel injection."""

    resp = await prd10_client.post(
        "/api/v1/uploads/multipart/init",
        json={
            "filename": "x.bin",
            "total_size_bytes": 1024,
            "user_id": "00000000-0000-0000-0000-000000000000",  # forbidden
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT chunk
# ---------------------------------------------------------------------------


async def test_put_chunk_persists_and_reports_progress(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    init = await _init_session(prd10_client, total_size=2048, chunk_size=1024)
    upload_id = init["upload_id"]

    chunk0 = b"a" * 1024
    resp = await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0",
        content=chunk0,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["chunk_index"] == 0
    assert body["size_bytes"] == 1024
    assert body["received_count"] == 1
    assert body["total_chunks"] == 2
    assert body["is_complete"] is False
    assert len(body["sha256"]) == 64

    # Status endpoint reflects the same.
    status = await prd10_client.get(f"/api/v1/uploads/multipart/{upload_id}")
    assert status.status_code == 200
    sbody = status.json()["data"]
    assert sbody["received_chunks"] == [0]
    assert sbody["missing_chunks"] == [1]
    assert sbody["status"] == "in_progress"


async def test_put_chunks_out_of_order_then_complete(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """Chunks may arrive in any order; complete must assemble in index order."""

    payload = _make_payload(2560)  # 3 chunks at 1 KiB
    init = await _init_session(
        prd10_client, total_size=2560, chunk_size=1024
    )
    upload_id = init["upload_id"]
    chunks = _split_chunks(payload, 1024)

    # Send chunk 2, then 0, then 1 — out of order.
    for idx in (2, 0, 1):
        resp = await prd10_client.put(
            f"/api/v1/uploads/multipart/{upload_id}/{idx}",
            content=chunks[idx],
        )
        assert resp.status_code == 200, resp.text

    status = await prd10_client.get(f"/api/v1/uploads/multipart/{upload_id}")
    assert status.json()["data"]["received_chunks"] == [0, 1, 2]
    assert status.json()["data"]["status"] == "ready"

    complete = await prd10_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()["data"]
    assert body["upload_id"] == upload_id
    assert body["size_bytes"] == 2560
    assert body["filename"] == "big.bin"
    assert body["total_chunks"] == 3
    assert body["file_url"].endswith(f"/api/v1/uploads/local/{upload_id}/raw")

    # Final assembled file lives in the regular UploadStorage tree.
    files = list(Path(isolated_storage).rglob("big.bin"))
    assert len(files) == 1
    assert files[0].read_bytes() == payload

    # Multipart staging tree is now empty for this upload.
    multipart_root = Path(isolated_multipart_storage)
    leftovers = list(multipart_root.rglob(f"{upload_id}/**/*"))
    assert leftovers == []


async def test_put_wrong_chunk_size_returns_400(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """A non-final chunk that's smaller than ``chunk_size`` is rejected."""

    init = await _init_session(prd10_client, total_size=2048, chunk_size=1024)
    upload_id = init["upload_id"]

    resp = await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0",
        content=b"only-512-bytes" * 1,  # << 1024
    )
    assert resp.status_code == 400, resp.text


async def test_put_chunk_index_out_of_range_returns_400(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    init = await _init_session(prd10_client, total_size=2048, chunk_size=1024)
    upload_id = init["upload_id"]

    resp = await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/99",
        content=b"a" * 1024,
    )
    assert resp.status_code == 400, resp.text


async def test_put_chunk_unknown_session_returns_404(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    resp = await prd10_client.put(
        f"/api/v1/uploads/multipart/{uuid.uuid4()}/0",
        content=b"a" * 1024,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# complete (happy path + guards)
# ---------------------------------------------------------------------------


async def test_complete_before_all_chunks_returns_400(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    init = await _init_session(prd10_client, total_size=2560, chunk_size=1024)
    upload_id = init["upload_id"]

    # Only push chunk 0; chunks 1 & 2 missing.
    await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0",
        content=b"a" * 1024,
    )
    resp = await prd10_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert resp.status_code == 400, resp.text


async def test_complete_creates_source_row(
    prd10_client, prd10_user, prd10_sessionmaker,
    isolated_storage, isolated_multipart_storage
):
    """After complete, the Source row is upserted to ``parse_status='uploaded'``
    so ``POST /api/v1/capture/file/commit`` can pick it up."""

    from sqlalchemy import select

    from agent_os.sources.models import Source

    payload = _make_payload(2048)
    init = await _init_session(
        prd10_client,
        filename="report.pdf",
        mime="application/pdf",
        total_size=2048,
        chunk_size=1024,
    )
    upload_id = init["upload_id"]

    for idx, chunk in enumerate(_split_chunks(payload, 1024)):
        resp = await prd10_client.put(
            f"/api/v1/uploads/multipart/{upload_id}/{idx}", content=chunk
        )
        assert resp.status_code == 200, resp.text

    complete = await prd10_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert complete.status_code == 200, complete.text

    async with prd10_sessionmaker() as session:
        row = (
            await session.execute(
                select(Source).where(Source.id == uuid.UUID(upload_id))
            )
        ).scalar_one()
        assert row.user_id == prd10_user.id
        assert row.source_type == "file"
        assert row.name == "report.pdf"
        assert row.mime_type == "application/pdf"
        assert row.size_bytes == 2048
        assert row.parse_status == "uploaded"


async def test_complete_envelope_matches_single_put_shape(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """The complete response uses the same field set as the single-PUT
    response so ``capture/file/commit`` can consume either path."""

    init = await _init_session(prd10_client, total_size=1024, chunk_size=1024)
    upload_id = init["upload_id"]
    await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0", content=b"X" * 1024
    )
    complete = await prd10_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert complete.status_code == 200, complete.text
    data = complete.json()["data"]
    assert {"upload_id", "filename", "size_bytes", "file_url"} <= set(data.keys())
    assert "completed_at" in data and "total_chunks" in data


async def test_full_capture_file_commit_uses_multipart_upload(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """End-to-end: multipart init → push chunks → complete → capture/file/commit
    must materialize a Document like the single-PUT path."""

    payload = _make_payload(3072)  # 3 KiB → 3 chunks
    init = await _init_session(
        prd10_client,
        filename="big-doc.pdf",
        mime="application/pdf",
        total_size=3072,
        chunk_size=1024,
    )
    upload_id = init["upload_id"]
    for idx, chunk in enumerate(_split_chunks(payload, 1024)):
        await prd10_client.put(
            f"/api/v1/uploads/multipart/{upload_id}/{idx}", content=chunk
        )
    complete = await prd10_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert complete.status_code == 200, complete.text

    commit = await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": upload_id,
            "filename": "big-doc.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 3072,
        },
    )
    assert commit.status_code == 200, commit.text
    document_id = commit.json()["data"]["document_id"]

    doc = await prd10_client.get(f"/api/v1/kb/documents/{document_id}")
    assert doc.status_code == 200, doc.text

    # Original bytes streamable via /raw — the very same path single-PUT uses.
    raw = await prd10_client.get(
        f"/api/v1/uploads/local/{upload_id}/raw"
    )
    assert raw.status_code == 200, raw.text
    assert raw.content == payload


# ---------------------------------------------------------------------------
# resume / status
# ---------------------------------------------------------------------------


async def test_status_resume_lists_missing_indices(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """A resuming client polls GET /multipart/{upload_id} to learn which
    indices it still needs to push."""

    init = await _init_session(prd10_client, total_size=4096, chunk_size=1024)
    upload_id = init["upload_id"]
    await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0", content=b"a" * 1024
    )
    await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/2", content=b"c" * 1024
    )

    resp = await prd10_client.get(f"/api/v1/uploads/multipart/{upload_id}")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["received_chunks"] == [0, 2]
    assert body["missing_chunks"] == [1, 3]
    assert body["status"] == "in_progress"


async def test_status_unknown_session_returns_404(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    resp = await prd10_client.get(
        f"/api/v1/uploads/multipart/{uuid.uuid4()}"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


async def test_cancel_cleans_up_chunks_and_returns_cancelled_true(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    init = await _init_session(prd10_client, total_size=2048, chunk_size=1024)
    upload_id = init["upload_id"]
    await prd10_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0", content=b"a" * 1024
    )

    cancel = await prd10_client.delete(
        f"/api/v1/uploads/multipart/{upload_id}"
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["data"]["cancelled"] is True

    # Subsequent status lookup is a 404 because the session is gone.
    follow_up = await prd10_client.get(
        f"/api/v1/uploads/multipart/{upload_id}"
    )
    assert follow_up.status_code == 404


async def test_cancel_unknown_session_is_idempotent(
    prd10_client, isolated_storage, isolated_multipart_storage
):
    """DELETE on a non-existent session returns 200 with ``cancelled=False``
    so client retries don't raise spurious errors."""

    resp = await prd10_client.delete(
        f"/api/v1/uploads/multipart/{uuid.uuid4()}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["cancelled"] is False


# ---------------------------------------------------------------------------
# cross-user isolation
# ---------------------------------------------------------------------------


async def test_other_user_cannot_see_or_push_my_session(
    prd10_client, prd10_other_client,
    isolated_storage, isolated_multipart_storage
):
    init = await _init_session(prd10_client, total_size=1024, chunk_size=1024)
    upload_id = init["upload_id"]

    # GET status from other user → 404 (avoid leaking session existence).
    leaked = await prd10_other_client.get(
        f"/api/v1/uploads/multipart/{upload_id}"
    )
    assert leaked.status_code == 404

    # PUT chunk from other user → 404 (same reason).
    pushed = await prd10_other_client.put(
        f"/api/v1/uploads/multipart/{upload_id}/0", content=b"x" * 1024
    )
    assert pushed.status_code == 404

    # Complete from other user → 404.
    complete = await prd10_other_client.post(
        f"/api/v1/uploads/multipart/{upload_id}/complete"
    )
    assert complete.status_code == 404
