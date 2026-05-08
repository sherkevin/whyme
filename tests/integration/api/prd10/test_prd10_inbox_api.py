"""PRD10 §8.5 / §8.6 InboxItem listing & status update tests."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _capture(client, *, kind: str = "text", **extra) -> dict:
    """Wrapper that returns the inbox_item dict from a capture call."""

    if kind == "text":
        resp = await client.post(
            "/api/v1/capture/text",
            json={"content": extra.get("content", "hello"), **{k: v for k, v in extra.items() if k != "content"}},
        )
    elif kind == "link":
        resp = await client.post(
            "/api/v1/capture/link",
            json={"url": extra.get("url", "https://example.com"), **{k: v for k, v in extra.items() if k != "url"}},
        )
    else:
        raise ValueError(kind)

    resp.raise_for_status()
    data = resp.json()["data"]
    if kind == "text":
        return data["inbox_item"]
    return {"id": data["inbox_item_id"], "type": "link"}


async def test_list_inbox_empty(prd10_client):
    resp = await prd10_client.get("/api/v1/inbox")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["items"] == []
    assert body["pagination"]["total"] == 0


async def test_list_inbox_returns_all_three(prd10_client):
    """List endpoint returns all captures (ordering by created_at is stable
    only at the millisecond granularity Postgres provides; SQLite in tests
    can put rows on the same timestamp, so the assertion focuses on
    set-equality and pagination metadata rather than micro-ordering)."""

    await _capture(prd10_client, content="一")
    await _capture(prd10_client, content="二")
    await _capture(prd10_client, content="三")

    resp = await prd10_client.get("/api/v1/inbox")
    body = resp.json()["data"]
    items = body["items"]
    assert len(items) == 3
    assert body["pagination"]["total"] == 3
    assert {i["raw_content"] for i in items} == {"一", "二", "三"}


async def test_list_inbox_filter_by_type(prd10_client):
    await _capture(prd10_client, content="text item")
    await _capture(prd10_client, kind="link", url="https://example.com/article")

    only_links = await prd10_client.get("/api/v1/inbox", params={"type": "link"})
    items = only_links.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["type"] == "link"


async def test_list_inbox_filter_by_status(prd10_client):
    await _capture(prd10_client, content="auto processed")
    await _capture(prd10_client, content="received only", auto_process=False)

    received = await prd10_client.get(
        "/api/v1/inbox", params={"status": "received"}
    )
    items = received.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["status"] == "received"


async def test_list_inbox_invalid_filter_returns_validation_error(prd10_client):
    resp = await prd10_client.get("/api/v1/inbox", params={"type": "weird"})
    assert resp.status_code == 400
    body = resp.json()
    # PRD10 envelope path
    if body.get("success") is False:
        assert body["error"]["code"] == "VALIDATION_ERROR"
    else:
        assert body["detail"]["code"] == "VALIDATION_ERROR"


async def test_patch_inbox_item_archives_and_changes_tags(prd10_client):
    item = await _capture(prd10_client, content="to archive")
    item_id = item["id"]

    patch = await prd10_client.patch(
        f"/api/v1/inbox/{item_id}",
        json={"status": "archived", "tags": ["重要", "已读"]},
    )
    assert patch.status_code == 200
    body = patch.json()["data"]
    assert body["status"] == "archived"
    assert body["tags"] == ["重要", "已读"]


async def test_patch_inbox_item_invalid_status(prd10_client):
    item = await _capture(prd10_client, content="bad status target")
    resp = await prd10_client.patch(
        f"/api/v1/inbox/{item['id']}", json={"status": "weird"}
    )
    assert resp.status_code == 400


async def test_patch_inbox_item_404_for_other_user(prd10_client, prd10_other_client):
    item = await _capture(prd10_client, content="mine")

    resp = await prd10_other_client.patch(
        f"/api/v1/inbox/{item['id']}", json={"status": "archived"}
    )
    assert resp.status_code == 404


async def test_patch_inbox_item_not_found(prd10_client):
    resp = await prd10_client.patch(
        f"/api/v1/inbox/{uuid.uuid4()}", json={"status": "archived"}
    )
    assert resp.status_code == 404
