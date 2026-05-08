"""PRD10 §14 task API tests."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_task_crud_complete_and_soft_delete(prd10_client):
    created = await prd10_client.post(
        "/api/v1/tasks",
        json={
            "title": "完成 PRD10 任务联调",
            "description": "验证任务真实落库",
            "priority": "high",
            "tags": ["PRD10", "任务"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["success"] is True
    task = body["data"]
    task_id = task["id"]
    assert task["status"] == "todo"
    assert task["priority"] == "high"

    listing = await prd10_client.get("/api/v1/tasks", params={"status": "todo"})
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert [item["id"] for item in items] == [task_id]

    detail = await prd10_client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "完成 PRD10 任务联调"

    updated = await prd10_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "doing", "priority": "urgent", "tags": ["收尾"]},
    )
    assert updated.status_code == 200
    updated_data = updated.json()["data"]
    assert updated_data["status"] == "doing"
    assert updated_data["priority"] == "urgent"
    assert updated_data["tags"] == ["收尾"]

    completed = await prd10_client.post(f"/api/v1/tasks/{task_id}/complete")
    assert completed.status_code == 200
    completed_data = completed.json()["data"]
    assert completed_data["status"] == "done"
    assert completed_data["completed_at"]

    deleted = await prd10_client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"id": task_id, "deleted": True}

    after_delete = await prd10_client.get(f"/api/v1/tasks/{task_id}")
    assert after_delete.status_code == 404


async def test_task_api_isolates_users(prd10_client, prd10_other_client):
    created = await prd10_client.post(
        "/api/v1/tasks",
        json={"title": "只有当前用户能看到"},
    )
    assert created.status_code == 201
    task_id = created.json()["data"]["id"]

    other_detail = await prd10_other_client.get(f"/api/v1/tasks/{task_id}")
    assert other_detail.status_code == 404

    other_listing = await prd10_other_client.get("/api/v1/tasks")
    assert other_listing.status_code == 200
    assert other_listing.json()["data"]["items"] == []


async def test_task_filters_and_validation_errors(prd10_client):
    await prd10_client.post(
        "/api/v1/tasks",
        json={"title": "高优先级 AI 任务", "priority": "high", "source_type": "ai"},
    )
    await prd10_client.post(
        "/api/v1/tasks",
        json={"title": "低优先级手动任务", "priority": "low", "source_type": "manual"},
    )

    filtered = await prd10_client.get(
        "/api/v1/tasks",
        params={"priority": "high", "source_type": "ai"},
    )
    assert filtered.status_code == 200
    items = filtered.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "高优先级 AI 任务"

    invalid_filter = await prd10_client.get(
        "/api/v1/tasks",
        params={"status": "pending"},
    )
    assert invalid_filter.status_code == 400
    body = invalid_filter.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    missing = await prd10_client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert missing.status_code == 404
