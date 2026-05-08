"""PRD10 §10 Knowledge Base endpoint tests."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _create_folder(client, name: str = "产品设计") -> dict:
    resp = await client.post(
        "/api/v1/kb/folders",
        json={"name": name, "description": "测试文件夹", "color": "#1f2937"},
    )
    resp.raise_for_status()
    return resp.json()["data"]


async def _commit_pdf(client, target_folder_id: str | None = None) -> dict:
    presign = await client.post(
        "/api/v1/uploads/presign",
        json={"filename": "spec.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
    )
    upload_id = presign.json()["data"]["upload_id"]
    payload: dict = {
        "upload_id": upload_id,
        "filename": "spec.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024,
    }
    if target_folder_id is not None:
        payload["target_folder_id"] = target_folder_id

    commit = await client.post("/api/v1/capture/file/commit", json=payload)
    commit.raise_for_status()
    return commit.json()["data"]


async def test_overview_starts_empty(prd10_client):
    resp = await prd10_client.get("/api/v1/kb/overview")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["stats"] == {
        "folder_count": 0,
        "document_count": 0,
        "favorite_count": 0,
        "recent_updated_count": 0,
    }
    assert body["recent_documents"] == []
    assert body["favorite_folders"] == []


async def test_create_and_list_folders(prd10_client):
    folder = await _create_folder(prd10_client, "产品")
    assert uuid.UUID(folder["id"])
    assert folder["name"] == "产品"

    listing = await prd10_client.get(
        "/api/v1/kb/folders", params={"include_counts": "true"}
    )
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == folder["id"]
    assert items[0]["document_count"] == 0


async def test_list_folders_default_no_counts(prd10_client):
    await _create_folder(prd10_client, "默认不带计数")
    listing = await prd10_client.get("/api/v1/kb/folders")
    items = listing.json()["data"]["items"]
    assert items, "expected at least one folder"
    assert "document_count" not in items[0]


async def test_list_folders_is_favorite_filter_and_sort_by_updated_at(prd10_client):
    fav = await _create_folder(prd10_client, "会收藏-alpha")
    plain = await _create_folder(prd10_client, "不收藏-beta")

    patch = await prd10_client.patch(
        f"/api/v1/kb/folders/{fav['id']}",
        json={"is_favorite": True},
    )
    patch.raise_for_status()

    fav_only = await prd10_client.get(
        "/api/v1/kb/folders", params={"is_favorite": "true"}
    )
    assert fav_only.status_code == 200
    fav_items = fav_only.json()["data"]["items"]
    assert len(fav_items) == 1
    assert fav_items[0]["id"] == fav["id"]

    bump = await prd10_client.patch(
        f"/api/v1/kb/folders/{fav['id']}",
        json={"name": "会收藏-alpha-改"},
    )
    bump.raise_for_status()

    sorted_resp = await prd10_client.get(
        "/api/v1/kb/folders", params={"sort_by": "updated_at"}
    )
    sorted_resp.raise_for_status()
    ids = [it["id"] for it in sorted_resp.json()["data"]["items"]]
    assert ids[0] == fav["id"], "updated folder should sort first"


async def test_documents_listed_under_folder_after_capture(prd10_client):
    folder = await _create_folder(prd10_client)
    committed = await _commit_pdf(prd10_client, target_folder_id=folder["id"])

    resp = await prd10_client.get(
        "/api/v1/kb/documents", params={"folder_id": folder["id"]}
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert committed["document_id"] in ids
    assert body["pagination"]["total"] == 1


async def test_get_document_includes_content_and_folder_block(prd10_client):
    folder = await _create_folder(prd10_client)
    committed = await _commit_pdf(prd10_client, target_folder_id=folder["id"])

    resp = await prd10_client.get(f"/api/v1/kb/documents/{committed['document_id']}")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["id"] == committed["document_id"]
    assert payload["status"] == "ready"
    assert payload.get("folder", {}).get("id") == folder["id"]


async def test_move_document(prd10_client):
    src_folder = await _create_folder(prd10_client, "Inbox")
    dst_folder = await _create_folder(prd10_client, "归档")
    committed = await _commit_pdf(prd10_client, target_folder_id=src_folder["id"])

    move = await prd10_client.post(
        f"/api/v1/kb/documents/{committed['document_id']}/move",
        json={"target_folder_id": dst_folder["id"]},
    )
    assert move.status_code == 200
    assert move.json()["data"]["folder_id"] == dst_folder["id"]


async def test_create_document_blank_in_folder(prd10_client):
    """§15.22 — biz prototype 新建文档 modal 真实化路径。"""

    folder = await _create_folder(prd10_client, "产品设计")
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "新的产品设计笔记",
            "folder_id": folder["id"],
            "template": "blank",
        },
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["title"] == "新的产品设计笔记"
    assert body["folder_id"] == folder["id"]
    assert body["status"] == "ready"
    assert body["document_type"] == "note"
    assert body["content"] == ""
    assert body["word_count"] == 0
    # New doc must show up immediately in the folder's listing.
    listing = await prd10_client.get(
        "/api/v1/kb/documents", params={"folder_id": folder["id"]}
    )
    ids = [item["id"] for item in listing.json()["data"]["items"]]
    assert body["id"] in ids


async def test_create_document_research_template_seeds_content(prd10_client):
    folder = await _create_folder(prd10_client, "研究")
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "Q2 用户调研",
            "folder_id": folder["id"],
            "template": "research_report",
        },
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["content"]
    assert "研究目标" in body["content"]
    assert "关键发现" in body["content"]
    assert body["word_count"] >= 0


async def test_create_document_solution_outline_template(prd10_client):
    folder = await _create_folder(prd10_client, "方案")
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "推荐方案 V1",
            "folder_id": folder["id"],
            "template": "solution_outline",
        },
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert "方案概述" in body["content"]
    assert "关键里程碑" in body["content"]


async def test_create_document_without_folder_lands_at_root(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "未归档笔记",
            "template": "blank",
        },
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["folder_id"] is None
    assert body["folder"] is None


async def test_create_document_explicit_content_wins(prd10_client):
    folder = await _create_folder(prd10_client)
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "我自己的提纲",
            "folder_id": folder["id"],
            "template": "research_report",
            "content": "explicit body wins template scaffold",
        },
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["content"] == "explicit body wins template scaffold"
    # Word count from the explicit body, not the seeded template.
    assert body["word_count"] == 5


async def test_create_document_validates_folder_ownership(
    prd10_client, prd10_other_client
):
    """Cannot create a document inside another user's folder."""

    other_folder = await _create_folder(prd10_other_client, "他人")
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={
            "title": "越权创建",
            "folder_id": other_folder["id"],
            "template": "blank",
        },
    )
    assert resp.status_code == 404


