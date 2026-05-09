"""PRD10 §8 Capture endpoint tests."""

from __future__ import annotations

import importlib
import uuid

import pytest
from sqlalchemy import select

from agent_os.ai import llm_provider
from agent_os.search_engine.models import SearchIndex

pytestmark = pytest.mark.asyncio


class CaptureJsonProvider:
    async def complete(self, messages, tools=None, **kwargs):
        return {
            "content": (
                '{"title":"真实灵感标题","summary":"这是由测试 LLM 生成的真实摘要",'
                '"tags":["产品洞察","AI"],"folder_hint":"产品设计",'
                '"content_type":"insight","entities":["Mydow"]}'
            ),
            "role": "assistant",
            "model": "fake-capture-llm",
        }


async def test_capture_text_creates_inbox_item_and_completes_job(
    prd10_client, prd10_sessionmaker
):
    response = await prd10_client.post(
        "/api/v1/capture/text",
        json={
            "content": "今天想到一个新的产品想法，关于知识库的双向同步。",
            "title": "知识库双向同步",
            "tags": ["产品", "知识库"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["request_id"].startswith("req_")
    assert response.headers.get("x-request-id") == body["request_id"]

    inbox = body["data"]["inbox_item"]
    assert uuid.UUID(inbox["id"])
    assert inbox["type"] == "text"
    # V1 pseudo-worker drives the InboxItem to processed before responding.
    assert inbox["status"] == "processed"
    assert inbox["processing_status"] == "completed"

    job = body["data"]["job"]
    assert job is not None
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["job_type"] == "summarize"

    # §17.1 — every text capture also lands in the KB as a Document, so
    # there are two SearchIndex rows (one for the Card, one for the
    # Document) sharing the same title. Both must be embedded.
    async with prd10_sessionmaker() as session:
        rows = (
            await session.execute(
                select(SearchIndex).where(SearchIndex.title == "知识库双向同步")
            )
        ).scalars().all()
    assert len(rows) == 2
    types = {row.item_type for row in rows}
    assert types == {"card", "document"}
    for row in rows:
        assert row.embedding_id
        assert isinstance(row.embedding, list) and row.embedding

    # §17.1 — capture/text now returns the enrichment metadata + the
    # auto-created Document id so the SPA can navigate to the new card
    # immediately.
    assert "document_id" in body["data"]
    assert body["data"]["document_id"]
    assert "enrichment" in body["data"]


async def test_capture_text_validation_error_envelope(prd10_client):
    response = await prd10_client.post("/api/v1/capture/text", json={"content": ""})
    # FastAPI's default validator returns 422; PRD10 envelope is wrapped by
    # the global exception handler in production. For this slice we only need
    # the outer status to reflect a validation failure.
    assert response.status_code in {400, 422}


async def test_capture_text_auto_process_false_skips_job(prd10_client):
    response = await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "不自动处理", "auto_process": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["inbox_item"]["status"] == "received"
    assert body["data"]["job"] is None


async def test_capture_link_creates_source_and_finishes(prd10_client, monkeypatch):
    async def fake_fetch_link_content(url):
        from agent_os.capture.link_service import LinkFetchResult

        return LinkFetchResult(
            url=url,
            title="Example Article",
            description="A real fetched article summary.",
            text="Fetched article body about AI product research.",
            content_type="text/html",
            links=[],
        )

    capture_router = importlib.import_module("agent_os.capture.router")
    monkeypatch.setattr(capture_router, "fetch_link_content", fake_fetch_link_content)
    response = await prd10_client.post(
        "/api/v1/capture/link",
        json={
            "url": "https://example.com/article",
            "note": "这篇文章值得一看",
            "tags": ["AI"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert uuid.UUID(data["inbox_item_id"])
    assert uuid.UUID(data["source_id"])
    assert data["fetch_status"] == "completed"
    assert data["job"]["status"] == "completed"
    assert uuid.UUID(data["document_id"])
    assert uuid.UUID(data["card_id"])
    assert "Fetched article body" in data["content_excerpt"]


async def test_capture_text_uses_llm_before_return(prd10_client):
    llm_provider.set_test_provider(CaptureJsonProvider())
    try:
        response = await prd10_client.post(
            "/api/v1/capture/text",
            json={"content": "这是一段很长的产品灵感，需要 AI 生成标题、摘要和标签。"},
        )
    finally:
        llm_provider.set_test_provider(None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["enrichment"]["used_llm"] is True
    assert data["enrichment"]["title"] == "真实灵感标题"
    assert data["card"]["title"] == "真实灵感标题"
    assert data["card"]["summary"] == "这是由测试 LLM 生成的真实摘要"
    assert "产品洞察" in data["card"]["tags"]


async def test_uploads_presign_returns_local_url(prd10_client):
    response = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={
            "filename": "spec.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert uuid.UUID(data["upload_id"])
    upload_id = data["upload_id"]
    # The presign URL must let the client PUT bytes against this local server.
    assert data["upload_url"].endswith(f"/api/v1/uploads/local/{upload_id}")
    # The downloadable file URL must point back at the same upload (with the
    # raw-bytes suffix) so the V1 web app can render previews without an
    # external object store.
    assert f"/api/v1/uploads/local/{upload_id}/raw" in data["file_url"]
    assert data["expires_in"] == 900


async def test_capture_file_commit_creates_document_and_inbox(prd10_client):
    presign = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={
            "filename": "spec.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    upload_id = presign.json()["data"]["upload_id"]

    response = await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": upload_id,
            "filename": "spec.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert uuid.UUID(data["source_id"])
    assert uuid.UUID(data["document_id"])
    assert uuid.UUID(data["inbox_item_id"])
    assert uuid.UUID(data["job_id"])
    assert data["status"] == "completed"


async def test_capture_writes_completion_notification(prd10_client):
    create = await prd10_client.post(
        "/api/v1/capture/text",
        json={"content": "提醒我吃饭"},
    )
    assert create.status_code == 200

    unread = await prd10_client.get("/api/v1/notifications/unread-count")
    assert unread.status_code == 200
    assert unread.json()["data"]["count"] >= 1

    listing = await prd10_client.get("/api/v1/notifications", params={"is_read": False})
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert any(item["type"] == "job_completed" for item in items)
async def test_capture_text_accepts_voice_alias_and_persists_transcript(
    prd10_client,
):
    response = await prd10_client.post(
        "/api/v1/capture/text",
        json={
            "content": "voice transcript should be stored as a real text asset",
            "title": "Voice transcript",
            "tags": ["voice"],
            "type": "voice",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["inbox_item"]["type"] == "text"
    assert body["data"]["inbox_item"]["raw_content"] == (
        "voice transcript should be stored as a real text asset"
    )
    assert body["data"]["document_id"]
