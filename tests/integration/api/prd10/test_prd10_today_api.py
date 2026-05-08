"""PRD10 §7 ``GET /api/v1/today`` aggregator tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_today_empty_payload_shape(prd10_client):
    resp = await prd10_client.get("/api/v1/today")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    data = body["data"]
    # PRD10 §7.1 mandates the (id/name/avatar_url) subset; additional user
    # fields are allowed and used by Agent 1's expanded payload.
    assert {"id", "name", "avatar_url"}.issubset(data["user"].keys())
    assert data["stats"] == {
        "today_capture_count": 0,
        "pending_task_count": 0,
        "knowledge_items_count": 0,
        "weekly_growth_rate": 0.0,
    }
    assert [a["key"] for a in data["quick_actions"]] == [
        "text",
        "link",
        "audio",
        "file",
    ]
    assert data["tasks"] == []
    assert "title" in data["insight_preview"]
    assert "summary" in data["insight_preview"]


async def test_today_counts_capture_for_current_day(prd10_client):
    for _ in range(3):
        await prd10_client.post("/api/v1/capture/text", json={"content": "hi"})

    resp = await prd10_client.get("/api/v1/today")
    stats = resp.json()["data"]["stats"]
    assert stats["today_capture_count"] == 3


async def test_today_counts_documents(prd10_client):
    presign = await prd10_client.post(
        "/api/v1/uploads/presign",
        json={"filename": "a.pdf", "mime_type": "application/pdf", "size_bytes": 10},
    )
    upload_id = presign.json()["data"]["upload_id"]
    await prd10_client.post(
        "/api/v1/capture/file/commit",
        json={
            "upload_id": upload_id,
            "filename": "a.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 10,
        },
    )

    resp = await prd10_client.get("/api/v1/today")
    stats = resp.json()["data"]["stats"]
    assert stats["knowledge_items_count"] == 1


async def test_today_isolation_between_users(prd10_client, prd10_other_client):
    await prd10_client.post("/api/v1/capture/text", json={"content": "私人"})

    resp = await prd10_other_client.get("/api/v1/today")
    assert resp.json()["data"]["stats"]["today_capture_count"] == 0


async def test_today_tasks_derived_from_prd10_tasks(prd10_client):
    created = await prd10_client.post(
        "/api/v1/tasks",
        json={
            "title": "完成今日复盘",
            "description": "今晚 22 点前发出复盘",
            "priority": "high",
        },
    )
    assert created.status_code == 201

    resp = await prd10_client.get("/api/v1/today")
    data = resp.json()["data"]
    tasks = data["tasks"]
    assert len(tasks) == 1
    task = tasks[0]
    assert task["title"] == "完成今日复盘"
    assert task["status"] == "todo"
    assert task["priority"] == "high"
    assert task["due_at"] is None
    assert data["stats"]["pending_task_count"] == 1


async def test_today_pending_task_count_drops_when_completed(prd10_client):
    create = await prd10_client.post(
        "/api/v1/tasks",
        json={
            "title": "auto-processed task",
            "description": "should be completed and not counted as pending",
        },
    )
    assert create.status_code == 201
    task_id = create.json()["data"]["id"]

    done = await prd10_client.post(f"/api/v1/tasks/{task_id}/complete")
    assert done.status_code == 200

    resp = await prd10_client.get("/api/v1/today")
    data = resp.json()["data"]
    tasks = data["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["status"] == "done"
    assert data["stats"]["pending_task_count"] == 0