async def test_create_document_rejects_blank_title(prd10_client):
    resp = await prd10_client.post(
        "/api/v1/kb/documents",
        json={"title": ""},
    )
    assert resp.status_code == 422


async def test_delete_folder_with_move_to_root_strategy(prd10_client):
    folder = await _create_folder(prd10_client)
    committed = await _commit_pdf(prd10_client, target_folder_id=folder["id"])

    delete = await prd10_client.request(
        "DELETE",
        f"/api/v1/kb/folders/{folder['id']}",
        json={"strategy": "move_to_root"},
    )
    assert delete.status_code == 200
    body = delete.json()["data"]
    assert body["deleted"] is True
    assert body["id"] == folder["id"]

    doc = await prd10_client.get(f"/api/v1/kb/documents/{committed['document_id']}")
    assert doc.status_code == 200
    assert doc.json()["data"]["folder_id"] is None


async def test_delete_folder_no_body_defaults_to_move_to_root(prd10_client):
    folder = await _create_folder(prd10_client, "无 body 删除")
    committed = await _commit_pdf(prd10_client, target_folder_id=folder["id"])

    delete = await prd10_client.delete(f"/api/v1/kb/folders/{folder['id']}")
    assert delete.status_code == 200
    assert delete.json()["data"]["deleted"] is True

    doc = await prd10_client.get(f"/api/v1/kb/documents/{committed['document_id']}")
    assert doc.status_code == 200
    assert doc.json()["data"]["folder_id"] is None


