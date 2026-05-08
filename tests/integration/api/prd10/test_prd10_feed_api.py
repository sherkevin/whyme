"""PRD10 §9 Feed/Card endpoint tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _capture_text(client, text: str = "hello") -> dict:
    resp = await client.post("/api/v1/capture/text", json={"content": text})
    resp.raise_for_status()
    return resp.json()["data"]


async def test_feed_empty_returns_empty_envelope(prd10_client):
    resp = await prd10_client.get("/api/v1/feed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["items"] == []
    assert data["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 0,
        "has_more": False,
    }
    assert data["facets"] == {"types": [], "tags": []}


async def test_feed_returns_card_for_each_capture(prd10_client):
    await _capture_text(prd10_client, "想法 A")
    await _capture_text(prd10_client, "想法 B")

    resp = await prd10_client.get("/api/v1/feed")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    titles = sorted(i["title"] for i in items)
    assert titles == ["想法 A", "想法 B"]


async def test_feed_pagination_with_facets(prd10_client):
    for i in range(3):
        await _capture_text(prd10_client, f"题目 {i}")

    resp = await prd10_client.get(
        "/api/v1/feed", params={"page": 1, "page_size": 2}
    )
    body = resp.json()["data"]
    assert len(body["items"]) == 2
    assert body["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "has_more": True,
    }
    type_facets = body["facets"]["types"]
    assert len(type_facets) >= 1
    assert any(f["count"] == 3 for f in type_facets)


async def test_create_card_then_get_and_patch(prd10_client):
    create = await prd10_client.post(
        "/api/v1/cards",
        json={"title": "我的卡片", "content": "正文", "tags": ["x"]},
    )
    assert create.status_code == 201
    card = create.json()["data"]
    card_id = card["id"]

    fetch = await prd10_client.get(f"/api/v1/cards/{card_id}")
    assert fetch.status_code == 200
    assert fetch.json()["data"]["title"] == "我的卡片"

    patch = await prd10_client.patch(
        f"/api/v1/cards/{card_id}", json={"title": "改名"}
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["title"] == "改名"


async def test_favorite_and_unfavorite(prd10_client):
    captured = await _capture_text(prd10_client, "需要收藏")
    feed = await prd10_client.get("/api/v1/feed")
    card_id = feed.json()["data"]["items"][0]["id"]

    fav = await prd10_client.post(f"/api/v1/cards/{card_id}/favorite", json={})
    assert fav.status_code == 200
    assert fav.json()["data"]["is_favorite"] is True

    unfav = await prd10_client.post(
        f"/api/v1/cards/{card_id}/favorite", json={"is_favorite": False}
    )
    assert unfav.json()["data"]["is_favorite"] is False


async def test_soft_delete_hides_card_from_feed(prd10_client):
    await _capture_text(prd10_client, "要删除")
    feed = await prd10_client.get("/api/v1/feed")
    card_id = feed.json()["data"]["items"][0]["id"]

    delete = await prd10_client.delete(f"/api/v1/cards/{card_id}")
    assert delete.status_code == 200

    feed2 = await prd10_client.get("/api/v1/feed")
    assert feed2.json()["data"]["items"] == []

    fetch = await prd10_client.get(f"/api/v1/cards/{card_id}")
    assert fetch.status_code == 404


async def test_feed_isolated_per_user(prd10_client, prd10_other_client):
    await _capture_text(prd10_client, "我自己")
    other = await prd10_other_client.get("/api/v1/feed")
    assert other.json()["data"]["items"] == []
