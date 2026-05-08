"""PRD10 §15 / §16 failure-path tests for capture/jobs/notifications.

These exercise the V1 pseudo-worker's failure branch
(``capture.pipeline.simulate_failure``). Production workers will eventually
replace the simulator, but the contract these tests pin down — failed Job +
typed Notification + downstream Source/Document state — must survive that
swap.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_capture_text_failure_marks_job_failed(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "x", "_simulate_failure": "summary worker crashed"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["inbox_item"]["status"] == "failed"
    assert data["inbox_item"]["processing_status"] == "failed"

    job = data["job"]
    assert job["status"] == "failed"
    assert job["error"]["code"] == "JOB_FAILED"
    assert "summary worker crashed" in job["error"]["message"]


async def test_capture_text_failure_emits_job_failed_notification(prd10_client):
    await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "x", "_simulate_failure": "summary failed"},
    )

    listing = await prd10_client.get(
        "/api/v1/notifications", params={"is_read": False}
    )
    types = {item["type"] for item in listing.json()["data"]["items"]}
    assert "job_failed" in types
    # The success-path ``job_completed`` must NOT show up for a failed run.
    assert "job_completed" not in types


async def test_capture_link_failure_sets_fetch_status_failed(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/capture/link",
        json={
            "url": "https://example.com/broken",
            "_simulate_failure": "remote 404",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fetch_status"] == "failed"
    assert data["job"]["status"] == "failed"


async def test_capture_file_failure_emits_upload_failed_notification(prd10_client):
    presign = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={
            "filename": "broken.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    upload_id = presign.json()["data"]["upload_id"]

    commit = await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": upload_id,
            "filename": "broken.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "_simulate_failure": "PDF parser segfaulted",
        },
    )
    assert commit.status_code == 200
    body = commit.json()["data"]
    assert body["status"] == "failed"

    notif = await prd10_client.get(
        "/api/v1/notifications", params={"is_read": False}
    )
    items = notif.json()["data"]["items"]
    assert any(item["type"] == "upload_failed" for item in items)


async def test_capture_file_failure_marks_document_failed(prd10_client):
    presign = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={
            "filename": "x.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1,
        },
    )
    upload_id = presign.json()["data"]["upload_id"]

    commit = await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": upload_id,
            "filename": "x.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1,
            "_simulate_failure": "OCR died",
        },
    )
    document_id = commit.json()["data"]["document_id"]

    fetch = await prd10_client.get(f"/api/v1/kb/documents/{document_id}")
    # Failed documents are still readable so the UI can surface the error.
    assert fetch.status_code == 200
    assert fetch.json()["data"]["status"] == "failed"


async def test_failed_job_can_be_inspected_via_jobs_endpoint(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "x", "_simulate_failure": "boom"},
    )
    job_id = resp.json()["data"]["job"]["id"]

    job = await prd10_client.get(f"/api/v1/jobs/{job_id}")
    assert job.status_code == 200
    body = job.json()["data"]
    assert body["status"] == "failed"
    assert body["error"]["message"] == "boom"


async def test_cancel_failed_job_is_validation_error(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "x", "_simulate_failure": "boom"},
    )
    job_id = resp.json()["data"]["job"]["id"]

    cancel = await prd10_client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 400