async def test_delete_folder_with_delete_children_strategy(prd10_client):
    folder = await _create_folder(prd10_client, "硬删")
    committed = await _commit_pdf(prd10_client, target_folder_id=folder["id"])

    delete = await prd10_client.request(
        "DELETE",
        f"/api/v1/kb/folders/{folder['id']}",
        json={"strategy": "delete_children"},
    )
    assert delete.status_code == 200

    doc = await prd10_client.get(f"/api/v1/kb/documents/{committed['document_id']}")
    assert doc.status_code == 404


async def test_other_user_cannot_see_folders(prd10_client, prd10_other_client):
    await _create_folder(prd10_client, "我的")

    resp = await prd10_other_client.get("/api/v1/kb/folders")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


# ---------------------------------------------------------------------------
# PRD10 §10.4 dedicated folder move/rename endpoints
# ---------------------------------------------------------------------------


async def test_rename_folder_endpoint(prd10_client):
    folder = await _create_folder(prd10_client, "Old Name")
    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{folder['id']}/rename",
        json={"name": "New Name"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["name"] == "New Name"


async def test_rename_folder_validates_blank(prd10_client):
    folder = await _create_folder(prd10_client, "X")
    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{folder['id']}/rename",
        json={"name": ""},
    )
    # PRD10 envelope: validation error from FastAPI (422) for the empty name.
    assert resp.status_code == 422


async def test_move_folder_under_parent(prd10_client):
    parent = await _create_folder(prd10_client, "Parent")
    child = await _create_folder(prd10_client, "Child")

    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{child['id']}/move",
        json={"parent_id": parent["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["parent_id"] == parent["id"]


async def test_move_folder_to_root(prd10_client):
    parent = await _create_folder(prd10_client, "Parent")
    child = await _create_folder(prd10_client, "Child")
    # First move it under parent so we can move it back to root.
    await prd10_client.post(
        f"/api/v1/kb/folders/{child['id']}/move",
        json={"parent_id": parent["id"]},
    )
    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{child['id']}/move",
        json={"parent_id": None},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["parent_id"] is None


async def test_move_folder_into_self_rejected(prd10_client):
    folder = await _create_folder(prd10_client, "Self")
    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{folder['id']}/move",
        json={"parent_id": folder["id"]},
    )
    assert resp.status_code == 400
    assert "VALIDATION_ERROR" in resp.text or "cannot be its own parent" in resp.text


async def test_move_folder_into_descendant_rejected(prd10_client):
    grand = await _create_folder(prd10_client, "Grand")
    parent = await _create_folder(prd10_client, "Parent")
    child = await _create_folder(prd10_client, "Child")

    # Build chain: Grand -> Parent -> Child
    await prd10_client.post(
        f"/api/v1/kb/folders/{parent['id']}/move",
        json={"parent_id": grand["id"]},
    )
    await prd10_client.post(
        f"/api/v1/kb/folders/{child['id']}/move",
        json={"parent_id": parent["id"]},
    )

    # Trying to move Grand under Child must fail (would create a cycle).
    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{grand['id']}/move",
        json={"parent_id": child["id"]},
    )
    assert resp.status_code == 400


async def test_move_folder_404_for_unknown_parent(prd10_client):
    folder = await _create_folder(prd10_client, "F")
    import uuid as _uuid

    resp = await prd10_client.post(
        f"/api/v1/kb/folders/{folder['id']}/move",
        json={"parent_id": str(_uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_other_user_cannot_rename_or_move_my_folder(
    prd10_client, prd10_other_client
):
    folder = await _create_folder(prd10_client, "Mine")

    rename = await prd10_other_client.post(
        f"/api/v1/kb/folders/{folder['id']}/rename",
        json={"name": "Hijacked"},
    )
    assert rename.status_code == 404

    move = await prd10_other_client.post(
        f"/api/v1/kb/folders/{folder['id']}/move",
        json={"parent_id": None},
    )
    assert move.status_code == 404
